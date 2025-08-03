# ml_engine/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TimetableDatasetViewSet, MLModelViewSet, ModelTrainingTaskViewSet,
    PredictionRequestViewSet, PredictionHistoryViewSet, ModelPerformanceMetricViewSet
)

router = DefaultRouter()
router.register(r'datasets', TimetableDatasetViewSet)
router.register(r'models', MLModelViewSet)
router.register(r'training-tasks', ModelTrainingTaskViewSet)
router.register(r'predictions', PredictionRequestViewSet)
router.register(r'prediction-history', PredictionHistoryViewSet)
router.register(r'performance-metrics', ModelPerformanceMetricViewSet)

urlpatterns = [
    path('', include(router.urls)),
]