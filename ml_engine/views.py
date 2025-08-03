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
from .services import TimetableDataProcessor, MLTrainingService, TimetablePredictor


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
        
        if not dataset_id:
            return Response({
                'error': 'dataset_id est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            dataset = get_object_or_404(TimetableDataset, id=dataset_id)
            
            # Démarrer la tâche d'entraînement
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
        
        task.status = 'failed'
        task.logs += f'\nTâche annulée par {request.user.username} à {timezone.now()}'
        task.save()
        
        return Response({
            'message': 'Tâche annulée avec succès'
        }, status=status.HTTP_200_OK)


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
            
            # Effectuer la prédiction
            predictor = TimetablePredictor(active_model)
            result = predictor.predict_difficulty(
                course_data=serializer.validated_data,
                user=request.user
            )
            
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
