"""Celery application + periodic schedule.

On Windows run the worker with ``--pool=solo`` (see docs/INSTALL.md). Redis is
used as broker and result backend.
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "saas_manager",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=60 * 60 * 24 * 7,
    task_routes={
        "app.workers.tasks.run_update_job": {"queue": "updates"},
        "app.workers.tasks.run_update_run": {"queue": "updates"},
        "app.workers.tasks.backup_tenant": {"queue": "backups"},
        "app.workers.tasks.provision_tenant": {"queue": "default"},
    },
)

if settings.scheduler_enabled:
    celery_app.conf.beat_schedule = {
        # Refresh usage counters every hour.
        "refresh-usage": {
            "task": "app.workers.tasks.refresh_all_usage",
            "schedule": crontab(minute=5),
        },
        # Daily billing sweep: overdue invoices, dunning, suspensions, expiries.
        "daily-billing": {
            "task": "app.workers.tasks.daily_billing_sweep",
            "schedule": crontab(hour=2, minute=0),
        },
        # Generate invoices whose next_invoice_date is due.
        "generate-invoices": {
            "task": "app.workers.tasks.generate_due_invoices",
            "schedule": crontab(hour=3, minute=0),
        },
    }
