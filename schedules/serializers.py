# schedules/serializers.py
from rest_framework import serializers
from .models import (
    AcademicPeriod, TimeSlot, Schedule, ScheduleSession, Conflict,
    ScheduleOptimization, ScheduleTemplate, ScheduleConstraint, ScheduleExport
)
from courses.serializers import CourseSerializer, TeacherSerializer, CurriculumSerializer
from rooms.serializers import RoomSerializer


class AcademicPeriodSerializer(serializers.ModelSerializer):
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = AcademicPeriod
        fields = '__all__'
        read_only_fields = ('created_at',)
    
    def get_duration(self, obj):
        """Calcule la durée de la période en jours"""
        if obj.start_date and obj.end_date:
            duration = obj.end_date - obj.start_date
            return duration.days
        return None


class TimeSlotSerializer(serializers.ModelSerializer):
    day_display = serializers.CharField(source='get_day_of_week_display', read_only=True)
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = TimeSlot
        fields = '__all__'
    
    def get_duration(self, obj):
        """Calcule la durée du créneau en minutes"""
        if obj.start_time and obj.end_time:
            start_minutes = obj.start_time.hour * 60 + obj.start_time.minute
            end_minutes = obj.end_time.hour * 60 + obj.end_time.minute
            return end_minutes - start_minutes
        return None


class ScheduleSessionSerializer(serializers.ModelSerializer):
    course_details = CourseSerializer(source='course', read_only=True)
    teacher_details = TeacherSerializer(source='teacher', read_only=True)
    room_details = RoomSerializer(source='room', read_only=True)
    time_slot_details = TimeSlotSerializer(source='time_slot', read_only=True)
    session_type_display = serializers.CharField(source='get_session_type_display', read_only=True)
    
    class Meta:
        model = ScheduleSession
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class ScheduleSessionCreateSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour la création de sessions"""
    class Meta:
        model = ScheduleSession
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class ConflictSerializer(serializers.ModelSerializer):
    schedule_session_details = ScheduleSessionSerializer(source='schedule_session', read_only=True)
    conflicting_session_details = ScheduleSessionSerializer(source='conflicting_session', read_only=True)
    conflict_type_display = serializers.CharField(source='get_conflict_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    
    class Meta:
        model = Conflict
        fields = '__all__'
        read_only_fields = ('detected_at', 'resolved_at')


class ScheduleSerializer(serializers.ModelSerializer):
    academic_period_details = AcademicPeriodSerializer(source='academic_period', read_only=True)
    curriculum_details = CurriculumSerializer(source='curriculum', read_only=True)
    teacher_details = TeacherSerializer(source='teacher', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    sessions_count = serializers.IntegerField(source='sessions.count', read_only=True)
    conflicts_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Schedule
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'published_at')
    
    def get_conflicts_count(self, obj):
        """Compte les conflits non résolus dans l'emploi du temps"""
        return Conflict.objects.filter(
            schedule_session__schedule=obj,
            is_resolved=False
        ).count()


class ScheduleDetailSerializer(ScheduleSerializer):
    """Serializer détaillé pour les emplois du temps avec sessions"""
    sessions = ScheduleSessionSerializer(many=True, read_only=True)
    unresolved_conflicts = serializers.SerializerMethodField()
    optimization_summary = serializers.SerializerMethodField()
    
    def get_unresolved_conflicts(self, obj):
        """Retourne les conflits non résolus"""
        conflicts = Conflict.objects.filter(
            schedule_session__schedule=obj,
            is_resolved=False
        )
        return ConflictSerializer(conflicts, many=True).data
    
    def get_optimization_summary(self, obj):
        """Résumé des optimisations"""
        latest_optimization = obj.optimizations.first()
        if latest_optimization:
            return {
                'last_optimization': latest_optimization.started_at,
                'optimization_score': latest_optimization.optimization_score,
                'conflicts_resolved': latest_optimization.conflicts_before - latest_optimization.conflicts_after
            }
        return None


class ScheduleOptimizationSerializer(serializers.ModelSerializer):
    schedule_name = serializers.CharField(source='schedule.name', read_only=True)
    started_by_name = serializers.CharField(source='started_by.username', read_only=True)
    optimization_type_display = serializers.CharField(source='get_optimization_type_display', read_only=True)
    improvement = serializers.SerializerMethodField()
    
    class Meta:
        model = ScheduleOptimization
        fields = '__all__'
        read_only_fields = ('started_at', 'completed_at')
    
    def get_improvement(self, obj):
        """Calcule l'amélioration en pourcentage"""
        if obj.conflicts_before > 0:
            improvement = ((obj.conflicts_before - obj.conflicts_after) / obj.conflicts_before) * 100
            return round(improvement, 2)
        return 0


class ScheduleTemplateSerializer(serializers.ModelSerializer):
    curriculum_details = CurriculumSerializer(source='curriculum', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    
    class Meta:
        model = ScheduleTemplate
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'usage_count')


class ScheduleConstraintSerializer(serializers.ModelSerializer):
    schedule_name = serializers.CharField(source='schedule.name', read_only=True)
    constraint_type_display = serializers.CharField(source='get_constraint_type_display', read_only=True)
    
    class Meta:
        model = ScheduleConstraint
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class ScheduleExportSerializer(serializers.ModelSerializer):
    schedule_name = serializers.CharField(source='schedule.name', read_only=True)
    exported_by_name = serializers.CharField(source='exported_by.username', read_only=True)
    export_format_display = serializers.CharField(source='get_export_format_display', read_only=True)
    file_size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = ScheduleExport
        fields = '__all__'
        read_only_fields = ('exported_at',)
    
    def get_file_size_mb(self, obj):
        """Convertit la taille du fichier en MB"""
        if obj.file_size:
            return round(obj.file_size / (1024 * 1024), 2)
        return 0


class ScheduleCreateSerializer(serializers.Serializer):
    """Serializer pour la création d'emplois du temps avec paramètres"""
    name = serializers.CharField(max_length=200)
    academic_period = serializers.IntegerField()
    curriculum = serializers.IntegerField(required=False)
    teacher = serializers.IntegerField(required=False)
    level = serializers.CharField(max_length=5, required=False)
    description = serializers.CharField(required=False)
    template = serializers.IntegerField(required=False)
    auto_optimize = serializers.BooleanField(default=True)
    optimization_parameters = serializers.DictField(required=False)


class ScheduleStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques des emplois du temps"""
    total_schedules = serializers.IntegerField()
    published_schedules = serializers.IntegerField()
    schedules_by_level = serializers.DictField()
    schedules_by_curriculum = serializers.DictField()
    average_sessions_per_schedule = serializers.FloatField()
    total_conflicts = serializers.IntegerField()
    unresolved_conflicts = serializers.IntegerField()
    optimization_stats = serializers.DictField()


class WeeklyScheduleSerializer(serializers.Serializer):
    """Serializer pour l'affichage hebdomadaire des emplois du temps"""
    monday = serializers.ListField(child=ScheduleSessionSerializer())
    tuesday = serializers.ListField(child=ScheduleSessionSerializer())
    wednesday = serializers.ListField(child=ScheduleSessionSerializer())
    thursday = serializers.ListField(child=ScheduleSessionSerializer())
    friday = serializers.ListField(child=ScheduleSessionSerializer())
    saturday = serializers.ListField(child=ScheduleSessionSerializer())
    sunday = serializers.ListField(child=ScheduleSessionSerializer())


class ScheduleValidationSerializer(serializers.Serializer):
    """Serializer pour la validation des emplois du temps"""
    is_valid = serializers.BooleanField()
    conflicts = serializers.ListField(child=ConflictSerializer())
    warnings = serializers.ListField(child=serializers.CharField())
    recommendations = serializers.ListField(child=serializers.CharField())
    validation_score = serializers.FloatField()


class BulkScheduleActionSerializer(serializers.Serializer):
    """Serializer pour les actions en lot sur les emplois du temps"""
    schedule_ids = serializers.ListField(child=serializers.IntegerField())
    action = serializers.ChoiceField(choices=[
        ('publish', 'Publier'),
        ('unpublish', 'Dépublier'),
        ('optimize', 'Optimiser'),
        ('export', 'Exporter'),
        ('delete', 'Supprimer')
    ])
    parameters = serializers.DictField(required=False)