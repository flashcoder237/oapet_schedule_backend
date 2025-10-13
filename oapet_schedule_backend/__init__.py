"""
OAPET Schedule Backend - Initialisation du package

Ce module charge l'application Celery au démarrage de Django
pour garantir que les tâches asynchrones sont disponibles.
"""

# Ceci va assurer que l'app Celery est toujours importée
# quand Django démarre afin que @shared_task utilise l'app correctement
from .celery import app as celery_app

__all__ = ('celery_app',)
