"""
OAPET Schedule Backend - Initialisation du package

Ce module charge l'application Celery au d�marrage de Django
pour garantir que les t�ches asynchrones sont disponibles.
"""

# Ceci va assurer que l'app Celery est toujours import�e
# quand Django d�marre afin que @shared_task utilise l'app correctement
from .celery import app as celery_app

__all__ = ('celery_app',)
