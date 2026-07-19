from celery import Celery

from apps.api.app.core.config import settings

celery_app = Celery(
    "insightops",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["workers.health_tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
