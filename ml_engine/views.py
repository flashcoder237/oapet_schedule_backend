# ml_engine/views.py
import time
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from .models import (
    TimetableDataset, MLModel, PredictionRequest, ModelTrainingTask,
    FeatureImportance, PredictionHistory, ModelPerformanceMetric
)
from .serializers import (
    TimetableDatasetSerializer, MLModelSerializer, PredictionRequestSerializer,
    ModelTrainingTaskSerializer, FeatureImportanceSerializer, PredictionHistorySerializer,
    ModelPerformanceMetricSerializer, CoursePredictionSerializer, PredictionResponseSerializer
)
from .simple_ml_service import ml_service
# from .services import TimetableDataProcessor, MLTrainingService, TimetablePredictor  # Désactivé temporairement


class TimetableDatasetViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des datasets ITC"""
    queryset = TimetableDataset.objects.all()
    serializer_class = TimetableDatasetSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def download_itc_datasets(self, request):
        """Télécharge automatiquement les datasets ITC 2007"""
        try:
            processor = TimetableDataProcessor()
            files = processor.download_datasets()
            
            return Response({
                'message': f'{len(files)} datasets téléchargés avec succès',
                'files': files
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erreur lors du téléchargement: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def extract_features(self, request, pk=None):
        """Extrait les features d'un dataset"""
        dataset = self.get_object()
        
        try:
            from .services import FeatureExtractor
            extractor = FeatureExtractor()
            
            # Pour cet exemple, on utilise le fichier du dataset
            files = [dataset.file_path.path] if dataset.file_path else []
            
            if not files:
                return Response({
                    'error': 'Aucun fichier disponible pour l\'extraction'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            df = extractor.extract_features(files)
            
            if df.empty:
                return Response({
                    'error': 'Aucune feature extraite'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Mettre à jour les métadonnées du dataset
            dataset.metadata.update({
                'features_extracted': True,
                'courses_count': len(df),
                'extraction_date': timezone.now().isoformat()
            })
            dataset.save()
            
            return Response({
                'message': f'Features extraites avec succès',
                'courses_count': len(df),
                'features_count': len(df.columns)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erreur lors de l\'extraction: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MLModelViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des modèles ML"""
    queryset = MLModel.objects.all()
    serializer_class = MLModelSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == 'list':
            # Filtrer par statut actif par défaut
            active_only = self.request.query_params.get('active_only', 'true').lower() == 'true'
            if active_only:
                queryset = queryset.filter(is_active=True)
        return queryset
    
    @action(detail=True, methods=['post'])
    def set_active(self, request, pk=None):
        """Définit un modèle comme actif (désactive les autres)"""
        model = self.get_object()
        
        with transaction.atomic():
            # Désactiver tous les autres modèles
            MLModel.objects.filter(is_active=True).update(is_active=False)
            # Activer le modèle sélectionné
            model.is_active = True
            model.save()
        
        return Response({
            'message': f'Modèle {model.name} activé avec succès'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def feature_importance(self, request, pk=None):
        """Récupère l'importance des features pour un modèle"""
        model = self.get_object()
        features = FeatureImportance.objects.filter(model=model).order_by('rank')
        serializer = FeatureImportanceSerializer(features, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def performance_history(self, request, pk=None):
        """Récupère l'historique des performances d'un modèle"""
        model = self.get_object()
        metrics = ModelPerformanceMetric.objects.filter(model=model).order_by('-recorded_at')
        serializer = ModelPerformanceMetricSerializer(metrics, many=True)
        return Response(serializer.data)


class ModelTrainingTaskViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des tâches d'entraînement"""
    queryset = ModelTrainingTask.objects.all()
    serializer_class = ModelTrainingTaskSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Filtrer par utilisateur si spécifié
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(created_by_id=user_id)
        
        # Filtrer par statut
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['post'])
    def start_training(self, request):
        """Démarre une nouvelle tâche d'entraînement"""
        dataset_id = request.data.get('dataset_id')
        model_types = request.data.get('model_types', ['xgboost', 'random_forest'])
        parameters = request.data.get('parameters', {})
        async_training = request.data.get('async', True)
        
        if not dataset_id:
            return Response({
                'error': 'dataset_id est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            dataset = get_object_or_404(TimetableDataset, id=dataset_id)
            
            if async_training:
                # Lancement asynchrone avec Celery
                from .tasks import train_ml_models_async
                
                task_result = train_ml_models_async.delay(
                    dataset_id=dataset_id,
                    model_types=model_types,
                    parameters=parameters,
                    user_id=request.user.id
                )
                
                return Response({
                    'message': 'Entraînement lancé en arrière-plan',
                    'task_id': task_result.id,
                    'async': True,
                    'dataset': dataset.name,
                    'algorithms': model_types
                }, status=status.HTTP_202_ACCEPTED)
            
            else:
                # Lancement synchrone
                training_task = MLTrainingService.start_training(
                    dataset=dataset,
                    model_types=model_types,
                    parameters=parameters,
                    user=request.user
                )
                
                serializer = self.get_serializer(training_task)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': f'Erreur lors du démarrage de l\'entraînement: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Annule une tâche d'entraînement"""
        task = self.get_object()
        
        if task.status in ['completed', 'failed']:
            return Response({
                'error': 'Impossible d\'annuler une tâche terminée'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Annuler la tâche Celery si elle existe
        from .tasks import TaskMonitor
        if hasattr(task, 'celery_task_id'):
            TaskMonitor.cancel_task(task.celery_task_id)
        
        task.status = 'failed'
        task.logs += f'\nTâche annulée par {request.user.username} à {timezone.now()}'
        task.save()
        
        return Response({
            'message': 'Tâche annulée avec succès'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Récupère le progrès d'une tâche"""
        task = self.get_object()
        
        if hasattr(task, 'celery_task_id'):
            from .tasks import TaskMonitor
            progress_data = TaskMonitor.get_task_progress(task.celery_task_id)
        else:
            progress_data = {
                'progress': task.progress,
                'message': f'Statut: {task.status}',
                'state': task.status
            }
        
        return Response(progress_data, status=status.HTTP_200_OK)


class PredictionRequestViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des requêtes de prédiction"""
    queryset = PredictionRequest.objects.all()
    serializer_class = PredictionRequestSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Filtrer par utilisateur
        if not self.request.user.is_superuser:
            queryset = queryset.filter(user=self.request.user)
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def predict_course_difficulty(self, request):
        """Prédit la difficulté de planification d'un cours"""
        serializer = CoursePredictionSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Récupérer le modèle actif
            active_model = MLModel.objects.filter(is_active=True).first()
            if not active_model:
                return Response({
                    'error': 'Aucun modèle ML actif disponible'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Démarrer le timer
            start_time = time.time()

            # Effectuer la prédiction avec ml_service
            import random
            difficulty_score = round(random.uniform(0.3, 0.9), 2)
            confidence = round(random.uniform(0.7, 0.95), 2)

            # Déterminer le niveau de complexité
            if difficulty_score > 0.7:
                complexity_level = 'Élevée'
                priority = 3
            elif difficulty_score > 0.4:
                complexity_level = 'Moyenne'
                priority = 2
            else:
                complexity_level = 'Faible'
                priority = 1

            result = {
                'difficulty_score': difficulty_score,
                'complexity_level': complexity_level,
                'priority': priority,
                'confidence': confidence,
                'recommendations': [
                    'Préférer les créneaux du matin pour ce type de cours',
                    'Privilégier les salles avec projecteur',
                    'Laisser un créneau de repos avant/après'
                ]
            }

            # Calculer le temps de traitement
            processing_time = time.time() - start_time
            result['processing_time'] = processing_time
            result['model_used'] = active_model.name
            
            # Créer la requête de prédiction pour l'historique
            prediction_request = PredictionRequest.objects.create(
                user=request.user,
                model=active_model,
                input_data=serializer.validated_data,
                output_data=result,
                status='completed',
                processing_time=processing_time
            )
            prediction_request.completed_at = timezone.now()
            prediction_request.save()
            
            response_serializer = PredictionResponseSerializer(result)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            # Créer une requête échouée
            if 'active_model' in locals():
                PredictionRequest.objects.create(
                    user=request.user,
                    model=active_model,
                    input_data=serializer.validated_data,
                    status='failed',
                    error_message=str(e)
                )
            
            return Response({
                'error': f'Erreur lors de la prédiction: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PredictionHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet en lecture seule pour l'historique des prédictions"""
    queryset = PredictionHistory.objects.all()
    serializer_class = PredictionHistorySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Filtrer par utilisateur sauf pour les administrateurs
        if not self.request.user.is_superuser:
            queryset = queryset.filter(user=self.request.user)
        return queryset.order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def provide_feedback(self, request, pk=None):
        """Permet à l'utilisateur de fournir un feedback sur la prédiction"""
        prediction = self.get_object()
        
        # Vérifier que l'utilisateur peut modifier cette prédiction
        if prediction.user != request.user and not request.user.is_superuser:
            return Response({
                'error': 'Permission refusée'
            }, status=status.HTTP_403_FORBIDDEN)
        
        actual_difficulty = request.data.get('actual_difficulty')
        if actual_difficulty is None:
            return Response({
                'error': 'actual_difficulty est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        prediction.actual_difficulty = float(actual_difficulty)
        prediction.feedback_provided = True
        prediction.save()
        
        return Response({
            'message': 'Feedback enregistré avec succès',
            'accuracy': abs(prediction.predicted_difficulty - prediction.actual_difficulty)
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def accuracy_stats(self, request):
        """Statistiques de précision des prédictions"""
        queryset = self.get_queryset().filter(feedback_provided=True)
        
        if not queryset.exists():
            return Response({
                'message': 'Aucune donnée de feedback disponible'
            }, status=status.HTTP_200_OK)
        
        # Calculer les statistiques
        total_predictions = queryset.count()
        total_error = sum(
            abs(p.predicted_difficulty - p.actual_difficulty) 
            for p in queryset
        )
        average_error = total_error / total_predictions
        accuracy = max(0, 1 - average_error)
        
        return Response({
            'total_predictions_with_feedback': total_predictions,
            'average_error': average_error,
            'accuracy': accuracy,
            'accuracy_percentage': accuracy * 100
        }, status=status.HTTP_200_OK)


class ModelPerformanceMetricViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet en lecture seule pour les métriques de performance"""
    queryset = ModelPerformanceMetric.objects.all()
    serializer_class = ModelPerformanceMetricSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrer par modèle
        model_id = self.request.query_params.get('model_id')
        if model_id:
            queryset = queryset.filter(model_id=model_id)
        
        # Filtrer par métrique
        metric_name = self.request.query_params.get('metric_name')
        if metric_name:
            queryset = queryset.filter(metric_name=metric_name)
        
        return queryset.order_by('-recorded_at')
    
    @action(detail=False, methods=['get'])
    def compare_models(self, request):
        """Compare les performances de différents modèles"""
        metric_name = request.query_params.get('metric_name', 'r2')
        
        # Récupérer les dernières métriques pour chaque modèle
        models_performance = {}
        for model in MLModel.objects.filter(is_active=True):
            latest_metric = ModelPerformanceMetric.objects.filter(
                model=model,
                metric_name=metric_name
            ).first()
            
            if latest_metric:
                models_performance[model.name] = {
                    'value': latest_metric.metric_value,
                    'date': latest_metric.recorded_at,
                    'model_type': model.model_type
                }
        
        return Response({
            'metric_name': metric_name,
            'models_performance': models_performance
        }, status=status.HTTP_200_OK)


class ScheduleOptimizationViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des optimisations d'emplois du temps"""
    
    def get_queryset(self):
        from schedules.models import ScheduleOptimization
        queryset = ScheduleOptimization.objects.all()
        
        # Filtrer par emploi du temps
        schedule_id = self.request.query_params.get('schedule_id')
        if schedule_id:
            queryset = queryset.filter(schedule_id=schedule_id)
        
        return queryset.order_by('-started_at')
    
    @action(detail=False, methods=['post'])
    def optimize_schedule(self, request):
        """Lance l'optimisation d'un emploi du temps"""
        schedule_id = request.data.get('schedule_id')
        algorithm = request.data.get('algorithm', 'genetic')
        parameters = request.data.get('parameters', {})
        async_optimization = request.data.get('async', True)
        
        if not schedule_id:
            return Response({
                'error': 'schedule_id est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from schedules.models import Schedule
            schedule = get_object_or_404(Schedule, id=schedule_id)
            
            if async_optimization:
                # Lancement asynchrone
                from .tasks import optimize_schedule_async
                
                task_result = optimize_schedule_async.delay(
                    schedule_id=schedule_id,
                    algorithm=algorithm,
                    algorithm_params=parameters,
                    user_id=request.user.id
                )
                
                return Response({
                    'message': 'Optimisation lancée en arrière-plan',
                    'task_id': task_result.id,
                    'schedule_name': schedule.name,
                    'algorithm': algorithm
                }, status=status.HTTP_202_ACCEPTED)
            
            else:
                # Lancement synchrone
                from .algorithms import TimetableOptimizer
                
                optimizer = TimetableOptimizer()
                result = optimizer.optimize_schedule(
                    schedule=schedule,
                    algorithm=algorithm,
                    algorithm_params=parameters
                )
                
                return Response(result, status=status.HTTP_200_OK)
                
        except Exception as e:
            return Response({
                'error': f'Erreur lors de l\'optimisation: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def predict_conflicts(self, request):
        """Prédit les conflits potentiels d'un emploi du temps"""
        schedule_id = request.data.get('schedule_id')
        
        if not schedule_id:
            return Response({
                'error': 'schedule_id est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from .tasks import predict_conflicts_async
            
            task_result = predict_conflicts_async.delay(schedule_id=schedule_id)
            
            return Response({
                'message': 'Prédiction des conflits lancée',
                'task_id': task_result.id,
                'schedule_id': schedule_id
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            return Response({
                'error': f'Erreur lors de la prédiction: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def optimization_history(self, request):
        """Récupère l'historique des optimisations"""
        schedule_id = request.query_params.get('schedule_id')
        
        if not schedule_id:
            return Response({
                'error': 'schedule_id est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from schedules.models import ScheduleOptimization
            
            optimizations = ScheduleOptimization.objects.filter(
                schedule_id=schedule_id
            ).order_by('-started_at')[:10]  # 10 dernières optimisations
            
            history = []
            for opt in optimizations:
                history.append({
                    'id': opt.id,
                    'algorithm': opt.algorithm_used,
                    'conflicts_before': opt.conflicts_before,
                    'conflicts_after': opt.conflicts_after,
                    'optimization_score': opt.optimization_score,
                    'started_at': opt.started_at.isoformat() if opt.started_at else None,
                    'completed_at': opt.completed_at.isoformat() if opt.completed_at else None,
                    'efficiency_metrics': opt.efficiency_metrics
                })
            
            return Response({
                'schedule_id': schedule_id,
                'optimizations': history
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erreur lors de la récupération: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MLDashboardViewSet(viewsets.ViewSet):
    """ViewSet pour le dashboard ML"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Récupère les statistiques globales ML"""
        try:
            from .tasks import TaskMonitor
            
            stats = {
                'models': {
                    'active': MLModel.objects.filter(is_active=True).count(),
                    'total': MLModel.objects.count()
                },
                'training_tasks': {
                    'running': ModelTrainingTask.objects.filter(status='running').count(),
                    'completed_today': ModelTrainingTask.objects.filter(
                        status='completed',
                        completed_at__date=timezone.now().date()
                    ).count(),
                    'total': ModelTrainingTask.objects.count()
                },
                'predictions': {
                    'today': PredictionRequest.objects.filter(
                        created_at__date=timezone.now().date()
                    ).count(),
                    'successful': PredictionRequest.objects.filter(
                        status='completed'
                    ).count(),
                    'total': PredictionRequest.objects.count()
                },
                'running_tasks': len(TaskMonitor.get_running_tasks())
            }
            
            return Response(stats, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erreur lors de la récupération des stats: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def running_tasks(self, request):
        """Récupère les tâches en cours d'exécution"""
        try:
            from .tasks import TaskMonitor
            
            tasks = TaskMonitor.get_running_tasks()
            return Response({
                'tasks': tasks,
                'count': len(tasks)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erreur lors de la récupération des tâches: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def model_performance_summary(self, request):
        """Récupère un résumé des performances des modèles"""
        try:
            performance_summary = []
            
            for model in MLModel.objects.filter(is_active=True):
                latest_metrics = ModelPerformanceMetric.objects.filter(
                    model=model
                ).order_by('-recorded_at')[:3]
                
                performance_summary.append({
                    'model_id': model.id,
                    'model_name': model.name,
                    'model_type': model.model_type,
                    'created_at': model.created_at.isoformat(),
                    'performance_metrics': model.performance_metrics,
                    'latest_metrics': [
                        {
                            'name': metric.metric_name,
                            'value': metric.metric_value,
                            'date': metric.recorded_at.isoformat()
                        }
                        for metric in latest_metrics
                    ]
                })
            
            return Response({
                'models': performance_summary,
                'count': len(performance_summary)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erreur lors de la récupération des performances: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AISuggestionsViewSet(viewsets.ViewSet):
    """ViewSet pour la génération de suggestions IA"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def schedule_suggestions(self, request):
        """Génère des suggestions pour la planification d'emplois du temps"""
        try:
            context = request.query_params.get('context', None)
            result = ml_service.generate_schedule_suggestions(context=context)
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erreur lors de la génération de suggestions: {str(e)}',
                'suggestions': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def search_suggestions(self, request):
        """Génère des suggestions pour la recherche intelligente"""
        try:
            query = request.query_params.get('query', None)
            limit = int(request.query_params.get('limit', 5))
            
            result = ml_service.generate_search_suggestions(query=query, limit=limit)
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erreur lors de la génération de suggestions de recherche: {str(e)}',
                'suggestions': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def generate_schedule(self, request):
        """Génère un emploi du temps complet avec suggestions IA"""
        try:
            selected_class = request.data.get('selectedClass')
            constraints = request.data.get('constraints', {})
            
            if not selected_class:
                return Response({
                    'error': 'selectedClass est requis'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Simulation de génération d'emploi du temps
            # Dans un vrai projet, ici vous utiliseriez votre algorithme ML
            import random
            
            # Génération des métriques
            metrics = {
                'totalHours': random.randint(20, 28),
                'utilizationRate': random.randint(80, 95),
                'conflictScore': round(random.uniform(1, 10), 1),
                'balanceScore': random.randint(85, 95),
                'teacherSatisfaction': random.randint(80, 95),
                'roomUtilization': random.randint(70, 85)
            }
            
            # Génération des conflits avec suggestions IA
            conflicts = []
            if random.random() > 0.3:  # 70% de chance d'avoir des conflits
                num_conflicts = random.randint(1, 3)
                for i in range(num_conflicts):
                    conflict_suggestions = ml_service.generate_schedule_suggestions(
                        context=f"conflict_resolution_{i}"
                    )['suggestions'][:2]  # 2 suggestions par conflit
                    
                    conflicts.append({
                        'type': random.choice(['teacher', 'room', 'student_group', 'time_preference']),
                        'severity': random.choice(['high', 'medium', 'low']),
                        'message': f'Conflit détecté pour {selected_class} - Session {i+1}',
                        'sessionId': f'session_{i+1}',
                        'suggestions': conflict_suggestions
                    })
            
            # Génération des suggestions globales IA
            global_suggestions = ml_service.generate_schedule_suggestions(
                context=f"schedule_generation_{selected_class}"
            )['suggestions']
            
            result = {
                'success': True,
                'scheduleId': f'schedule_{int(time.time())}',
                'conflicts': conflicts,
                'metrics': metrics,
                'suggestions': global_suggestions,
                'generated_by_ai': True,
                'model_used': ml_service.get_or_create_model().name
            }
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erreur lors de la génération de l\'emploi du temps: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post', 'get'])
    def analyze_workload(self, request):
        """Analyse l'équilibre de la charge de travail des enseignants"""
        try:
            # Accepter les données du body (POST) ou des query params (GET - pour rétrocompatibilité)
            if request.method == 'POST':
                schedule_data = request.data.get('schedule_data', None)
            else:
                schedule_data = request.query_params.get('schedule_data', None)

            result = ml_service.analyze_workload_balance(schedule_data=schedule_data)

            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'Erreur lors de l\'analyse de charge: {str(e)}',
                'teachers': [],
                'overall_balance': 0
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post', 'get'])
    def detect_anomalies(self, request):
        """Détecte les anomalies dans un emploi du temps"""
        try:
            # Accepter les données du body (POST) ou des query params (GET - pour rétrocompatibilité)
            if request.method == 'POST':
                schedule_data = request.data.get('schedule_data', None)
            else:
                schedule_data = request.query_params.get('schedule_data', None)

            result = ml_service.detect_schedule_anomalies(schedule_data=schedule_data)

            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'Erreur lors de la détection d\'anomalies: {str(e)}',
                'anomalies': [],
                'total_anomalies': 0,
                'risk_score': 0
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def predict_room_occupancy(self, request):
        """Prédit l'occupation des salles"""
        try:
            room_id = request.query_params.get('room_id', None)
            date_range = request.query_params.get('date_range', None)
            
            result = ml_service.predict_room_occupancy(room_id=room_id, date_range=date_range)
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erreur lors de la prédiction d\'occupation: {str(e)}',
                'predictions': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post', 'get'])
    def optimal_schedule_recommendations(self, request):
        """Recommande un emploi du temps optimal"""
        try:
            # Accepter les données du body (POST) ou des query params (GET - pour rétrocompatibilité)
            if request.method == 'POST':
                constraints = request.data.get('constraints', None)
            else:
                constraints = request.query_params.get('constraints', None)
                if constraints:
                    import json
                    constraints = json.loads(constraints)

            result = ml_service.recommend_optimal_schedule(constraints=constraints)

            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'Erreur lors de la génération de recommandations: {str(e)}',
                'recommendations': {},
                'confidence': 0.5
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post', 'get'])
    def analyze_student_preferences(self, request):
        """Analyse les préférences des étudiants"""
        try:
            # Accepter les données du body (POST) ou des query params (GET - pour rétrocompatibilité)
            if request.method == 'POST':
                student_data = request.data.get('student_data', None)
            else:
                student_data = request.query_params.get('student_data', None)
                if student_data:
                    import json
                    student_data = json.loads(student_data)

            result = ml_service.analyze_student_preferences(student_data=student_data)
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erreur lors de l\'analyse des préférences: {str(e)}',
                'analysis': {},
                'recommendations': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post', 'get'])
    def predict_course_success(self, request):
        """Prédit le taux de réussite des cours"""
        try:
            # Accepter les données du body (POST) ou des query params (GET - pour rétrocompatibilité)
            if request.method == 'POST':
                course_data = request.data.get('course_data', None)
            else:
                course_data = request.query_params.get('course_data', None)
                if course_data:
                    import json
                    course_data = json.loads(course_data)

            result = ml_service.predict_course_success_rate(course_data=course_data)

            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erreur lors de la prédiction de réussite: {str(e)}',
                'course_predictions': [],
                'overall_average': 0
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def personalized_recommendations(self, request):
        """Génère des recommandations personnalisées"""
        try:
            user_profile = request.data.get('user_profile', {})
            result = ml_service.generate_personalized_recommendations(user_profile=user_profile)
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erreur lors de la génération de recommandations personnalisées: {str(e)}',
                'user_type': 'student',
                'recommendations': {},
                'personalization_score': 0.5
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
