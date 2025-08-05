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
    TimetableDataset, ScheduleOptimization
)
from .services import (
    TimetableDataProcessor, FeatureExtractor, TimetableMLService,
    TimetablePredictor, MLTrainingService
)
from .algorithms import (
    TimetableOptimizer, ConflictPredictor, 
    GeneticAlgorithm, SimulatedAnnealing
)
from schedules.models import Schedule, ScheduleSession

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