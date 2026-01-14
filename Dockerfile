FROM python:3.11-slim

WORKDIR /app

# 一次性完成所有安装和清理
RUN set -ex && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        curl \
        libgomp1 && \
    pip install --no-cache-dir \
        git+https://github.com/myshell-ai/MeloTTS.git \
        fastapi \
        uvicorn[standard] && \
    python -m unidic download && \
    pip cache purge && \
    apt-get purge -y --auto-remove git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY server.py /app/server.py

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
