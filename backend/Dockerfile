# Keep in sync with the Python version in .github/workflows/ci.yml. Build context is backend/.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Hugging Face Spaces runs containers as uid 1000.
RUN useradd --uid 1000 --create-home app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .
# Git on Windows does not preserve the executable bit, so set it explicitly.
RUN chmod 0755 /app/entrypoint.sh

USER app
ENV HOME=/home/app

EXPOSE 7860

# Restarts the container if the API stops answering. Readiness (DB/Redis) is at /health/ready.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7860/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/app/entrypoint.sh"]
