from celery import Celery

from app.core.config import settings
from app.tasks.beat_schedule import beat_schedule

celery_app = Celery(
    "app",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.domains.notifications.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=False,
    beat_schedule=beat_schedule,
)
