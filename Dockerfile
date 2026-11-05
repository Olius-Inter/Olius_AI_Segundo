FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/olivia

WORKDIR /app

# libgomp atende bibliotecas numéricas como FAISS; certificados permitem HTTPS.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 olivia \
    && useradd --uid 10001 --gid olivia --create-home olivia

COPY requirements.txt security-constraints.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check

COPY --chown=olivia:olivia app/ ./app/
COPY --chown=olivia:olivia frontend/ ./frontend/

USER olivia
EXPOSE 8000

# Verifica a resposta da aplicação sem executar chat ou consumir cota de LLM.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import json, urllib.request; r = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3); assert json.load(r).get('status') == 'ok'"]

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
