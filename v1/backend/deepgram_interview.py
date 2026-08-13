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

# Nova-3: better technical vocabulary than Nova-2
# utterance_end_ms=5000: 5s silence fallback for mid-thought pauses
# Sentence-completion detection (2s after terminal punctuation) is the primary trigger
DEEPGRAM_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?model=nova-3"
    "&language=en"
    "&encoding=linear16"
    "&sample_rate=16000"
    "&channels=1"
    "&endpointing=500"
    "&interim_results=true"
    "&utterance_end_ms=5000"
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
    # GraphQL
    "greed ai": "GraphQL", "greed ql": "GraphQL", "graph ql": "GraphQL",
    "graph q l": "GraphQL", "graph cue l": "GraphQL",
    # schema
    "scama": "schema", "skim a": "schema", "skim ah": "schema",
    "skema": "schema", "shema": "schema",
    # policies / policy
    "colis": "policies", "collis": "policies",
    # Kubernetes
    "cube ernetes": "Kubernetes", "cube nettles": "Kubernetes",
    "q bernetes": "Kubernetes", "kubernetes": "Kubernetes",
    "cube rnetes": "Kubernetes",
    # Docker / DevOps
    "doc ker": "Docker", "doc care": "Docker",
    "dev ops": "DevOps", "deaf ops": "DevOps",
    # CI/CD
    "c i c d": "CI/CD", "si si di": "CI/CD",
    # microservices
    "micro services": "microservices", "micro service": "microservice",
    # PostgreSQL / MongoDB
    "post gres": "PostgreSQL", "post gray sql": "PostgreSQL",
    "postgres ql": "PostgreSQL", "post grease ql": "PostgreSQL",
    "mongo db": "MongoDB", "mango db": "MongoDB",
    # REST API
    "rest a p i": "REST API", "restapi": "REST API",
    # other terms
    "na10": "n8n", "nato": "n8n", "n 10": "n8n",
    "random board": "random forest", "random port": "random forest",
    "binary search three": "binary search tree",
    "pie torch": "PyTorch", "num pie": "NumPy", "pan das": "pandas",
    "tensor flow": "TensorFlow", "fast api": "FastAPI",
    "data race": "data structure",
    "over feeding": "overfitting", "under feeding": "underfitting",
    "regularisation": "regularization", "normalisation": "normalization",
    "link list": "linked list", "link lists": "linked lists",
    "hash set": "HashSet", "tree map": "TreeMap", "array list": "ArrayList",
    "re curse ion": "recursion", "re curse": "recurse",
    "al go rhythm": "algorithm", "al go rithm": "algorithm",
}

# Pure thinking sounds that should not trigger processing
_FILLER_ONLY_RE = re.compile(
    r"^(?:uh+|um+|hmm+|ah+|err+|oh+|hm+|mm+|uh[ -]huh|yeah|yep|yup|"
    r"right|okay|ok|so|like|well|i see|got it|sure|alright|"
    r"let me see|let me think|i think|basically|actually)\s*[.,!?]?\s*$",
    re.IGNORECASE,
)

# Sentence-final punctuation: 2s after one of these → process (don't wait for UtteranceEnd)
_SENTENCE_END = frozenset(".?!")


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
    dg_finals = []

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
        except Exception as _e:
            print(f"[speak ERROR] {type(_e).__name__}: {_e}", flush=True)

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
    try:
        opening = await engine.get_opening()
    except Exception as _e:
        print(f"[get_opening ERROR] {type(_e).__name__}: {_e}", flush=True)
        await jt({"type": "error", "message": "Failed to start interview. Please refresh and try again."})
        return
    await jt({"type": "transcript", "role": "agent", "text": opening})
    speak_task = asyncio.create_task(speak(opening))
    await speak_task
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

        sentence_timer = None  # fires 2s after sentence-final punctuation

        async def _do_process():
            """Single entry point: process whatever is in dg_finals right now."""
            nonlocal processing, speak_task, recording_turn

            if processing or not recording_turn:
                dg_finals.clear()
                return

            raw_answer = " ".join(dg_finals).strip()
            dg_finals.clear()
            recording_turn = False

            if not raw_answer or len(raw_answer.split()) < 2:
                recording_turn = True
                return
            if _FILLER_ONLY_RE.match(raw_answer.strip()):
                recording_turn = True
                return

            if agent_speaking:
                await interrupt_agent()

            answer = _fix_transcript(raw_answer)
            processing = True
            await jt({"type": "processing"})
            await jt({"type": "transcript", "role": "user", "text": answer})

            try:
                result = await engine.process_answer(answer)
                response_text = result.get("response_text", "")
            except Exception as _e:
                print(f"[process_answer ERROR] {type(_e).__name__}: {_e}", flush=True)
                processing = False
                fallback = "Sorry, I didn't quite catch that — could you say that again?"
                await jt({"type": "transcript", "role": "agent", "text": fallback})
                speak_task = asyncio.create_task(speak(fallback))
                await speak_task
                return

            await jt({"type": "transcript", "role": "agent", "text": response_text})
            speak_task = asyncio.create_task(speak(response_text))
            try:
                await speak_task
            except asyncio.CancelledError:
                # speak was cancelled externally (e.g. barge-in) — reset cleanly
                agent_speaking = False
                recording_turn = True
                processing = False
                return
            processing = False

            if result.get("interview_complete"):
                engine.is_interview_done = True
                await jt({"type": "interview_complete"})
                done.set()
                return

            await jt({"type": "user_turn"})

        async def _sentence_fire():
            """Wait 2s after sentence-final punctuation, then process."""
            try:
                await asyncio.sleep(2.0)
                await _do_process()
            except asyncio.CancelledError:
                pass

        def _cancel_sentence_timer():
            nonlocal sentence_timer
            # Never cancel while _do_process is running — it would raise
            # CancelledError inside the task and leave processing=True stuck.
            if processing:
                return
            if sentence_timer and not sentence_timer.done():
                sentence_timer.cancel()
            sentence_timer = None

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

                # Candidate spoke while AI was talking → interrupt immediately
                if text and agent_speaking:
                    await interrupt_agent()
                    recording_turn = True
                    dg_finals.clear()
                    _cancel_sentence_timer()

                if is_final and text and recording_turn:
                    # Any new final segment → cancel previous sentence timer (still talking)
                    _cancel_sentence_timer()
                    dg_finals.append(text)
                    # Fast path: complete sentence → start 2s confirmation window
                    stripped = text.strip()
                    if stripped and stripped[-1] in _SENTENCE_END and not processing:
                        sentence_timer = asyncio.create_task(_sentence_fire())

                elif not is_final and text:
                    # Interim speech → they're still mid-sentence, cancel timer
                    _cancel_sentence_timer()
                    await jt({"type": "interim", "text": text})

            elif msg_type == "UtteranceEnd":
                # 5s silence fallback — but only act if not already processing.
                # Must check processing BEFORE cancelling: if sentence_timer is
                # mid-_do_process, cancelling it kills the task and leaves
                # processing=True stuck forever.
                if processing or not recording_turn:
                    dg_finals.clear()
                    continue

                _cancel_sentence_timer()
                await _do_process()

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
