# schedules/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AcademicPeriodViewSet, TimeSlotViewSet, ScheduleViewSet, ScheduleSessionViewSet,
    ConflictViewSet, ScheduleOptimizationViewSet, ScheduleTemplateViewSet,
    ScheduleConstraintViewSet, ScheduleExportViewSet
)
from .views_generation import (
    ScheduleGenerationConfigViewSet, SessionOccurrenceViewSet,
    ScheduleGenerationViewSet
)

router = DefaultRouter()
router.register(r'schedules', ScheduleViewSet)
router.register(r'academic-periods', AcademicPeriodViewSet)
router.register(r'time-slots', TimeSlotViewSet)
router.register(r'sessions', ScheduleSessionViewSet)
router.register(r'conflicts', ConflictViewSet)
router.register(r'optimizations', ScheduleOptimizationViewSet)
router.register(r'templates', ScheduleTemplateViewSet)
router.register(r'constraints', ScheduleConstraintViewSet)
router.register(r'exports', ScheduleExportViewSet)

# Nouvelles routes pour la génération dynamique
router.register(r'generation-configs', ScheduleGenerationConfigViewSet, basename='generation-config')
router.register(r'occurrences', SessionOccurrenceViewSet, basename='occurrence')
router.register(r'generation', ScheduleGenerationViewSet, basename='generation')


urlpatterns = [
    path('', include(router.urls)),
]