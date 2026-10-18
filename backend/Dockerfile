FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
# Instala só as dependências primeiro para aproveitar o cache de camadas.
RUN mkdir app && touch app/__init__.py && pip install . && pip uninstall -y logistics-ops-api && rm -rf app

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

RUN useradd --system --no-create-home appuser
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

# --proxy-headers: o IP real do cliente vem do nginx (rate limit). A porta 8000 não deve
# ser exposta publicamente; o compose a publica apenas em 127.0.0.1.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
