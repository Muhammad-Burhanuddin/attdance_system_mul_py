from celery import Celery
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "attandance_app_mul.settings.dev")

app = Celery("attandance_app_mul")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Celery Beat schedule
from celery.schedules import crontab
app.conf.beat_schedule = {
    'fetch-attendance-every-5-minutes': {
        'task': 'yourapp.tasks.fetch_attendance',
        'schedule': crontab(minute='*/1')
    },
}
