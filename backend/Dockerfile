FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app app

COPY --chown=app:app alembic.ini ./alembic.ini
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app app ./app
RUN mkdir -p /app/data/documents && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["sh", "-c", "python -m alembic upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
