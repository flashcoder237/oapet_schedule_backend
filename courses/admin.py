from django.contrib import admin
from .models import (
    Department, Teacher, Course, Curriculum, CurriculumCourse,
    Student, CourseEnrollment, CoursePrerequisite,
    TeacherPreference, TeacherUnavailability, TeacherScheduleRequest, SessionFeedback
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'head_of_department', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'user', 'department', 'max_hours_per_week', 'is_active']
    list_filter = ['department', 'is_active']
    search_fields = ['employee_id', 'user__first_name', 'user__last_name']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'course_type', 'level', 'teacher', 'department', 'is_active']
    list_filter = ['course_type', 'level', 'department', 'is_active']
    search_fields = ['code', 'name']


@admin.register(Curriculum)
class CurriculumAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'level', 'department', 'is_active']
    list_filter = ['level', 'department', 'is_active']
    search_fields = ['code', 'name']


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'user', 'curriculum', 'current_level', 'is_active']
    list_filter = ['curriculum', 'current_level', 'is_active']
    search_fields = ['student_id', 'user__first_name', 'user__last_name']


@admin.register(TeacherPreference)
class TeacherPreferenceAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'preference_type', 'priority', 'is_active', 'created_at']
    list_filter = ['preference_type', 'priority', 'is_active']
    search_fields = ['teacher__user__first_name', 'teacher__user__last_name', 'reason']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Informations principales', {
            'fields': ('teacher', 'preference_type', 'priority', 'is_active')
        }),
        ('Données de préférence', {
            'fields': ('preference_data', 'reason')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TeacherUnavailability)
class TeacherUnavailabilityAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'unavailability_type', 'is_approved', 'approved_by', 'created_at']
    list_filter = ['unavailability_type', 'is_approved']
    search_fields = ['teacher__user__first_name', 'teacher__user__last_name', 'reason']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Informations principales', {
            'fields': ('teacher', 'unavailability_type', 'reason')
        }),
        ('Indisponibilité temporaire', {
            'fields': ('start_date', 'end_date'),
            'description': 'Utilisé pour les indisponibilités temporaires'
        }),
        ('Indisponibilité récurrente', {
            'fields': ('day_of_week', 'start_time', 'end_time'),
            'description': 'Utilisé pour les indisponibilités récurrentes'
        }),
        ('Approbation', {
            'fields': ('is_approved', 'approved_by')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if obj.is_approved and not obj.approved_by:
            obj.approved_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TeacherScheduleRequest)
class TeacherScheduleRequestAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'request_type', 'status', 'priority', 'created_at', 'reviewed_by']
    list_filter = ['request_type', 'status', 'priority', 'created_at']
    search_fields = ['teacher__user__first_name', 'teacher__user__last_name', 'current_situation', 'requested_change']
    readonly_fields = ['created_at', 'updated_at', 'reviewed_at']

    fieldsets = (
        ('Informations principales', {
            'fields': ('teacher', 'request_type', 'session', 'status', 'priority')
        }),
        ('Détails de la demande', {
            'fields': ('current_situation', 'requested_change', 'reason', 'change_data')
        }),
        ('Révision', {
            'fields': ('reviewed_by', 'reviewed_at', 'review_notes')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if obj.status in ['approved', 'rejected'] and not obj.reviewed_by:
            obj.reviewed_by = request.user
            from django.utils import timezone
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(SessionFeedback)
class SessionFeedbackAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'session', 'feedback_type', 'issue_type', 'severity', 'is_resolved', 'created_at']
    list_filter = ['feedback_type', 'issue_type', 'severity', 'is_resolved', 'created_at']
    search_fields = ['teacher__user__first_name', 'teacher__user__last_name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'resolved_at']

    fieldsets = (
        ('Informations principales', {
            'fields': ('teacher', 'session', 'feedback_type')
        }),
        ('Détails du retour', {
            'fields': ('issue_type', 'severity', 'description')
        }),
        ('Résolution', {
            'fields': ('is_resolved', 'resolved_by', 'resolved_at', 'resolution_notes')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if obj.is_resolved and not obj.resolved_by:
            obj.resolved_by = request.user
            from django.utils import timezone
            obj.resolved_at = timezone.now()
        super().save_model(request, obj, form, change)


admin.site.register(CurriculumCourse)
admin.site.register(CourseEnrollment)
admin.site.register(CoursePrerequisite)
