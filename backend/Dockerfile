# Matches CI (python-version 3.10). Build context is the backend/ directory.
FROM python:3.10-slim

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

ENTRYPOINT ["/app/entrypoint.sh"]
