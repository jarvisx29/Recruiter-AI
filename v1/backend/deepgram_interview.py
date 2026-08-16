"""
Voice interview session — explicit state machine replaces flag soup.

States
------
IDLE        : before session starts
LISTENING   : collecting user speech (VAD active)
PROCESSING  : LLM call in flight
SPEAKING    : TTS audio streaming to browser
INTERRUPTED : agent was cut off; next user turn plays recovery
DONE        : interview complete
"""
import asyncio
import json
import os
import re
import urllib.request
from enum import Enum, auto

import httpx
import numpy as np
import onnxruntime as ort
import websockets
from fastapi import WebSocket

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

TTS_SAMPLE_RATE = 24_000
TTS_URL = (
    "https://api.deepgram.com/v1/speak"
    "?model=aura-athena-en"
    "&encoding=linear16"
    f"&sample_rate={TTS_SAMPLE_RATE}"
    "&container=none"
)
DEEPGRAM_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?model=nova-3"
    "&language=en"
    "&encoding=linear16"
    "&sample_rate=16000"
    "&channels=1"
    "&endpointing=300"
    "&interim_results=true"
    "&utterance_end_ms=5000"
    "&smart_format=true"
)

# ── Silero VAD ────────────────────────────────────────────────────────────────

_VAD_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "silero_vad.onnx")
_VAD_MODEL_URL  = (
    "https://raw.githubusercontent.com/snakers4/silero-vad/"
    "master/src/silero_vad/data/silero_vad.onnx"
)
_vad_ort_session = None
_vad_model_ver   = 4  # detected at load time: 4 = h/c inputs, 5 = state input


def _load_vad():
    global _vad_ort_session, _vad_model_ver
    if _vad_ort_session is not None:
        return _vad_ort_session
    try:
        if not os.path.exists(_VAD_MODEL_PATH):
            print("[VAD] Downloading Silero VAD model …", flush=True)
            urllib.request.urlretrieve(_VAD_MODEL_URL, _VAD_MODEL_PATH)
        sess = ort.InferenceSession(_VAD_MODEL_PATH, providers=["CPUExecutionProvider"])
        inp_names = {i.name for i in sess.get_inputs()}
        _vad_model_ver = 5 if "state" in inp_names else 4
        _vad_ort_session = sess
        print(f"[VAD] Silero VAD v{_vad_model_ver} loaded (inputs: {inp_names}).", flush=True)
    except Exception as e:
        print(f"[VAD] Unavailable ({e}) — sentence-timer fallback active.", flush=True)
    return _vad_ort_session


class SileroVAD:
    _SPEECH_THRESH   = 0.5
    _SPEECH_CONFIRM  = 3    # ≥3 consecutive frames (~96 ms)  → speech started
    _SILENCE_CONFIRM = 10   # ≥10 consecutive frames (~320 ms) → speech ended
    _CHUNK           = 1024  # 512 samples × 2 bytes (32 ms @ 16 kHz)

    def __init__(self):
        self._sess   = _load_vad()
        self._buf    = b""
        # v4 state tensors
        self._h      = np.zeros((2, 1, 64),  dtype=np.float32)
        self._c      = np.zeros((2, 1, 64),  dtype=np.float32)
        # v5 state tensor
        self._state  = np.zeros((2, 1, 128), dtype=np.float32)
        self._sf     = 0
        self._lf     = 0
        self._active = False

    def reset(self):
        self._buf    = b""
        self._h      = np.zeros((2, 1, 64),  dtype=np.float32)
        self._c      = np.zeros((2, 1, 64),  dtype=np.float32)
        self._state  = np.zeros((2, 1, 128), dtype=np.float32)
        self._sf = self._lf = 0
        self._active = False

    def feed(self, raw: bytes) -> list:
        if self._sess is None:
            return []
        events = []
        self._buf += raw
        while len(self._buf) >= self._CHUNK:
            chunk, self._buf = self._buf[:self._CHUNK], self._buf[self._CHUNK:]
            ev = self._infer(chunk)
            if ev:
                events.append(ev)
        return events

    def _infer(self, chunk: bytes):
        x = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
        if _vad_model_ver == 5:
            outs = self._sess.run(
                None,
                {"input": x[np.newaxis, :],
                 "sr":    np.array(16000, dtype=np.int64),
                 "state": self._state},
            )
            p = float(outs[0].flatten()[0])
            self._state = outs[1]
        else:
            outs = self._sess.run(
                None,
                {"input": x[np.newaxis, :],
                 "sr":    np.array(16000, dtype=np.int64),
                 "h":     self._h,
                 "c":     self._c},
            )
            p = float(outs[0].flatten()[0])
            self._h = outs[1]
            self._c = outs[2]

        if p >= self._SPEECH_THRESH:
            self._lf = 0
            self._sf += 1
            if not self._active and self._sf >= self._SPEECH_CONFIRM:
                self._active = True
                return "speech_start"
        else:
            self._sf = 0
            if self._active:
                self._lf += 1
                if self._lf >= self._SILENCE_CONFIRM:
                    self._active = False
                    self._lf = 0
                    return "speech_end"
        return None


_load_vad()  # pre-load at startup

# ── transcript corrections ────────────────────────────────────────────────────

_TERM_FIXES = {
    "keketlone": "scikit-learn", "kik it": "scikit-learn",
    "kick it learn": "scikit-learn", "kicket learn": "scikit-learn",
    "skit learn": "scikit-learn", "sk learn": "scikit-learn",
    "psychic learn": "scikit-learn", "kick it along": "scikit-learn",
    "kik it along": "scikit-learn", "slice it learn": "scikit-learn",
    "slice, it learn": "scikit-learn", "scikit learn": "scikit-learn",
    "secret line": "scikit-learn", "secret learn": "scikit-learn",
    "secret lean": "scikit-learn", "cicket learn": "scikit-learn",
    "lead code": "LeetCode", "leet code": "LeetCode",
    "lite code": "LeetCode", "lead code sums": "LeetCode problems",
    "ashma": "hashmap", "ash ma": "hashmap", "ash map": "hashmap",
    "hash mob": "hashmap", "hash mop": "hashmap", "has map": "hashmap",
    "greed ai": "GraphQL", "greed ql": "GraphQL", "graph ql": "GraphQL",
    "graph q l": "GraphQL", "graph cue l": "GraphQL",
    "scama": "schema", "skim a": "schema", "skim ah": "schema",
    "skema": "schema", "shema": "schema",
    "colis": "policies", "collis": "policies",
    "cube ernetes": "Kubernetes", "cube nettles": "Kubernetes",
    "q bernetes": "Kubernetes", "kubernetes": "Kubernetes",
    "cube rnetes": "Kubernetes",
    "doc ker": "Docker", "doc care": "Docker",
    "dev ops": "DevOps", "deaf ops": "DevOps",
    "c i c d": "CI/CD", "si si di": "CI/CD",
    "micro services": "microservices", "micro service": "microservice",
    "post gres": "PostgreSQL", "post gray sql": "PostgreSQL",
    "postgres ql": "PostgreSQL", "post grease ql": "PostgreSQL",
    "mongo db": "MongoDB", "mango db": "MongoDB",
    "rest a p i": "REST API", "restapi": "REST API",
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

_FILLER_ONLY_RE = re.compile(
    r"^(?:uh+|um+|hmm+|ah+|err+|oh+|hm+|mm+|uh[ -]huh|yeah|yep|yup|"
    r"right|okay|ok|so|like|well|i see|got it|sure|alright|"
    r"let me see|let me think|i think|basically|actually)\s*[.,!?]?\s*$",
    re.IGNORECASE,
)


def _fix_transcript(text: str) -> str:
    lower = text.lower()
    for wrong, right in _TERM_FIXES.items():
        if wrong in lower:
            lower = lower.replace(wrong, right)
    lower = re.sub(r'\b(\w+)(?:[,\s]+\1){2,}', r'\1', lower)
    if text and text[0].isupper() and lower:
        lower = lower[0].upper() + lower[1:]
    return lower


# ── state machine ─────────────────────────────────────────────────────────────

class S(Enum):
    IDLE        = auto()
    LISTENING   = auto()
    PROCESSING  = auto()
    SPEAKING    = auto()
    INTERRUPTED = auto()
    DONE        = auto()


# ── session ───────────────────────────────────────────────────────────────────

async def run_session(browser_ws: WebSocket, engine) -> None:
    if not DEEPGRAM_API_KEY:
        await browser_ws.send_json({"type": "error", "message": "DEEPGRAM_API_KEY not set."})
        return

    state          = S.IDLE
    done           = asyncio.Event()
    current_task   = None   # the one active speak-or-process asyncio.Task
    sentence_timer = None   # VAD-gated debounce timer → fires _do_process
    dg_finals      = []     # accumulated Deepgram final transcripts for current turn
    audio_queue: asyncio.Queue = asyncio.Queue()
    vad            = SileroVAD()
    vad_done       = [False]  # mutable flag: VAD confirmed end-of-speech

    async def jt(data: dict):
        await browser_ws.send_json(data)

    # ── TTS ───────────────────────────────────────────────────────────────────

    async def _do_speak(text: str) -> None:
        """Stream TTS to browser. Transitions state SPEAKING → LISTENING on clean exit."""
        nonlocal state
        state = S.SPEAKING
        dg_finals.clear()
        vad.reset()
        vad_done[0] = False

        try:
            await jt({"type": "agent_start_talking"})
            await jt({"type": "audio_start", "sampleRate": TTS_SAMPLE_RATE})
            async with httpx.AsyncClient(timeout=30) as http:
                async with http.stream(
                    "POST", TTS_URL,
                    headers={
                        "Authorization": f"Token {DEEPGRAM_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={"text": text},
                ) as resp:
                    async for chunk in resp.aiter_bytes(4096):
                        await browser_ws.send_bytes(chunk)
            await jt({"type": "audio_end"})
            await jt({"type": "agent_stop_talking"})
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[TTS ERROR] {type(e).__name__}: {e}", flush=True)
        finally:
            dg_finals.clear()
            vad.reset()
            vad_done[0] = False
            # Only advance to LISTENING if nobody set INTERRUPTED while we were speaking
            if state == S.SPEAKING:
                state = S.LISTENING

    # ── interrupt ─────────────────────────────────────────────────────────────

    async def _interrupt() -> None:
        """Cancel the running task, clear audio. State → INTERRUPTED."""
        nonlocal current_task, state
        state = S.INTERRUPTED
        dg_finals.clear()
        if current_task and not current_task.done():
            current_task.cancel()
            try:
                await current_task
            except (asyncio.CancelledError, Exception):
                pass
        await jt({"type": "clear_audio"})

    # ── sentence timer ────────────────────────────────────────────────────────

    def _cancel_sentence_timer():
        nonlocal sentence_timer
        if sentence_timer and not sentence_timer.done():
            sentence_timer.cancel()
        sentence_timer = None

    async def _sentence_fire():
        """50 ms debounce + VAD gate (max 1.5 s wait), then fire _do_process."""
        nonlocal current_task
        try:
            for _ in range(30):        # 30 × 50 ms = 1.5 s ceiling
                await asyncio.sleep(0.05)
                if vad_done[0]:
                    break
            if state in (S.LISTENING, S.INTERRUPTED) and dg_finals:
                if not (current_task and not current_task.done()):
                    current_task = asyncio.create_task(_do_process())
        except asyncio.CancelledError:
            pass

    # ── main processing ───────────────────────────────────────────────────────

    async def _do_process() -> None:
        nonlocal state

        raw = " ".join(dg_finals).strip()
        dg_finals.clear()

        # ── barge-in recovery ─────────────────────────────────────────────────
        if state == S.INTERRUPTED:
            last_agent = next(
                (m["content"] for m in reversed(engine.conversation_history)
                 if m.get("role") == "assistant"),
                None,
            )
            if last_agent:
                parts = re.split(r"(?<=[.!?])\s+", last_agent.strip())
                qs    = [p for p in parts if p.rstrip().endswith("?")]
                q     = qs[-1] if qs else (parts[-1] if parts else last_agent)
                recovery = (
                    f"Sorry about that! Did you catch my question? I asked: {q}"
                    if len(q) <= 120
                    else "Sorry about that! Did you catch my question? Let me know and I'll repeat it."
                )
            else:
                recovery = "Sorry about that! Did you catch my question? Take your time."

            await jt({"type": "transcript", "role": "agent", "text": recovery})
            await _do_speak(recovery)
            if state == S.LISTENING:          # completed without re-interrupt
                await jt({"type": "user_turn"})
            return

        # ── filter trivial input ──────────────────────────────────────────────
        if not raw or len(raw.split()) < 2:
            state = S.LISTENING
            return
        if _FILLER_ONLY_RE.match(raw.strip()):
            state = S.LISTENING
            return

        # ── LLM → TTS ────────────────────────────────────────────────────────
        state  = S.PROCESSING
        answer = _fix_transcript(raw)
        await jt({"type": "processing"})
        await jt({"type": "transcript", "role": "user", "text": answer})

        result = {}
        try:
            result       = await engine.process_answer(answer)
            response_text = result.get("response_text", "")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[process_answer ERROR] {type(e).__name__}: {e}", flush=True)
            response_text = "Sorry, I didn't quite catch that — could you say that again?"

        await jt({"type": "transcript", "role": "agent", "text": response_text})
        await _do_speak(response_text)

        if state == S.LISTENING:              # completed without interruption
            if result.get("interview_complete"):
                engine.is_interview_done = True
                await jt({"type": "interview_complete"})
                done.set()
                state = S.DONE
                return
            await jt({"type": "user_turn"})

    # ── opening ───────────────────────────────────────────────────────────────

    try:
        opening = await engine.get_opening()
    except Exception as e:
        print(f"[get_opening ERROR] {type(e).__name__}: {e}", flush=True)
        await jt({"type": "error", "message": "Failed to start interview. Please refresh."})
        return

    await jt({"type": "transcript", "role": "agent", "text": opening})
    await _do_speak(opening)          # direct await — Deepgram not connected yet
    # _do_speak finally: state → LISTENING
    await jt({"type": "user_turn"})

    # ── WebSocket worker tasks ────────────────────────────────────────────────

    async def receive_from_browser():
        try:
            while not done.is_set():
                msg = await browser_ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    done.set()
                    break
                raw = msg.get("bytes")
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
            # Feed VAD while listening or after a barge-in (to detect when user finishes)
            if state in (S.LISTENING, S.INTERRUPTED):
                try:
                    for ev in vad.feed(chunk):
                        if ev == "speech_end":
                            vad_done[0] = True
                            print("[VAD] speech_end", flush=True)
                        elif ev == "speech_start":
                            vad_done[0] = False
                except Exception as e:
                    print(f"[VAD] disabled after error: {e}", flush=True)
                    vad._sess = None
            try:
                await dg_ws.send(chunk)
            except Exception:
                break

    async def handle_deepgram(dg_ws):
        nonlocal current_task, sentence_timer
        async for raw in dg_ws:
            if done.is_set():
                break
            if not isinstance(raw, str):
                continue
            data     = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "Results":
                alts     = data.get("channel", {}).get("alternatives", [{}])
                text     = alts[0].get("transcript", "")
                is_final = data.get("is_final", False)

                # Barge-in: any speech while agent is speaking or LLM is running
                if text and state in (S.SPEAKING, S.PROCESSING):
                    _cancel_sentence_timer()
                    await _interrupt()
                    # text that triggered barge-in falls through to final handler below

                # Interim: user is still mid-sentence → cancel timer, show preview
                if not is_final and text and state in (S.LISTENING, S.INTERRUPTED):
                    _cancel_sentence_timer()
                    await jt({"type": "interim", "text": text})

                # Final: accumulate and arm the process timer
                if is_final and text and state in (S.LISTENING, S.INTERRUPTED):
                    _cancel_sentence_timer()
                    dg_finals.append(text)
                    if not (current_task and not current_task.done()):
                        sentence_timer = asyncio.create_task(_sentence_fire())

            elif msg_type == "UtteranceEnd":
                # 5 s silence fallback — only if there is something to process
                if state not in (S.LISTENING, S.INTERRUPTED) or not dg_finals:
                    continue
                _cancel_sentence_timer()
                if not (current_task and not current_task.done()):
                    current_task = asyncio.create_task(_do_process())

    # ── connect Deepgram and run ──────────────────────────────────────────────

    dg_headers = [("Authorization", f"Token {DEEPGRAM_API_KEY}")]
    try:
        async with websockets.connect(DEEPGRAM_URL, extra_headers=dg_headers) as dg_ws:
            tasks = [
                asyncio.create_task(receive_from_browser()),
                asyncio.create_task(forward_to_deepgram(dg_ws)),
                asyncio.create_task(handle_deepgram(dg_ws)),
            ]
            # Drain: audio queued during opening flows to Deepgram; ignore any finals.
            await asyncio.sleep(0.5)
            _cancel_sentence_timer()
            dg_finals.clear()

            try:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                done.set()
                if current_task and not current_task.done():
                    current_task.cancel()
                _cancel_sentence_timer()
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    except Exception as e:
        await jt({"type": "error", "message": str(e)})
