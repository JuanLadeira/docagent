"""
Fase 23 — Celery application.

Broker: Redis DB 1 (separado do DB 0 usado pelo rate limiter / session).
Backend: Redis DB 2 (result backend).

Uso:
    celery -A docagent.celery_app worker --loglevel=info
    celery -A docagent.celery_app beat --loglevel=info
"""
import os

from celery import Celery

_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
# Normaliza URL sem db suffix e força DB 1 para broker, DB 2 para backend.
_base = _redis_url.rstrip("/").rsplit("/", 1)[0]

celery = Celery(
    "docagent",
    broker=f"{_base}/1",
    backend=f"{_base}/2",
    include=["docagent.tasks.ingestao"],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # requeue on worker crash
    worker_prefetch_multiplier=1,  # fairness: 1 task por worker de cada vez
)
