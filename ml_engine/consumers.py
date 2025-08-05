#!/usr/bin/env python3
"""
WebSocket Consumers pour OAPET ML Engine
=======================================

Gestion des connexions WebSocket pour le suivi en temps réel des:
- Tâches d'entraînement ML
- Optimisations d'emplois du temps
- Prédictions en lot
- Notifications de conflits
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, Any

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.core.cache import cache

from .models import ModelTrainingTask, ScheduleOptimization
from .tasks import TaskMonitor


class MLTaskConsumer(AsyncWebsocketConsumer):
    """Consumer pour le suivi des tâches ML"""
    
    async def connect(self):
        """Connexion WebSocket"""
        self.task_id = self.scope['url_route']['kwargs']['task_id']
        self.task_group_name = f'ml_task_{self.task_id}'
        
        # Rejoindre le groupe
        await self.channel_layer.group_add(
            self.task_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Envoyer l'état initial
        await self.send_task_status()
    
    async def disconnect(self, close_code):
        """Déconnexion WebSocket"""
        await self.channel_layer.group_discard(
            self.task_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Réception de messages du client"""
        try:
            data = json.loads(text_data)
            command = data.get('command')
            
            if command == 'get_status':
                await self.send_task_status()
            elif command == 'cancel_task':
                await self.cancel_task()
            elif command == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': datetime.now().isoformat()
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Format JSON invalide'
            }))
    
    async def send_task_status(self):
        """Envoie l'état actuel de la tâche"""
        progress_data = TaskMonitor.get_task_progress(self.task_id)
        
        await self.send(text_data=json.dumps({
            'type': 'task_status',
            'task_id': self.task_id,
            'data': progress_data
        }))
    
    async def cancel_task(self):
        """Annule la tâche"""
        success = TaskMonitor.cancel_task(self.task_id)
        
        await self.send(text_data=json.dumps({
            'type': 'task_cancelled',
            'task_id': self.task_id,
            'success': success
        }))
    
    # Handlers pour les messages du groupe
    async def task_progress(self, event):
        """Diffuse le progrès de la tâche"""
        await self.send(text_data=json.dumps({
            'type': 'progress_update',
            'task_id': event['task_id'],
            'progress': event['progress'],
            'message': event['message'],
            'timestamp': event.get('timestamp', datetime.now().isoformat())
        }))
    
    async def task_completed(self, event):
        """Diffuse la completion de la tâche"""
        await self.send(text_data=json.dumps({
            'type': 'task_completed',
            'task_id': event['task_id'],
            'result': event['result'],
            'timestamp': event.get('timestamp', datetime.now().isoformat())
        }))
    
    async def task_failed(self, event):
        """Diffuse l'échec de la tâche"""
        await self.send(text_data=json.dumps({
            'type': 'task_failed',
            'task_id': event['task_id'],
            'error': event['error'],
            'timestamp': event.get('timestamp', datetime.now().isoformat())
        }))


class OptimizationConsumer(AsyncWebsocketConsumer):
    """Consumer pour le suivi des optimisations d'emplois du temps"""
    
    async def connect(self):
        """Connexion WebSocket"""
        self.schedule_id = self.scope['url_route']['kwargs']['schedule_id']
        self.optimization_group_name = f'optimization_{self.schedule_id}'
        
        # Vérifier les permissions
        user = self.scope['user']
        if not await self.check_permissions(user, self.schedule_id):
            await self.close()
            return
        
        # Rejoindre le groupe
        await self.channel_layer.group_add(
            self.optimization_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Envoyer l'état initial
        await self.send_optimization_status()
    
    async def disconnect(self, close_code):
        """Déconnexion WebSocket"""
        await self.channel_layer.group_discard(
            self.optimization_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Réception de messages du client"""
        try:
            data = json.loads(text_data)
            command = data.get('command')
            
            if command == 'get_status':
                await self.send_optimization_status()
            elif command == 'start_optimization':
                await self.start_optimization(data)
            elif command == 'get_conflicts':
                await self.send_conflicts_status()
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Format JSON invalide'
            }))
    
    @database_sync_to_async
    def check_permissions(self, user, schedule_id):
        """Vérifie les permissions de l'utilisateur"""
        if not user.is_authenticated:
            return False
        
        # Ici vous pouvez ajouter votre logique de permissions
        # Par exemple, vérifier si l'utilisateur peut modifier cet emploi du temps
        return True
    
    async def send_optimization_status(self):
        """Envoie l'état actuel de l'optimisation"""
        optimization_data = await self.get_latest_optimization()
        
        await self.send(text_data=json.dumps({
            'type': 'optimization_status',
            'schedule_id': self.schedule_id,
            'data': optimization_data
        }))
    
    async def send_conflicts_status(self):
        """Envoie l'état des conflits"""
        conflicts_data = await self.get_conflicts_data()
        
        await self.send(text_data=json.dumps({
            'type': 'conflicts_status',
            'schedule_id': self.schedule_id,
            'conflicts': conflicts_data
        }))
    
    @database_sync_to_async
    def get_latest_optimization(self):
        """Récupère la dernière optimisation"""
        try:
            optimization = ScheduleOptimization.objects.filter(
                schedule_id=self.schedule_id
            ).order_by('-started_at').first()
            
            if optimization:
                return {
                    'id': optimization.id,
                    'algorithm': optimization.algorithm_used,
                    'status': 'completed' if optimization.completed_at else 'running',
                    'conflicts_before': optimization.conflicts_before,
                    'conflicts_after': optimization.conflicts_after,
                    'score': optimization.optimization_score,
                    'started_at': optimization.started_at.isoformat() if optimization.started_at else None,
                    'completed_at': optimization.completed_at.isoformat() if optimization.completed_at else None
                }
            return None
            
        except Exception:
            return None
    
    @database_sync_to_async
    def get_conflicts_data(self):
        """Récupère les données de conflits"""
        try:
            from schedules.models import Schedule, Conflict
            
            schedule = Schedule.objects.get(id=self.schedule_id)
            conflicts = Conflict.objects.filter(
                schedule_session__schedule=schedule,
                is_resolved=False
            )
            
            conflicts_data = []
            for conflict in conflicts:
                conflicts_data.append({
                    'id': conflict.id,
                    'type': conflict.conflict_type,
                    'description': conflict.description,
                    'severity': conflict.severity,
                    'session_id': conflict.schedule_session.id,
                    'course_name': conflict.schedule_session.course.name
                })
            
            return conflicts_data
            
        except Exception:
            return []
    
    async def start_optimization(self, data):
        """Démarre une nouvelle optimisation"""
        algorithm = data.get('algorithm', 'genetic')
        params = data.get('parameters', {})
        
        # Lancer la tâche d'optimisation
        from .tasks import optimize_schedule_async
        
        task_result = optimize_schedule_async.delay(
            schedule_id=self.schedule_id,
            algorithm=algorithm,
            algorithm_params=params,
            user_id=self.scope['user'].id
        )
        
        await self.send(text_data=json.dumps({
            'type': 'optimization_started',
            'task_id': task_result.id,
            'algorithm': algorithm,
            'schedule_id': self.schedule_id
        }))
    
    # Handlers pour les messages du groupe
    async def optimization_progress(self, event):
        """Diffuse le progrès de l'optimisation"""
        await self.send(text_data=json.dumps({
            'type': 'optimization_progress',
            'schedule_id': event['schedule_id'],
            'progress': event['progress'],
            'message': event['message'],
            'conflicts_resolved': event.get('conflicts_resolved', 0)
        }))
    
    async def optimization_completed(self, event):
        """Diffuse la completion de l'optimisation"""
        await self.send(text_data=json.dumps({
            'type': 'optimization_completed',
            'schedule_id': event['schedule_id'],
            'result': event['result']
        }))
    
    async def conflicts_detected(self, event):
        """Diffuse la détection de nouveaux conflits"""
        await self.send(text_data=json.dumps({
            'type': 'conflicts_detected',
            'schedule_id': event['schedule_id'],
            'conflicts': event['conflicts'],
            'count': len(event['conflicts'])
        }))


class DashboardConsumer(AsyncWebsocketConsumer):
    """Consumer pour le dashboard ML en temps réel"""
    
    async def connect(self):
        """Connexion WebSocket"""
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.dashboard_group_name = 'ml_dashboard'
        
        # Rejoindre le groupe
        await self.channel_layer.group_add(
            self.dashboard_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Envoyer l'état initial
        await self.send_dashboard_status()
    
    async def disconnect(self, close_code):
        """Déconnexion WebSocket"""
        await self.channel_layer.group_discard(
            self.dashboard_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Réception de messages du client"""
        try:
            data = json.loads(text_data)
            command = data.get('command')
            
            if command == 'get_stats':
                await self.send_dashboard_status()
            elif command == 'get_running_tasks':
                await self.send_running_tasks()
            elif command == 'get_model_performance':
                await self.send_model_performance()
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Format JSON invalide'
            }))
    
    async def send_dashboard_status(self):
        """Envoie l'état global du dashboard"""
        stats = await self.get_ml_stats()
        
        await self.send(text_data=json.dumps({
            'type': 'dashboard_status',
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        }))
    
    async def send_running_tasks(self):
        """Envoie la liste des tâches en cours"""
        running_tasks = TaskMonitor.get_running_tasks()
        
        await self.send(text_data=json.dumps({
            'type': 'running_tasks',
            'tasks': running_tasks
        }))
    
    async def send_model_performance(self):
        """Envoie les performances des modèles"""
        performance_data = await self.get_model_performance()
        
        await self.send(text_data=json.dumps({
            'type': 'model_performance',
            'performance': performance_data
        }))
    
    @database_sync_to_async
    def get_ml_stats(self):
        """Récupère les statistiques ML"""
        try:
            from .models import MLModel, ModelTrainingTask, PredictionRequest
            
            stats = {
                'active_models': MLModel.objects.filter(is_active=True).count(),
                'total_models': MLModel.objects.count(),
                'training_tasks_today': ModelTrainingTask.objects.filter(
                    created_at__date=datetime.now().date()
                ).count(),
                'predictions_today': PredictionRequest.objects.filter(
                    created_at__date=datetime.now().date()
                ).count(),
                'successful_trainings': ModelTrainingTask.objects.filter(
                    status='completed'
                ).count(),
                'failed_trainings': ModelTrainingTask.objects.filter(
                    status='failed'
                ).count()
            }
            
            return stats
            
        except Exception:
            return {}
    
    @database_sync_to_async
    def get_model_performance(self):
        """Récupère les performances des modèles"""
        try:
            from .models import MLModel, ModelPerformanceMetric
            
            performance = {}
            
            for model in MLModel.objects.filter(is_active=True):
                latest_metrics = ModelPerformanceMetric.objects.filter(
                    model=model
                ).order_by('-recorded_at')[:5]
                
                performance[model.name] = {
                    'model_type': model.model_type,
                    'metrics': [
                        {
                            'name': metric.metric_name,
                            'value': metric.metric_value,
                            'date': metric.recorded_at.isoformat()
                        }
                        for metric in latest_metrics
                    ]
                }
            
            return performance
            
        except Exception:
            return {}
    
    # Handlers pour les messages du groupe
    async def stats_update(self, event):
        """Diffuse la mise à jour des statistiques"""
        await self.send(text_data=json.dumps({
            'type': 'stats_update',
            'stats': event['stats']
        }))
    
    async def model_trained(self, event):
        """Diffuse l'entraînement d'un nouveau modèle"""
        await self.send(text_data=json.dumps({
            'type': 'model_trained',
            'model': event['model']
        }))
    
    async def prediction_made(self, event):
        """Diffuse une nouvelle prédiction"""
        await self.send(text_data=json.dumps({
            'type': 'prediction_made',
            'prediction': event['prediction']
        }))


# Utilitaires pour diffuser les messages WebSocket
class WebSocketNotifier:
    """Classe utilitaire pour envoyer des notifications WebSocket"""
    
    @staticmethod
    async def notify_task_progress(task_id: str, progress: float, message: str):
        """Notifie le progrès d'une tâche"""
        from channels.layers import get_channel_layer
        
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f'ml_task_{task_id}',
            {
                'type': 'task_progress',
                'task_id': task_id,
                'progress': progress,
                'message': message,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    @staticmethod
    async def notify_task_completed(task_id: str, result: Dict[str, Any]):
        """Notifie la completion d'une tâche"""
        from channels.layers import get_channel_layer
        
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f'ml_task_{task_id}',
            {
                'type': 'task_completed',
                'task_id': task_id,
                'result': result,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    @staticmethod
    async def notify_optimization_progress(schedule_id: int, progress: float, 
                                         message: str, conflicts_resolved: int = 0):
        """Notifie le progrès d'une optimisation"""
        from channels.layers import get_channel_layer
        
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f'optimization_{schedule_id}',
            {
                'type': 'optimization_progress',
                'schedule_id': schedule_id,
                'progress': progress,
                'message': message,
                'conflicts_resolved': conflicts_resolved
            }
        )
    
    @staticmethod
    async def notify_conflicts_detected(schedule_id: int, conflicts: List[Dict[str, Any]]):
        """Notifie la détection de conflits"""
        from channels.layers import get_channel_layer
        
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f'optimization_{schedule_id}',
            {
                'type': 'conflicts_detected',
                'schedule_id': schedule_id,
                'conflicts': conflicts
            }
        )
    
    @staticmethod
    async def notify_dashboard_update(stats: Dict[str, Any]):
        """Notifie une mise à jour du dashboard"""
        from channels.layers import get_channel_layer
        
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            'ml_dashboard',
            {
                'type': 'stats_update',
                'stats': stats
            }
        )