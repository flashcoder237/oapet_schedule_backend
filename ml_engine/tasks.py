#!/usr/bin/env python3
"""
Tâches asynchrones Celery pour OAPET ML Engine
==============================================

Gestion des tâches longues d'optimisation, d'entraînement ML et de prédictions
en arrière-plan avec Celery et Redis.
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from celery import shared_task, current_task
from celery.exceptions import Retry
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache

from .models import (
    ModelTrainingTask, MLModel, PredictionRequest, 
    TimetableDataset
)
from .services import (
    TimetableDataProcessor, FeatureExtractor, TimetableMLService,
    TimetablePredictor, MLTrainingService
)
from .algorithms import (
    TimetableOptimizer, ConflictPredictor, 
    GeneticAlgorithm, SimulatedAnnealing
)
from schedules.models import Schedule, ScheduleSession, ScheduleOptimization

logger = logging.getLogger('ml_engine.tasks')


class TaskProgress:
    """Helper pour gérer le progrès des tâches"""
    
    def __init__(self, task_id: str, total_steps: int = 100):
        self.task_id = task_id
        self.total_steps = total_steps
        self.current_step = 0
        self.messages = []
    
    def update(self, step: int, message: str = ""):
        """Met à jour le progrès"""
        self.current_step = step
        if message:
            self.messages.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
        progress = min((step / self.total_steps) * 100, 100)
        
        if current_task:
            current_task.update_state(
                state='PROGRESS',
                meta={
                    'current': step,
                    'total': self.total_steps,
                    'progress': progress,
                    'message': message,
                    'messages': self.messages[-10:]  # Garder les 10 derniers messages
                }
            )
        
        # Sauver aussi en cache pour l'accès rapide
        cache.set(f"task_progress_{self.task_id}", {
            'progress': progress,
            'message': message,
            'messages': self.messages[-10:]
        }, timeout=3600)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def train_ml_models_async(self, dataset_id: int, model_types: List[str], 
                         parameters: Dict[str, Any], user_id: int) -> Dict[str, Any]:
    """Tâche asynchrone pour l'entraînement des modèles ML"""
    
    task_progress = TaskProgress(self.request.id, total_steps=100)
    
    try:
        # Récupérer la tâche d'entraînement
        training_task = ModelTrainingTask.objects.get(
            dataset_id=dataset_id,
            created_by_id=user_id,
            status='queued'
        )
        
        task_progress.update(5, "Initialisation de l'entraînement...")
        
        # Marquer comme en cours
        training_task.status = 'running'
        training_task.started_at = timezone.now()
        training_task.save()
        
        # Récupérer le dataset
        dataset = TimetableDataset.objects.get(id=dataset_id)
        task_progress.update(10, f"Dataset {dataset.name} chargé")
        
        # Initialiser les services
        processor = TimetableDataProcessor()
        extractor = FeatureExtractor()
        ml_service = TimetableMLService()
        
        task_progress.update(15, "Services ML initialisés")
        
        # Télécharger les datasets si nécessaires
        if not dataset.file_path or not dataset.file_path.path:
            task_progress.update(20, "Téléchargement des datasets ITC...")
            files = processor.download_datasets()
            task_progress.update(35, f"{len(files)} datasets téléchargés")
        else:
            files = [dataset.file_path.path]
            task_progress.update(35, "Utilisation du dataset existant")
        
        # Extraction des features
        task_progress.update(40, "Extraction des features...")
        df = extractor.extract_features(files)
        
        if df.empty:
            raise ValueError("Aucune feature extraite des datasets")
        
        task_progress.update(55, f"Features extraites: {len(df)} cours, {len(df.columns)} features")
        
        # Préparation des données
        ml_service.create_models()
        X, y = ml_service.prepare_data(df)
        task_progress.update(65, "Données préparées pour l'entraînement")
        
        # Entraînement des modèles
        def training_progress_callback(progress, message):
            current_progress = 65 + (progress * 0.25)  # 65% à 90%
            task_progress.update(int(current_progress), message)
        
        task_progress.update(70, "Démarrage de l'entraînement...")
        best_name, results = ml_service.train_models(X, y, training_task)
        
        task_progress.update(90, f"Meilleur modèle: {best_name}")
        
        # Sauvegarde du modèle
        model_name = f"{dataset.name}_{best_name.replace(' ', '_')}_{int(time.time())}"
        ml_model = ml_service.save_model(model_name)
        
        task_progress.update(95, "Modèle sauvegardé")
        
        # Mise à jour de la tâche
        training_task.status = 'completed'
        training_task.completed_at = timezone.now()
        training_task.results.update({
            'best_model': best_name,
            'model_id': ml_model.id,
            'performance': {name: {k: v for k, v in res.items() if k != 'model'} 
                          for name, res in results.items()}
        })
        training_task.save()
        
        task_progress.update(100, "Entraînement terminé avec succès!")
        
        logger.info(f"Entraînement terminé pour dataset {dataset_id}, modèle {ml_model.id}")
        
        return {
            'success': True,
            'model_id': ml_model.id,
            'model_name': ml_model.name,
            'best_algorithm': best_name,
            'performance': results[best_name]
        }
        
    except Exception as e:
        logger.error(f"Erreur entraînement ML: {str(e)}")
        
        # Marquer la tâche comme échouée
        try:
            training_task.status = 'failed'
            training_task.logs += f"\nErreur: {str(e)}"
            training_task.save()
        except:
            pass
        
        task_progress.update(0, f"Erreur: {str(e)}")
        
        # Retry si c'est une erreur temporaire
        if isinstance(e, (ConnectionError, TimeoutError)):
            raise self.retry(exc=e, countdown=60, max_retries=3)
        
        raise e


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def optimize_schedule_async(self, schedule_id: int, algorithm: str = 'genetic',
                           algorithm_params: Dict[str, Any] = None,
                           user_id: Optional[int] = None) -> Dict[str, Any]:
    """Tâche asynchrone pour l'optimisation d'emplois du temps"""
    
    task_progress = TaskProgress(self.request.id, total_steps=100)
    
    try:
        # Récupérer l'emploi du temps
        schedule = Schedule.objects.get(id=schedule_id)
        task_progress.update(5, f"Emploi du temps {schedule.name} chargé")
        
        # Créer l'enregistrement d'optimisation
        optimization_record = ScheduleOptimization.objects.create(
            schedule=schedule,
            optimization_type='automatic',
            algorithm_used=algorithm,
            optimization_parameters=algorithm_params or {},
            started_by_id=user_id,
            started_at=timezone.now()
        )
        
        task_progress.update(10, "Enregistrement d'optimisation créé")
        
        # Compter les conflits avant optimisation
        conflicts_before = schedule.sessions.filter(
            id__in=[c.schedule_session_id for c in schedule.sessions.all()]
        ).count()
        
        optimization_record.conflicts_before = conflicts_before
        optimization_record.save()
        
        task_progress.update(15, f"Conflits détectés avant optimisation: {conflicts_before}")
        
        # Initialiser l'optimiseur
        optimizer = TimetableOptimizer()
        
        def optimization_progress_callback(progress, message):
            current_progress = 15 + (progress * 0.7)  # 15% à 85%
            task_progress.update(int(current_progress), message)
        
        task_progress.update(20, f"Démarrage optimisation {algorithm}...")
        
        # Lancer l'optimisation
        result = optimizer.optimize_schedule(
            schedule=schedule,
            algorithm=algorithm,
            algorithm_params=algorithm_params or {},
            progress_callback=optimization_progress_callback
        )
        
        if result['success']:
            task_progress.update(85, "Optimisation terminée, application des résultats...")
            
            # Recalculer les conflits après optimisation
            conflicts_after = len([s for s in schedule.sessions.all() 
                                 if s.get_conflicts().exists()])
            
            # Mettre à jour l'enregistrement
            optimization_record.conflicts_after = conflicts_after
            optimization_record.optimization_score = result['fitness']
            optimization_record.efficiency_metrics = {
                'conflicts_reduced': conflicts_before - conflicts_after,
                'improvement_percentage': ((conflicts_before - conflicts_after) / max(conflicts_before, 1)) * 100,
                'objectives': result['objectives'],
                'assignments_changed': result['assignments_changed']
            }
            optimization_record.convergence_achieved = True
            optimization_record.completed_at = timezone.now()
            optimization_record.save()
            
            task_progress.update(95, f"Conflits réduits: {conflicts_before} → {conflicts_after}")
            
            # Recalculer les métriques du schedule
            schedule.calculate_metrics()
            
            task_progress.update(100, "Optimisation terminée avec succès!")
            
            logger.info(f"Optimisation terminée pour schedule {schedule_id}")
            
            return {
                'success': True,
                'schedule_id': schedule_id,
                'algorithm': algorithm,
                'conflicts_before': conflicts_before,
                'conflicts_after': conflicts_after,
                'fitness_score': result['fitness'],
                'objectives': result['objectives'],
                'optimization_id': optimization_record.id
            }
        else:
            raise Exception(result.get('error', 'Erreur inconnue lors de l\'optimisation'))
            
    except Exception as e:
        logger.error(f"Erreur optimisation schedule {schedule_id}: {str(e)}")
        
        # Marquer l'optimisation comme échouée
        try:
            optimization_record.logs += f"\nErreur: {str(e)}"
            optimization_record.save()
        except:
            pass
        
        task_progress.update(0, f"Erreur: {str(e)}")
        
        # Retry pour certaines erreurs
        if "database" in str(e).lower() or "connection" in str(e).lower():
            raise self.retry(exc=e, countdown=30, max_retries=2)
        
        raise e


@shared_task(bind=True)
def predict_conflicts_async(self, schedule_id: int) -> Dict[str, Any]:
    """Tâche asynchrone pour la prédiction des conflits"""
    
    task_progress = TaskProgress(self.request.id, total_steps=100)
    
    try:
        # Récupérer l'emploi du temps
        schedule = Schedule.objects.get(id=schedule_id)
        task_progress.update(10, f"Analyse de {schedule.name}")
        
        # Initialiser le prédicteur
        predictor = ConflictPredictor()
        task_progress.update(20, "Prédicteur initialisé")
        
        # Prédire les conflits
        task_progress.update(30, "Analyse des risques de conflits...")
        predicted_conflicts = predictor.predict_conflicts(schedule)
        
        task_progress.update(80, f"{len(predicted_conflicts)} conflits potentiels détectés")
        
        # Sauvegarder les résultats en cache
        cache_key = f"predicted_conflicts_{schedule_id}"
        cache.set(cache_key, {
            'conflicts': predicted_conflicts,
            'generated_at': timezone.now().isoformat(),
            'schedule_name': schedule.name
        }, timeout=3600)  # 1 heure
        
        task_progress.update(100, "Prédiction terminée")
        
        return {
            'success': True,
            'schedule_id': schedule_id,
            'conflicts_count': len(predicted_conflicts),
            'high_risk_conflicts': len([c for c in predicted_conflicts if c['risk_score'] > 0.8]),
            'cache_key': cache_key
        }
        
    except Exception as e:
        logger.error(f"Erreur prédiction conflits: {str(e)}")
        task_progress.update(0, f"Erreur: {str(e)}")
        raise e


@shared_task(bind=True)
def batch_predictions_async(self, course_data_list: List[Dict[str, Any]], 
                           user_id: int) -> Dict[str, Any]:
    """Tâche asynchrone pour les prédictions en lot"""
    
    task_progress = TaskProgress(self.request.id, total_steps=len(course_data_list))
    
    try:
        # Récupérer le modèle actif
        active_model = MLModel.objects.filter(is_active=True).first()
        if not active_model:
            raise ValueError("Aucun modèle ML actif disponible")
        
        predictor = TimetablePredictor(active_model)
        results = []
        
        for i, course_data in enumerate(course_data_list):
            task_progress.update(i + 1, f"Prédiction {i + 1}/{len(course_data_list)}")
            
            # Effectuer la prédiction
            prediction = predictor.predict_difficulty(course_data, user_id=user_id)
            results.append({
                'course_name': course_data.get('course_name', f'Cours {i + 1}'),
                'prediction': prediction
            })
        
        task_progress.update(len(course_data_list), "Toutes les prédictions terminées")
        
        return {
            'success': True,
            'predictions_count': len(results),
            'results': results,
            'model_used': active_model.name
        }
        
    except Exception as e:
        logger.error(f"Erreur prédictions en lot: {str(e)}")
        task_progress.update(0, f"Erreur: {str(e)}")
        raise e


@shared_task
def cleanup_old_tasks():
    """Tâche de nettoyage des anciennes tâches et données"""
    try:
        # Nettoyer les tâches d'entraînement anciennes (> 30 jours)
        cutoff_date = timezone.now() - timedelta(days=30)
        
        old_training_tasks = ModelTrainingTask.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['completed', 'failed']
        )
        
        deleted_count = old_training_tasks.count()
        old_training_tasks.delete()
        
        # Nettoyer les requêtes de prédiction anciennes (> 7 jours)
        old_prediction_requests = PredictionRequest.objects.filter(
            created_at__lt=timezone.now() - timedelta(days=7)
        )
        
        deleted_predictions = old_prediction_requests.count()
        old_prediction_requests.delete()
        
        # Nettoyer le cache des prédictions
        cache_keys = cache.keys("predicted_conflicts_*")
        for key in cache_keys:
            cache.delete(key)
        
        logger.info(f"Nettoyage terminé: {deleted_count} tâches, {deleted_predictions} prédictions supprimées")
        
        return {
            'success': True,
            'training_tasks_deleted': deleted_count,
            'prediction_requests_deleted': deleted_predictions,
            'cache_cleaned': len(cache_keys)
        }
        
    except Exception as e:
        logger.error(f"Erreur nettoyage: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def update_model_performance():
    """Tâche pour mettre à jour les métriques de performance des modèles"""
    try:
        from .models import ModelPerformanceMetric, PredictionHistory
        
        active_models = MLModel.objects.filter(is_active=True)
        
        for model in active_models:
            # Calculer les métriques basées sur le feedback utilisateur
            predictions_with_feedback = PredictionHistory.objects.filter(
                feedback_provided=True
            )
            
            if predictions_with_feedback.exists():
                # Calculer l'erreur moyenne
                total_error = sum(
                    abs(p.predicted_difficulty - p.actual_difficulty)
                    for p in predictions_with_feedback
                )
                
                avg_error = total_error / predictions_with_feedback.count()
                accuracy = max(0, 1 - avg_error)
                
                # Enregistrer la métrique
                ModelPerformanceMetric.objects.create(
                    model=model,
                    metric_name='user_feedback_accuracy',
                    metric_value=accuracy,
                    dataset_name='user_feedback'
                )
                
                logger.info(f"Métriques mises à jour pour {model.name}: accuracy={accuracy:.3f}")
        
        return {'success': True, 'models_updated': len(active_models)}
        
    except Exception as e:
        logger.error(f"Erreur mise à jour métriques: {str(e)}")
        return {'success': False, 'error': str(e)}


# Tâches périodiques configurées dans Celery Beat
@shared_task
def daily_optimization_check():
    """Vérification quotidienne des emplois du temps nécessitant une optimisation"""
    try:
        # Trouver les emplois du temps avec beaucoup de conflits
        problematic_schedules = []
        
        for schedule in Schedule.objects.filter(is_published=True):
            conflicts_count = schedule.sessions.filter(
                conflicts__isnull=False
            ).distinct().count()
            
            if conflicts_count > 5:  # Seuil de conflits
                problematic_schedules.append({
                    'schedule_id': schedule.id,
                    'conflicts_count': conflicts_count,
                    'name': schedule.name
                })
        
        # Lancer des optimisations automatiques si nécessaire
        optimizations_started = 0
        for schedule_info in problematic_schedules[:5]:  # Limiter à 5 par jour
            optimize_schedule_async.delay(
                schedule_id=schedule_info['schedule_id'],
                algorithm='genetic',
                algorithm_params={'generations': 200}  # Version rapide
            )
            optimizations_started += 1
        
        logger.info(f"Vérification quotidienne: {len(problematic_schedules)} emplois problématiques, "
                   f"{optimizations_started} optimisations lancées")
        
        return {
            'success': True,
            'problematic_schedules': len(problematic_schedules),
            'optimizations_started': optimizations_started
        }
        
    except Exception as e:
        logger.error(f"Erreur vérification quotidienne: {str(e)}")
        return {'success': False, 'error': str(e)}


# Utilitaires pour le monitoring des tâches
class TaskMonitor:
    """Moniteur pour suivre l'état des tâches"""
    
    @staticmethod
    def get_task_progress(task_id: str) -> Dict[str, Any]:
        """Récupère le progrès d'une tâche"""
        from celery.result import AsyncResult
        
        result = AsyncResult(task_id)
        
        if result.state == 'PROGRESS':
            return result.info
        elif result.state == 'SUCCESS':
            return {
                'progress': 100,
                'message': 'Terminé avec succès',
                'result': result.result
            }
        elif result.state == 'FAILURE':
            return {
                'progress': 0,
                'message': f'Erreur: {str(result.info)}',
                'error': str(result.info)
            }
        else:
            return {
                'progress': 0,
                'message': f'État: {result.state}',
                'state': result.state
            }
    
    @staticmethod
    def cancel_task(task_id: str) -> bool:
        """Annule une tâche"""
        from celery.result import AsyncResult
        
        result = AsyncResult(task_id)
        result.revoke(terminate=True)
        return True
    
    @staticmethod
    def get_running_tasks() -> List[Dict[str, Any]]:
        """Récupère toutes les tâches en cours"""
        from celery import current_app
        
        inspect = current_app.control.inspect()
        active_tasks = inspect.active()
        
        if not active_tasks:
            return []
        
        tasks = []
        for worker, task_list in active_tasks.items():
            for task in task_list:
                tasks.append({
                    'task_id': task['id'],
                    'name': task['name'],
                    'worker': worker,
                    'args': task['args'],
                    'kwargs': task['kwargs']
                })
        
        return tasks


# ============================================================================
# NOUVELLES TÂCHES SIMPLES POUR L'INTÉGRATION ML BASIQUE
# ============================================================================

@shared_task(name='ml_engine.tasks.update_all_course_predictions')
def update_all_course_predictions():
    """
    Tâche périodique: Met à jour les prédictions ML pour tous les cours actifs
    Planifié: Tous les jours à 2h du matin
    """
    from courses.models import Course
    from django.db.models import Q

    logger.info("🤖 Début de la mise à jour quotidienne des prédictions ML")

    # Récupérer tous les cours actifs qui n'ont pas été mis à jour dans les 23 heures
    cutoff_time = timezone.now() - timedelta(hours=23)
    courses_to_update = Course.objects.filter(
        Q(ml_last_updated__lt=cutoff_time) | Q(ml_last_updated__isnull=True)
    )

    total_courses = courses_to_update.count()
    success_count = 0
    error_count = 0

    logger.info(f"📊 {total_courses} cours à mettre à jour")

    for course in courses_to_update:
        try:
            prediction = course.update_ml_predictions(force=True)
            if prediction and not prediction.get('error'):
                success_count += 1
                logger.debug(f"✅ Cours {course.code}: {course.ml_complexity_level}")
            else:
                error_count += 1
                logger.warning(f"⚠️ Erreur pour le cours {course.code}")
        except Exception as e:
            error_count += 1
            logger.error(f"❌ Erreur pour le cours {course.code}: {e}")

    logger.info(f"✅ Mise à jour terminée: {success_count} succès, {error_count} erreurs sur {total_courses} cours")

    return {
        'total': total_courses,
        'success': success_count,
        'errors': error_count,
        'timestamp': timezone.now().isoformat()
    }


@shared_task(name='ml_engine.tasks.detect_anomalies_for_published_schedules')
def detect_anomalies_for_published_schedules():
    """
    Tâche périodique: Détecte les anomalies dans tous les emplois du temps publiés
    Planifié: Toutes les heures
    """
    from schedules.models import Schedule
    from ml_engine.simple_ml_service import SimpleMLService

    logger.info("🔍 Début de la détection d'anomalies pour les schedules publiés")

    ml_service = SimpleMLService()

    # Récupérer tous les schedules publiés
    published_schedules = Schedule.objects.filter(is_published=True)
    total_schedules = published_schedules.count()

    total_anomalies = 0
    critical_anomalies = 0

    logger.info(f"📊 {total_schedules} emplois du temps à analyser")

    for schedule in published_schedules:
        try:
            anomalies_result = ml_service.detect_schedule_anomalies(
                schedule_data={'schedule_id': schedule.id}
            )

            anomalies = anomalies_result.get('anomalies', [])
            total_anomalies += len(anomalies)

            # Compter les anomalies critiques
            critical = sum(1 for a in anomalies if a.get('severity') == 'critical')
            critical_anomalies += critical

            if critical > 0:
                logger.warning(
                    f"⚠️ Schedule {schedule.id} ({schedule.name}): "
                    f"{critical} anomalies critiques détectées"
                )

        except Exception as e:
            logger.error(f"❌ Erreur pour le schedule {schedule.id}: {e}")

    logger.info(
        f"✅ Détection terminée: {total_anomalies} anomalies trouvées "
        f"({critical_anomalies} critiques) dans {total_schedules} schedules"
    )

    return {
        'total_schedules': total_schedules,
        'total_anomalies': total_anomalies,
        'critical_anomalies': critical_anomalies,
        'timestamp': timezone.now().isoformat()
    }


@shared_task(name='ml_engine.tasks.cleanup_old_predictions')
def cleanup_old_predictions():
    """
    Tâche périodique: Nettoie les anciennes prédictions ML (>30 jours)
    Planifié: Chaque dimanche à 3h du matin
    """
    from courses.models import Course

    logger.info("🧹 Début du nettoyage des anciennes prédictions ML")

    cutoff_date = timezone.now() - timedelta(days=30)

    # Trouver les cours avec de vieilles prédictions
    old_predictions = Course.objects.filter(
        ml_last_updated__lt=cutoff_date
    ).exclude(ml_last_updated__isnull=True)

    count = old_predictions.count()

    if count > 0:
        logger.info(f"📊 {count} anciennes prédictions à nettoyer")

        # Réinitialiser les prédictions anciennes
        updated = old_predictions.update(
            ml_difficulty_score=None,
            ml_complexity_level='',
            ml_scheduling_priority=2,
            ml_prediction_metadata={}
        )

        logger.info(f"✅ {updated} prédictions nettoyées")
    else:
        logger.info("✅ Aucune ancienne prédiction à nettoyer")

    return {
        'cleaned_count': count,
        'cutoff_date': cutoff_date.isoformat(),
        'timestamp': timezone.now().isoformat()
    }


@shared_task(name='ml_engine.tasks.generate_weekly_ml_report')
def generate_weekly_ml_report():
    """
    Tâche périodique: Génère un rapport hebdomadaire des performances ML
    Planifié: Chaque lundi à 6h du matin
    """
    from courses.models import Course
    from schedules.models import Schedule

    logger.info("📊 Génération du rapport hebdomadaire ML")

    # Statistiques sur les cours
    total_courses = Course.objects.count()
    courses_with_predictions = Course.objects.exclude(ml_last_updated__isnull=True).count()

    # Distribution de complexité
    complexity_distribution = {
        'facile': Course.objects.filter(ml_complexity_level='Facile').count(),
        'moyenne': Course.objects.filter(ml_complexity_level='Moyenne').count(),
        'difficile': Course.objects.filter(ml_complexity_level='Difficile').count(),
    }

    # Statistiques sur les schedules
    total_schedules = Schedule.objects.count()
    published_schedules = Schedule.objects.filter(is_published=True).count()

    # Prédictions récentes (7 derniers jours)
    week_ago = timezone.now() - timedelta(days=7)
    recent_predictions = Course.objects.filter(ml_last_updated__gte=week_ago).count()

    report = {
        'period': {
            'start': week_ago.isoformat(),
            'end': timezone.now().isoformat(),
        },
        'courses': {
            'total': total_courses,
            'with_predictions': courses_with_predictions,
            'prediction_coverage': round(
                (courses_with_predictions / total_courses * 100) if total_courses > 0 else 0, 2
            ),
            'complexity_distribution': complexity_distribution,
        },
        'schedules': {
            'total': total_schedules,
            'published': published_schedules,
        },
        'activity': {
            'recent_predictions': recent_predictions,
            'predictions_per_day': round(recent_predictions / 7, 1),
        },
        'timestamp': timezone.now().isoformat()
    }

    logger.info(f"✅ Rapport généré: {courses_with_predictions}/{total_courses} cours avec prédictions")
    logger.info(f"   Distribution: Facile={complexity_distribution['facile']}, "
                f"Moyenne={complexity_distribution['moyenne']}, "
                f"Difficile={complexity_distribution['difficile']}")

    return report


@shared_task(name='ml_engine.tasks.update_course_prediction')
def update_course_prediction(course_id):
    """
    Tâche asynchrone: Met à jour les prédictions ML pour un cours spécifique
    Utilisé pour les mises à jour à la demande

    Args:
        course_id: ID du cours à mettre à jour
    """
    from courses.models import Course

    try:
        course = Course.objects.get(id=course_id)
        logger.info(f"🤖 Mise à jour ML pour le cours {course.code}")

        prediction = course.update_ml_predictions(force=True)

        if prediction and not prediction.get('error'):
            logger.info(f"✅ Prédiction ML réussie pour {course.code}: {course.ml_complexity_level}")
            return {
                'success': True,
                'course_id': course_id,
                'course_code': course.code,
                'complexity': course.ml_complexity_level,
                'difficulty_score': course.ml_difficulty_score,
                'timestamp': timezone.now().isoformat()
            }
        else:
            logger.error(f"❌ Erreur lors de la prédiction ML pour {course.code}")
            return {
                'success': False,
                'course_id': course_id,
                'error': prediction.get('error', 'Unknown error'),
                'timestamp': timezone.now().isoformat()
            }

    except Course.DoesNotExist:
        logger.error(f"❌ Cours {course_id} introuvable")
        return {
            'success': False,
            'course_id': course_id,
            'error': 'Course not found',
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Erreur lors de la mise à jour ML pour le cours {course_id}: {e}")
        return {
            'success': False,
            'course_id': course_id,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name='ml_engine.tasks.analyze_schedule_async')
def analyze_schedule_async(schedule_id):
    """
    Tâche asynchrone: Analyse complète d'un emploi du temps avec détection d'anomalies

    Args:
        schedule_id: ID du schedule à analyser
    """
    from schedules.models import Schedule
    from ml_engine.simple_ml_service import SimpleMLService

    try:
        schedule = Schedule.objects.get(id=schedule_id)
        logger.info(f"🔍 Analyse ML asynchrone du schedule {schedule.id} ({schedule.name})")

        ml_service = SimpleMLService()

        # Détection des anomalies
        anomalies_result = ml_service.detect_schedule_anomalies(
            schedule_data={'schedule_id': schedule.id}
        )

        anomalies = anomalies_result.get('anomalies', [])
        critical_count = sum(1 for a in anomalies if a.get('severity') == 'critical')

        logger.info(
            f"✅ Analyse terminée pour {schedule.name}: "
            f"{len(anomalies)} anomalies ({critical_count} critiques)"
        )

        return {
            'success': True,
            'schedule_id': schedule_id,
            'schedule_name': schedule.name,
            'total_anomalies': len(anomalies),
            'critical_anomalies': critical_count,
            'anomalies': anomalies[:10],  # Limiter à 10 pour ne pas surcharger
            'timestamp': timezone.now().isoformat()
        }

    except Schedule.DoesNotExist:
        logger.error(f"❌ Schedule {schedule_id} introuvable")
        return {
            'success': False,
            'schedule_id': schedule_id,
            'error': 'Schedule not found',
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'analyse ML du schedule {schedule_id}: {e}")
        return {
            'success': False,
            'schedule_id': schedule_id,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }