# courses/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DepartmentViewSet, TeacherViewSet, CourseViewSet, CurriculumViewSet,
    StudentViewSet, CourseEnrollmentViewSet, CoursePrerequisiteViewSet,
    TeacherPreferenceViewSet, TeacherUnavailabilityViewSet,
    TeacherScheduleRequestViewSet, SessionFeedbackViewSet
)
from .views_class import StudentClassViewSet, ClassCourseViewSet, ClassRoomPreferenceViewSet

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet)
router.register(r'teachers', TeacherViewSet)
router.register(r'courses', CourseViewSet)
router.register(r'curricula', CurriculumViewSet)
router.register(r'students', StudentViewSet)
router.register(r'enrollments', CourseEnrollmentViewSet)
router.register(r'prerequisites', CoursePrerequisiteViewSet)
router.register(r'teacher-preferences', TeacherPreferenceViewSet, basename='teacher-preference')
router.register(r'teacher-unavailabilities', TeacherUnavailabilityViewSet, basename='teacher-unavailability')
router.register(r'teacher-schedule-requests', TeacherScheduleRequestViewSet, basename='teacher-schedule-request')
router.register(r'session-feedbacks', SessionFeedbackViewSet, basename='session-feedback')

# Routes pour les classes
router.register(r'classes', StudentClassViewSet, basename='class')
router.register(r'class-courses', ClassCourseViewSet, basename='class-course')
router.register(r'class-room-preferences', ClassRoomPreferenceViewSet, basename='class-room-preference')

urlpatterns = [
    path('', include(router.urls)),
]