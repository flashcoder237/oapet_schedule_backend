# schedules/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AcademicPeriodViewSet, TimeSlotViewSet, ScheduleViewSet, ScheduleSessionViewSet,
    ConflictViewSet, ScheduleOptimizationViewSet, ScheduleTemplateViewSet,
    ScheduleConstraintViewSet, ScheduleExportViewSet
)

router = DefaultRouter()
router.register(r'academic-periods', AcademicPeriodViewSet)
router.register(r'time-slots', TimeSlotViewSet)
router.register(r'schedules', ScheduleViewSet)
router.register(r'sessions', ScheduleSessionViewSet)
router.register(r'conflicts', ConflictViewSet)
router.register(r'optimizations', ScheduleOptimizationViewSet)
router.register(r'templates', ScheduleTemplateViewSet)
router.register(r'constraints', ScheduleConstraintViewSet)
router.register(r'exports', ScheduleExportViewSet)

urlpatterns = [
    path('', include(router.urls)),
]