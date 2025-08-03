# courses/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DepartmentViewSet, TeacherViewSet, CourseViewSet, CurriculumViewSet,
    StudentViewSet, CourseEnrollmentViewSet, CoursePrerequisiteViewSet
)

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet)
router.register(r'teachers', TeacherViewSet)
router.register(r'courses', CourseViewSet)
router.register(r'curricula', CurriculumViewSet)
router.register(r'students', StudentViewSet)
router.register(r'enrollments', CourseEnrollmentViewSet)
router.register(r'prerequisites', CoursePrerequisiteViewSet)

urlpatterns = [
    path('', include(router.urls)),
]