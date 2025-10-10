from django.contrib import admin
from .models import (
    AcademicPeriod, TimeSlot, Schedule, ScheduleSession,
    Conflict, ScheduleOptimization, ScheduleTemplate,
    ScheduleConstraint, ScheduleExport, ScheduleGenerationConfig,
    SessionOccurrence
)


@admin.register(AcademicPeriod)
class AcademicPeriodAdmin(admin.ModelAdmin):
    list_display = ['name', 'academic_year', 'semester', 'start_date', 'end_date', 'is_current']
    list_filter = ['academic_year', 'semester', 'is_current']
    search_fields = ['name', 'academic_year']


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ['day_of_week', 'start_time', 'end_time', 'name', 'is_active']
    list_filter = ['day_of_week', 'is_active']
    ordering = ['day_of_week', 'start_time']


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ['name', 'academic_period', 'schedule_type', 'status', 'is_published', 'created_at']
    list_filter = ['status', 'schedule_type', 'is_published', 'academic_period']
    search_fields = ['name', 'description']
    readonly_fields = ['total_hours', 'utilization_rate', 'conflict_score', 'quality_score', 'created_at', 'updated_at']


@admin.register(ScheduleSession)
class ScheduleSessionAdmin(admin.ModelAdmin):
    list_display = ['course', 'teacher', 'room', 'time_slot', 'session_type', 'is_cancelled']
    list_filter = ['session_type', 'is_cancelled', 'schedule']
    search_fields = ['course__code', 'course__name', 'teacher__user__first_name', 'teacher__user__last_name']
    raw_id_fields = ['schedule', 'course', 'room', 'teacher', 'time_slot']


@admin.register(Conflict)
class ConflictAdmin(admin.ModelAdmin):
    list_display = ['schedule_session', 'conflict_type', 'severity', 'is_resolved', 'detected_at']
    list_filter = ['conflict_type', 'severity', 'is_resolved']
    search_fields = ['description']
    readonly_fields = ['detected_at', 'resolved_at']


@admin.register(ScheduleOptimization)
class ScheduleOptimizationAdmin(admin.ModelAdmin):
    list_display = ['schedule', 'optimization_type', 'conflicts_before', 'conflicts_after', 'optimization_score', 'started_at']
    list_filter = ['optimization_type', 'convergence_achieved']
    readonly_fields = ['started_at', 'completed_at']


@admin.register(ScheduleTemplate)
class ScheduleTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'curriculum', 'level', 'usage_count', 'success_rate', 'is_active']
    list_filter = ['level', 'is_active', 'curriculum']
    search_fields = ['name', 'description']


@admin.register(ScheduleConstraint)
class ScheduleConstraintAdmin(admin.ModelAdmin):
    list_display = ['name', 'schedule', 'constraint_type', 'priority', 'is_hard_constraint', 'is_active']
    list_filter = ['constraint_type', 'priority', 'is_hard_constraint', 'is_active']
    search_fields = ['name', 'description']


@admin.register(ScheduleExport)
class ScheduleExportAdmin(admin.ModelAdmin):
    list_display = ['schedule', 'export_format', 'exported_by', 'exported_at', 'file_size']
    list_filter = ['export_format', 'exported_at']
    readonly_fields = ['exported_at']


@admin.register(ScheduleGenerationConfig)
class ScheduleGenerationConfigAdmin(admin.ModelAdmin):
    list_display = ['schedule', 'start_date', 'end_date', 'recurrence_type', 'flexibility_level', 'is_active']
    list_filter = ['recurrence_type', 'flexibility_level', 'optimization_priority', 'is_active']
    search_fields = ['schedule__name']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Informations principales', {
            'fields': ('schedule', 'start_date', 'end_date', 'is_active')
        }),
        ('Paramètres de récurrence', {
            'fields': ('recurrence_type', 'recurrence_pattern')
        }),
        ('Paramètres de génération', {
            'fields': (
                'flexibility_level', 'allow_conflicts', 'max_sessions_per_day',
                'respect_teacher_preferences', 'respect_room_preferences', 'optimization_priority'
            )
        }),
        ('Exclusions et semaines spéciales', {
            'fields': ('excluded_dates', 'special_weeks')
        }),
        ('Métadonnées', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SessionOccurrence)
class SessionOccurrenceAdmin(admin.ModelAdmin):
    list_display = ['session_template', 'actual_date', 'start_time', 'end_time', 'room', 'teacher', 'status']
    list_filter = ['status', 'actual_date', 'is_cancelled', 'is_room_modified', 'is_teacher_modified']
    search_fields = [
        'session_template__course__code',
        'session_template__course__name',
        'teacher__user__first_name',
        'teacher__user__last_name'
    ]
    raw_id_fields = ['session_template', 'room', 'teacher', 'cancelled_by', 'rescheduled_from']
    readonly_fields = ['created_at', 'updated_at', 'cancelled_at']
    date_hierarchy = 'actual_date'

    fieldsets = (
        ('Informations de base', {
            'fields': ('session_template', 'actual_date', 'start_time', 'end_time', 'status')
        }),
        ('Ressources', {
            'fields': ('room', 'teacher')
        }),
        ('Suivi', {
            'fields': ('attendance_count', 'notes')
        }),
        ('Modifications', {
            'fields': ('is_room_modified', 'is_teacher_modified', 'is_time_modified')
        }),
        ('Annulation', {
            'fields': ('is_cancelled', 'cancellation_reason', 'cancelled_at', 'cancelled_by'),
            'classes': ('collapse',)
        }),
        ('Reprogrammation', {
            'fields': ('rescheduled_from',),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_as_completed', 'mark_as_cancelled']

    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status='completed')
        self.message_user(request, f'{updated} occurrence(s) marquée(s) comme terminée(s).')
    mark_as_completed.short_description = 'Marquer comme terminé'

    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled', is_cancelled=True)
        self.message_user(request, f'{updated} occurrence(s) annulée(s).')
    mark_as_cancelled.short_description = 'Annuler'
