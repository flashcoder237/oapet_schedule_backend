# schedules/serializers.py
from rest_framework import serializers
from .models import (
    AcademicPeriod, TimeSlot, Schedule, ScheduleSession, Conflict,
    ScheduleOptimization, ScheduleTemplate, ScheduleConstraint, ScheduleExport,
    ScheduleGenerationConfig, SessionOccurrence
)
from courses.serializers import CourseSerializer, TeacherSerializer
from courses.serializers_class import StudentClassListSerializer
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
    student_class_details = StudentClassListSerializer(source='student_class', read_only=True)
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
    student_class_details = StudentClassListSerializer(source='student_class', read_only=True)
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
    student_class = serializers.IntegerField(required=False)
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
    schedules_by_class = serializers.DictField()
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


class ScheduleGenerationConfigSerializer(serializers.ModelSerializer):
    """Serializer pour la configuration de génération d'emploi du temps"""
    schedule_name = serializers.CharField(source='schedule.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    recurrence_type_display = serializers.CharField(source='get_recurrence_type_display', read_only=True)
    flexibility_level_display = serializers.CharField(source='get_flexibility_level_display', read_only=True)
    optimization_priority_display = serializers.CharField(source='get_optimization_priority_display', read_only=True)
    duration_days = serializers.SerializerMethodField()
    excluded_dates_count = serializers.SerializerMethodField()
    special_weeks_count = serializers.SerializerMethodField()

    class Meta:
        model = ScheduleGenerationConfig
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

    def get_duration_days(self, obj):
        """Calcule la durée de génération en jours"""
        if obj.start_date and obj.end_date:
            return (obj.end_date - obj.start_date).days
        return 0

    def get_excluded_dates_count(self, obj):
        """Compte le nombre de dates exclues"""
        return len(obj.excluded_dates) if obj.excluded_dates else 0

    def get_special_weeks_count(self, obj):
        """Compte le nombre de semaines spéciales"""
        return len(obj.special_weeks) if obj.special_weeks else 0


class ScheduleGenerationConfigCreateSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour créer une configuration de génération"""
    class Meta:
        model = ScheduleGenerationConfig
        fields = [
            'schedule', 'start_date', 'end_date', 'recurrence_type', 'recurrence_pattern',
            'flexibility_level', 'allow_conflicts', 'max_sessions_per_day',
            'respect_teacher_preferences', 'respect_room_preferences',
            'optimization_priority', 'excluded_dates', 'special_weeks',
            # Nouvelles contraintes horaires
            'min_break_between_sessions', 'max_consecutive_sessions',
            'preferred_start_time', 'preferred_end_time',
            # Contraintes de charge de travail
            'max_hours_per_day_students', 'max_hours_per_week_students',
            # Contraintes enseignants
            'max_hours_per_day_teachers', 'min_rest_time_teachers',
            # Distribution des cours
            'distribute_evenly', 'avoid_single_sessions', 'group_same_subject',
            # Préférences de jours
            'preferred_days', 'excluded_days'
        ]

    def validate(self, data):
        """Valide les données de configuration"""
        if data['start_date'] >= data['end_date']:
            raise serializers.ValidationError("La date de fin doit être après la date de début")

        # Valide les dates exclues
        if 'excluded_dates' in data and data['excluded_dates']:
            from datetime import datetime
            for date_str in data['excluded_dates']:
                try:
                    datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    raise serializers.ValidationError(f"Format de date invalide: {date_str}")

        # Valide les semaines spéciales
        if 'special_weeks' in data and data['special_weeks']:
            for week in data['special_weeks']:
                if 'start_date' not in week or 'end_date' not in week:
                    raise serializers.ValidationError("Chaque semaine spéciale doit avoir start_date et end_date")

        return data


class SessionOccurrenceSerializer(serializers.ModelSerializer):
    """Serializer pour les occurrences de sessions"""
    session_template_details = ScheduleSessionSerializer(source='session_template', read_only=True)
    room_details = RoomSerializer(source='room', read_only=True)
    teacher_details = TeacherSerializer(source='teacher', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    course_code = serializers.CharField(source='session_template.course.code', read_only=True)
    course_name = serializers.CharField(source='session_template.course.name', read_only=True)
    duration_hours = serializers.SerializerMethodField()
    has_conflicts = serializers.SerializerMethodField()

    class Meta:
        model = SessionOccurrence
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'cancelled_at')

    def get_duration_hours(self, obj):
        """Retourne la durée en heures"""
        return obj.get_duration_hours()

    def get_has_conflicts(self, obj):
        """Vérifie s'il y a des conflits"""
        return len(obj.check_conflicts()) > 0


class SessionOccurrenceListSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour les listes d'occurrences"""
    course_code = serializers.CharField(source='session_template.course.code', read_only=True)
    course_name = serializers.CharField(source='session_template.course.name', read_only=True)
    room_code = serializers.CharField(source='room.code', read_only=True)
    teacher_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = SessionOccurrence
        fields = [
            'id', 'actual_date', 'start_time', 'end_time', 'status',
            'course_code', 'course_name', 'room_code', 'teacher_name',
            'status_display', 'is_cancelled', 'is_room_modified',
            'is_teacher_modified', 'is_time_modified'
        ]

    def get_teacher_name(self, obj):
        """Retourne le nom complet de l'enseignant"""
        return obj.teacher.user.get_full_name()


class SessionOccurrenceCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer une occurrence de session"""
    class Meta:
        model = SessionOccurrence
        fields = [
            'session_template', 'actual_date', 'start_time', 'end_time',
            'room', 'teacher', 'notes'
        ]

    def validate(self, data):
        """Valide les données de l'occurrence"""
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("L'heure de fin doit être après l'heure de début")

        # Vérifie si le template de session existe
        if 'session_template' not in data:
            raise serializers.ValidationError("Le template de session est obligatoire")

        return data


class SessionOccurrenceCancelSerializer(serializers.Serializer):
    """Serializer pour annuler une occurrence de session"""
    reason = serializers.CharField(required=True)
    notify_students = serializers.BooleanField(default=True)
    notify_teacher = serializers.BooleanField(default=True)


class SessionOccurrenceRescheduleSerializer(serializers.Serializer):
    """Serializer pour reprogrammer une occurrence de session"""
    new_date = serializers.DateField(required=True)
    new_start_time = serializers.TimeField(required=True)
    new_end_time = serializers.TimeField(required=True)
    new_room = serializers.IntegerField(required=False, allow_null=True)
    new_teacher = serializers.IntegerField(required=False, allow_null=True)
    reason = serializers.CharField(required=False)
    notify_students = serializers.BooleanField(default=True)
    notify_teacher = serializers.BooleanField(default=True)

    def validate(self, data):
        """Valide les données de reprogrammation"""
        if data['new_start_time'] >= data['new_end_time']:
            raise serializers.ValidationError("L'heure de fin doit être après l'heure de début")
        return data


class SessionOccurrenceModifySerializer(serializers.Serializer):
    """Serializer pour modifier une occurrence de session"""
    room = serializers.IntegerField(required=False, allow_null=True)
    teacher = serializers.IntegerField(required=False, allow_null=True)
    start_time = serializers.TimeField(required=False)
    end_time = serializers.TimeField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    notify_students = serializers.BooleanField(default=False)
    notify_teacher = serializers.BooleanField(default=False)


class DailyScheduleSerializer(serializers.Serializer):
    """Serializer pour l'affichage journalier des occurrences"""
    date = serializers.DateField()
    occurrences = SessionOccurrenceListSerializer(many=True)
    total_sessions = serializers.IntegerField()
    cancelled_sessions = serializers.IntegerField()
    conflicts_count = serializers.IntegerField()


class WeeklyOccurrencesSerializer(serializers.Serializer):
    """Serializer pour l'affichage hebdomadaire des occurrences"""
    week_start = serializers.DateField()
    week_end = serializers.DateField()
    days = serializers.DictField(child=DailyScheduleSerializer())
    total_sessions = serializers.IntegerField()
    total_hours = serializers.FloatField()


class ScheduleGenerationRequestSerializer(serializers.Serializer):
    """Serializer pour les requêtes de génération d'emploi du temps"""
    schedule_id = serializers.IntegerField()
    preview_mode = serializers.BooleanField(default=False)
    force_regenerate = serializers.BooleanField(default=False)
    preserve_modifications = serializers.BooleanField(default=True)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)


class ScheduleGenerationResponseSerializer(serializers.Serializer):
    """Serializer pour les réponses de génération d'emploi du temps"""
    success = serializers.BooleanField()
    message = serializers.CharField()
    occurrences_created = serializers.IntegerField()
    conflicts_detected = serializers.IntegerField()
    conflicts = serializers.ListField(child=serializers.DictField(), required=False)
    preview_data = serializers.DictField(required=False)
    generation_time = serializers.FloatField()