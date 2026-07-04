# HelixForge AI backend — FastAPI + scientific tools.
# RDKit and PyTDC install from pip wheels on this base. `curl` is included
# because the HTTP client falls back to curl when a CDN/WAF blocks httpx's TLS
# fingerprint (see app/services/httpclient.py).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HELIXFORGE_DATA_DIR=/data

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential libxrender1 libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
COPY fixtures ./fixtures

RUN mkdir -p /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
