FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libfreetype6 libjpeg62-turbo libopenjp2-7 \
    libgl1 libsm6 libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download InsightFace buffalo_sc model so cold starts are fast
RUN python -c "\
from insightface.app import FaceAnalysis; \
app = FaceAnalysis(name='buffalo_sc', root='/app/insightface', providers=['CPUExecutionProvider']); \
app.prepare(ctx_id=0, det_size=(320, 320)); \
print('InsightFace buffalo_sc ready')"

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
