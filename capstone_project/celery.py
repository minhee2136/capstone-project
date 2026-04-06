import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'capstone_project.settings')

app = Celery('capstone_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
