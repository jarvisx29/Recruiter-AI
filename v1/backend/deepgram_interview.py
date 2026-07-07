import asyncio
import json
import os
import re

import httpx
import websockets
from fastapi import WebSocket

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

TTS_SAMPLE_RATE = 24000
TTS_URL = (
    "https://api.deepgram.com/v1/speak"
    "?model=aura-athena-en"
    "&encoding=linear16"
    f"&sample_rate={TTS_SAMPLE_RATE}"
    "&container=none"
)

# Deepgram: VAD (UtteranceEnd) + final STT transcript
DEEPGRAM_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?model=nova-2"
    "&language=en"
    "&encoding=linear16"
    "&sample_rate=16000"
    "&channels=1"
    "&endpointing=400"
    "&interim_results=true"
    "&utterance_end_ms=2000"
    "&smart_format=true"
)

# Known STT mishearings → correct technical terms
_TERM_FIXES = {
    # scikit-learn variants
    "keketlone": "scikit-learn", "kik it": "scikit-learn",
    "kick it learn": "scikit-learn", "kicket learn": "scikit-learn",
    "skit learn": "scikit-learn", "sk learn": "scikit-learn",
    "psychic learn": "scikit-learn", "kick it along": "scikit-learn",
    "kik it along": "scikit-learn", "slice it learn": "scikit-learn",
    "slice, it learn": "scikit-learn", "scikit learn": "scikit-learn",
    "secret line": "scikit-learn", "secret learn": "scikit-learn",
    "secret lean": "scikit-learn", "cicket learn": "scikit-learn",
    # LeetCode
    "lead code": "LeetCode", "leet code": "LeetCode",
    "lite code": "LeetCode", "lead code sums": "LeetCode problems",
    # hashmap
    "ashma": "hashmap", "ash ma": "hashmap", "ash map": "hashmap",
    "hash mob": "hashmap", "hash mop": "hashmap", "has map": "hashmap",
    # other terms
    "na10": "n8n", "nato": "n8n", "n 10": "n8n",
    "random board": "random forest", "random port": "random forest",
    "binary search three": "binary search tree",
    "pie torch": "PyTorch", "num pie": "NumPy", "pan das": "pandas",
    "tensor flow": "TensorFlow", "fast api": "FastAPI",
    "data race": "data structure",
    "over feeding": "overfitting", "under feeding": "underfitting",
    "regularisation": "regularization", "normalisation": "normalization",
}


def _fix_transcript(text: str) -> str:
    """Apply known-term corrections and collapse repeated-word hallucinations."""
    lower = text.lower()
    for wrong, right in _TERM_FIXES.items():
        if wrong in lower:
            lower = lower.replace(wrong, right)
    lower = re.sub(r'\b(\w+)(?:[,\s]+\1){2,}', r'\1', lower)
    if text and text[0].isupper() and lower:
        lower = lower[0].upper() + lower[1:]
    return lower


async def run_session(browser_ws: WebSocket, engine) -> None:
    if not DEEPGRAM_API_KEY:
        await browser_ws.send_json({"type": "error", "message": "DEEPGRAM_API_KEY not set."})
        return

    agent_speaking = False
    processing = False
    done = asyncio.Event()
    speak_task = None
    recording_turn = False
    dg_finals = []  # Deepgram final transcripts accumulated during user's turn

    audio_queue: asyncio.Queue = asyncio.Queue()

    async def jt(data: dict):
        await browser_ws.send_json(data)

    async def speak(text: str):
        nonlocal agent_speaking, recording_turn
        agent_speaking = True
        recording_turn = False
        dg_finals.clear()

        await jt({"type": "agent_start_talking"})
        await jt({"type": "audio_start", "sampleRate": TTS_SAMPLE_RATE})

        try:
            async with httpx.AsyncClient(timeout=30) as http:
                async with http.stream(
                    "POST", TTS_URL,
                    headers={
                        "Authorization": f"Token {DEEPGRAM_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={"text": text},
                ) as resp:
                    async for chunk in resp.aiter_bytes(chunk_size=4096):
                        await browser_ws.send_bytes(chunk)
        except asyncio.CancelledError:
            pass

        await jt({"type": "audio_end"})
        await jt({"type": "agent_stop_talking"})
        agent_speaking = False
        dg_finals.clear()
        recording_turn = True

    async def interrupt_agent():
        nonlocal speak_task
        if speak_task and not speak_task.done():
            speak_task.cancel()
            try:
                await speak_task
            except asyncio.CancelledError:
                pass
        await jt({"type": "clear_audio"})

    # ── opening ───────────────────────────────────────────────────────────────
    opening = await engine.get_opening()
    await jt({"type": "transcript", "role": "agent", "text": opening})
    speak_task = asyncio.create_task(speak(opening))
    await speak_task
    # Override recording_turn so the 1s backlog drain doesn't pollute dg_finals
    recording_turn = False
    await jt({"type": "user_turn"})

    # ── tasks ─────────────────────────────────────────────────────────────────

    async def receive_from_browser():
        try:
            while not done.is_set():
                message = await browser_ws.receive()
                if message.get("type") == "websocket.disconnect":
                    done.set()
                    break
                raw = message.get("bytes")
                if raw:
                    await audio_queue.put(raw)
        except Exception:
            done.set()
        finally:
            await audio_queue.put(None)

    async def forward_to_deepgram(dg_ws):
        while not done.is_set():
            try:
                chunk = await asyncio.wait_for(audio_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            if chunk is None:
                break
            try:
                await dg_ws.send(chunk)
            except Exception:
                break

    async def handle_deepgram(dg_ws):
        nonlocal processing, speak_task, recording_turn

        async for raw in dg_ws:
            if done.is_set():
                break
            if not isinstance(raw, str):
                continue
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "Results":
                alts = data.get("channel", {}).get("alternatives", [{}])
                text = alts[0].get("transcript", "")
                is_final = data.get("is_final", False)

                if text and agent_speaking:
                    await interrupt_agent()
                    recording_turn = True
                    dg_finals.clear()

                if is_final and text and recording_turn:
                    # Accumulate Deepgram's final transcript for this utterance
                    dg_finals.append(text)
                elif not is_final and text:
                    await jt({"type": "interim", "text": text})

            elif msg_type == "UtteranceEnd":
                if processing or not recording_turn:
                    dg_finals.clear()
                    continue

                # What Deepgram actually heard — same source as the live transcript
                raw_answer = " ".join(dg_finals).strip()
                dg_finals.clear()
                recording_turn = False

                if not raw_answer or len(raw_answer) < 2:
                    recording_turn = True
                    continue

                if agent_speaking:
                    await interrupt_agent()

                answer = _fix_transcript(raw_answer)

                processing = True
                await jt({"type": "processing"})
                await jt({"type": "transcript", "role": "user", "text": answer})

                result = await engine.process_answer(answer)
                response_text = result.get("response_text", "")

                await jt({"type": "transcript", "role": "agent", "text": response_text})
                speak_task = asyncio.create_task(speak(response_text))
                await speak_task
                processing = False

                if result.get("interview_complete"):
                    engine.is_interview_done = True
                    await jt({"type": "interview_complete"})
                    done.set()
                    return

                await jt({"type": "user_turn"})

    # ── connect Deepgram and run ──────────────────────────────────────────────
    dg_headers = [("Authorization", f"Token {DEEPGRAM_API_KEY}")]

    try:
        async with websockets.connect(DEEPGRAM_URL, extra_headers=dg_headers) as dg_ws:
            tasks = [
                asyncio.create_task(receive_from_browser()),
                asyncio.create_task(forward_to_deepgram(dg_ws)),
                asyncio.create_task(handle_deepgram(dg_ws)),
            ]
            # 1s drain: backlog flows to Deepgram but dg_finals stays clear
            await asyncio.sleep(1.0)
            dg_finals.clear()
            recording_turn = True
            try:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                done.set()
                if speak_task and not speak_task.done():
                    speak_task.cancel()
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    except Exception as e:
        await jt({"type": "error", "message": str(e)})
