from workers.celery_app import celery_app


@celery_app.task(name="workers.health_tasks.ping")
def ping() -> dict[str, str]:
    return {"status": "ok", "worker": "insightops-worker"}
