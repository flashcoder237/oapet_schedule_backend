"""
Configuration Celery pour OAPET Schedule Backend

Ce module configure Celery pour gérer les tâches asynchrones,
notamment les prédictions ML et les mises à jour périodiques.
"""

import os
from celery import Celery
from celery.schedules import crontab

# Définir les settings Django par défaut
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oapet_schedule_backend.settings')

# Créer l'instance Celery
app = Celery('oapet_schedule_backend')

# Charger la configuration depuis Django settings
# Le préfixe 'CELERY' signifie que toutes les configs Celery
# doivent être préfixées avec CELERY_ dans settings.py
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-découverte des tâches depuis tous les apps installés
app.autodiscover_tasks()


# Tâches périodiques planifiées
app.conf.beat_schedule = {
    # Mise à jour quotidienne des prédictions ML pour tous les cours
    'update-ml-predictions-daily': {
        'task': 'ml_engine.tasks.update_all_course_predictions',
        'schedule': crontab(hour=2, minute=0),  # Chaque jour à 2h du matin
    },

    # Détection d'anomalies dans les schedules publiés
    'detect-schedule-anomalies-hourly': {
        'task': 'ml_engine.tasks.detect_anomalies_for_published_schedules',
        'schedule': crontab(minute=0),  # Chaque heure
    },

    # Nettoyage des anciennes prédictions (> 30 jours)
    'cleanup-old-predictions': {
        'task': 'ml_engine.tasks.cleanup_old_predictions',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Chaque dimanche à 3h
    },

    # Génération de rapports ML hebdomadaires
    'generate-ml-reports-weekly': {
        'task': 'ml_engine.tasks.generate_weekly_ml_report',
        'schedule': crontab(hour=6, minute=0, day_of_week=1),  # Chaque lundi à 6h
    },
}


@app.task(bind=True)
def debug_task(self):
    """Tâche de débogage pour tester Celery"""
    print(f'Request: {self.request!r}')
