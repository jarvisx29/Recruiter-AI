import asyncio
import base64
import threading
import concurrent.futures

import cv2
import numpy as np
from insightface.app import FaceAnalysis

_INSIGHTFACE_ROOT = '/app/insightface'

_app = None
_app_lock = threading.Lock()
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


def _get_app() -> FaceAnalysis:
    global _app
    if _app is None:
        with _app_lock:
            if _app is None:
                a = FaceAnalysis(
                    name='buffalo_sc',
                    root=_INSIGHTFACE_ROOT,
                    providers=['CPUExecutionProvider'],
                )
                a.prepare(ctx_id=0, det_size=(320, 320))
                _app = a
    return _app


def _decode_image(image_b64: str) -> np.ndarray | None:
    if ',' in image_b64:
        image_b64 = image_b64.split(',', 1)[1]
    try:
        raw = base64.b64decode(image_b64)
        arr = np.frombuffer(raw, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _get_embedding_sync(image_b64: str) -> tuple[list | None, str | None]:
    app = _get_app()
    img = _decode_image(image_b64)
    if img is None:
        return None, 'decode_failed'
    faces = app.get(img)
    if not faces:
        return None, 'no_face'
    # largest face = main subject
    faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
    return faces[0].normed_embedding.tolist(), None


async def get_embedding(image_b64: str) -> tuple[list | None, str | None]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _get_embedding_sync, image_b64)


def compare_embeddings(e1: list, e2: list, threshold: float = 0.25) -> dict:
    a = np.array(e1, dtype=np.float32)
    b = np.array(e2, dtype=np.float32)
    similarity = float(np.dot(a, b))  # embeddings are L2-normalised
    return {'matched': similarity >= threshold, 'similarity': round(similarity, 3)}


async def preload() -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_executor, _get_app)
