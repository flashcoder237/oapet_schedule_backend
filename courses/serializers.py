# courses/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Department, Teacher, Course, Curriculum, CurriculumCourse,
    Student, CourseEnrollment, CoursePrerequisite,
    TeacherPreference, TeacherUnavailability, TeacherScheduleRequest, SessionFeedback
)


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name']
        read_only_fields = ['id']


class DepartmentSerializer(serializers.ModelSerializer):
    head_of_department_name = serializers.CharField(
        source='head_of_department.get_full_name', 
        read_only=True
    )
    teachers_count = serializers.IntegerField(
        source='teachers.count', 
        read_only=True
    )
    courses_count = serializers.IntegerField(
        source='courses.count', 
        read_only=True
    )
    
    class Meta:
        model = Department
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class TeacherSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    courses_count = serializers.IntegerField(source='courses.count', read_only=True)
    
    class Meta:
        model = Teacher
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class TeacherCreateSerializer(serializers.ModelSerializer):
    """Serializer spécialisé pour la création d'enseignants"""
    user = UserSerializer()
    
    class Meta:
        model = Teacher
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
    
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = User.objects.create_user(**user_data)
        teacher = Teacher.objects.create(user=user, **validated_data)
        return teacher


class CourseSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    enrollments_count = serializers.IntegerField(source='enrollments.count', read_only=True)
    
    class Meta:
        model = Course
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class CourseDetailSerializer(CourseSerializer):
    """Serializer détaillé pour les cours avec informations supplémentaires"""
    prerequisites = serializers.SerializerMethodField()
    prerequisite_for = serializers.SerializerMethodField()
    
    def get_prerequisites(self, obj):
        """Retourne les prérequis du cours"""
        prerequisites = CoursePrerequisite.objects.filter(course=obj)
        return [{
            'course_code': prereq.prerequisite_course.code,
            'course_name': prereq.prerequisite_course.name,
            'is_mandatory': prereq.is_mandatory
        } for prereq in prerequisites]
    
    def get_prerequisite_for(self, obj):
        """Retourne les cours pour lesquels ce cours est un prérequis"""
        prerequisite_for = CoursePrerequisite.objects.filter(prerequisite_course=obj)
        return [{
            'course_code': prereq.course.code,
            'course_name': prereq.course.name,
            'is_mandatory': prereq.is_mandatory
        } for prereq in prerequisite_for]


class CurriculumCourseSerializer(serializers.ModelSerializer):
    course_details = CourseSerializer(source='course', read_only=True)
    
    class Meta:
        model = CurriculumCourse
        fields = '__all__'


class CurriculumSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    students_count = serializers.IntegerField(source='students.count', read_only=True)
    courses_count = serializers.IntegerField(source='courses.count', read_only=True)
    
    class Meta:
        model = Curriculum
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class CurriculumDetailSerializer(CurriculumSerializer):
    """Serializer détaillé pour les curriculums avec leurs cours"""
    curriculum_courses = CurriculumCourseSerializer(
        source='curriculumcourse_set', 
        many=True, 
        read_only=True
    )


class StudentSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)
    curriculum_name = serializers.CharField(source='curriculum.name', read_only=True)
    enrollments_count = serializers.IntegerField(source='enrollments.count', read_only=True)
    
    class Meta:
        model = Student
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class StudentCreateSerializer(serializers.ModelSerializer):
    """Serializer spécialisé pour la création d'étudiants"""
    user = UserSerializer()
    
    class Meta:
        model = Student
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
    
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = User.objects.create_user(**user_data)
        student = Student.objects.create(user=user, **validated_data)
        return student


class CourseEnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_id = serializers.CharField(source='student.student_id', read_only=True)
    course_name = serializers.CharField(source='course.name', read_only=True)
    course_code = serializers.CharField(source='course.code', read_only=True)
    
    class Meta:
        model = CourseEnrollment
        fields = '__all__'
        read_only_fields = ('enrollment_date',)


class CoursePrerequisiteSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.name', read_only=True)
    course_code = serializers.CharField(source='course.code', read_only=True)
    prerequisite_course_name = serializers.CharField(source='prerequisite_course.name', read_only=True)
    prerequisite_course_code = serializers.CharField(source='prerequisite_course.code', read_only=True)
    
    class Meta:
        model = CoursePrerequisite
        fields = '__all__'


class CourseStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques des cours"""
    total_courses = serializers.IntegerField()
    courses_by_level = serializers.DictField()
    courses_by_type = serializers.DictField()
    courses_by_department = serializers.DictField()
    average_hours_per_week = serializers.FloatField()
    total_enrollments = serializers.IntegerField()


class TeacherStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques des enseignants"""
    total_teachers = serializers.IntegerField()
    teachers_by_department = serializers.DictField()
    average_courses_per_teacher = serializers.FloatField()
    average_hours_per_teacher = serializers.FloatField()


class DepartmentStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques des départements"""
    total_departments = serializers.IntegerField()
    teachers_distribution = serializers.DictField()
    courses_distribution = serializers.DictField()
    students_distribution = serializers.DictField()


class TeacherPreferenceSerializer(serializers.ModelSerializer):
    """Serializer pour les préférences des enseignants"""
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)
    preference_type_display = serializers.CharField(source='get_preference_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = TeacherPreference
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class TeacherPreferenceCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer des préférences enseignants avec validation"""

    class Meta:
        model = TeacherPreference
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

    def validate_preference_data(self, value):
        """Valide les données de préférence selon le type"""
        preference_type = self.initial_data.get('preference_type')

        if preference_type == 'time_slot':
            required_fields = ['day', 'start_time', 'end_time']
            for field in required_fields:
                if field not in value:
                    raise serializers.ValidationError(
                        f"Le champ '{field}' est requis pour le type 'time_slot'"
                    )

        elif preference_type == 'day':
            if 'day' not in value:
                raise serializers.ValidationError(
                    "Le champ 'day' est requis pour le type 'day'"
                )

        elif preference_type == 'max_hours_per_day':
            if 'max_hours' not in value:
                raise serializers.ValidationError(
                    "Le champ 'max_hours' est requis pour le type 'max_hours_per_day'"
                )

        elif preference_type == 'consecutive_days':
            if 'max_consecutive_days' not in value:
                raise serializers.ValidationError(
                    "Le champ 'max_consecutive_days' est requis pour le type 'consecutive_days'"
                )

        elif preference_type == 'avoid_time':
            required_fields = ['day', 'start_time', 'end_time']
            for field in required_fields:
                if field not in value:
                    raise serializers.ValidationError(
                        f"Le champ '{field}' est requis pour le type 'avoid_time'"
                    )

        elif preference_type == 'room':
            if 'room_id' not in value:
                raise serializers.ValidationError(
                    "Le champ 'room_id' est requis pour le type 'room'"
                )

        return value


class TeacherUnavailabilitySerializer(serializers.ModelSerializer):
    """Serializer pour les indisponibilités des enseignants"""
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)
    unavailability_type_display = serializers.CharField(source='get_unavailability_type_display', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, allow_null=True)

    class Meta:
        model = TeacherUnavailability
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'approved_by')


class TeacherUnavailabilityCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer des indisponibilités avec validation"""

    class Meta:
        model = TeacherUnavailability
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'approved_by', 'is_approved')

    def validate(self, data):
        """Valide les données selon le type d'indisponibilité"""
        unavailability_type = data.get('unavailability_type')

        if unavailability_type == 'temporary':
            if not data.get('start_date') or not data.get('end_date'):
                raise serializers.ValidationError(
                    "Les dates de début et fin sont requises pour les indisponibilités temporaires"
                )
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError(
                    "La date de début doit être antérieure à la date de fin"
                )

        elif unavailability_type == 'recurring':
            if not data.get('day_of_week') or not data.get('start_time') or not data.get('end_time'):
                raise serializers.ValidationError(
                    "Le jour, heure de début et heure de fin sont requis pour les indisponibilités récurrentes"
                )
            if data['start_time'] >= data['end_time']:
                raise serializers.ValidationError(
                    "L'heure de début doit être antérieure à l'heure de fin"
                )

        return data


class TeacherDetailWithPreferencesSerializer(TeacherSerializer):
    """Serializer détaillé incluant les préférences et indisponibilités"""
    preferences = TeacherPreferenceSerializer(many=True, read_only=True)
    unavailabilities = TeacherUnavailabilitySerializer(many=True, read_only=True)
    active_preferences_count = serializers.SerializerMethodField()
    approved_unavailabilities_count = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = '__all__'

    def get_active_preferences_count(self, obj):
        return obj.preferences.filter(is_active=True).count()

    def get_approved_unavailabilities_count(self, obj):
        return obj.unavailabilities.filter(is_approved=True).count()


class TeacherScheduleRequestSerializer(serializers.ModelSerializer):
    """Serializer pour les demandes de modification d'emploi du temps"""
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)
    request_type_display = serializers.CharField(source='get_request_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True, allow_null=True)

    # Informations sur la session si elle existe
    session_details = serializers.SerializerMethodField()

    class Meta:
        model = TeacherScheduleRequest
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'reviewed_by', 'reviewed_at')

    def get_session_details(self, obj):
        """Retourne les détails de la session concernée"""
        if obj.session:
            return {
                'id': obj.session.id,
                'course_name': obj.session.course.name,
                'course_code': obj.session.course.code,
                'room': obj.session.room.code,
                'day': obj.session.time_slot.day_of_week,
                'start_time': obj.session.time_slot.start_time.strftime('%H:%M'),
                'end_time': obj.session.time_slot.end_time.strftime('%H:%M'),
                'session_type': obj.session.session_type
            }
        return None


class TeacherScheduleRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer des demandes de modification avec validation"""

    class Meta:
        model = TeacherScheduleRequest
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'reviewed_by', 'reviewed_at', 'status', 'review_notes')

    def validate(self, data):
        """Valide les données de la demande"""
        request_type = data.get('request_type')

        # Certains types de demande nécessitent une session
        if request_type in ['schedule_change', 'room_change', 'session_cancellation', 'time_swap']:
            if not data.get('session'):
                raise serializers.ValidationError(
                    f"Une session doit être spécifiée pour le type de demande '{request_type}'"
                )

        # Valider les données de changement
        change_data = data.get('change_data', {})
        if request_type == 'schedule_change' and not change_data.get('new_time_slot_id'):
            raise serializers.ValidationError(
                "Le nouveau créneau horaire doit être spécifié dans change_data.new_time_slot_id"
            )

        if request_type == 'room_change' and not change_data.get('new_room_id'):
            raise serializers.ValidationError(
                "La nouvelle salle doit être spécifiée dans change_data.new_room_id"
            )

        if request_type == 'time_swap':
            if not change_data.get('swap_with_session_id'):
                raise serializers.ValidationError(
                    "La session à échanger doit être spécifiée dans change_data.swap_with_session_id"
                )

        return data


class SessionFeedbackSerializer(serializers.ModelSerializer):
    """Serializer pour les retours sur les sessions"""
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)
    feedback_type_display = serializers.CharField(source='get_feedback_type_display', read_only=True)
    issue_type_display = serializers.CharField(source='get_issue_type_display', read_only=True, allow_null=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True, allow_null=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True, allow_null=True)

    # Détails de la session
    session_details = serializers.SerializerMethodField()

    class Meta:
        model = SessionFeedback
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'resolved_by', 'resolved_at', 'is_resolved', 'resolution_notes')

    def get_session_details(self, obj):
        """Retourne les détails de la session"""
        return {
            'id': obj.session.id,
            'course_name': obj.session.course.name,
            'course_code': obj.session.course.code,
            'room': obj.session.room.code,
            'day': obj.session.time_slot.day_of_week,
            'start_time': obj.session.time_slot.start_time.strftime('%H:%M'),
            'end_time': obj.session.time_slot.end_time.strftime('%H:%M'),
            'session_type': obj.session.session_type
        }


class SessionFeedbackCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer des retours avec validation"""

    class Meta:
        model = SessionFeedback
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'resolved_by', 'resolved_at', 'is_resolved', 'resolution_notes')

    def validate(self, data):
        """Valide les données du retour"""
        feedback_type = data.get('feedback_type')

        # Si c'est un problème, le type de problème doit être spécifié
        if feedback_type == 'issue':
            if not data.get('issue_type'):
                raise serializers.ValidationError(
                    "Le type de problème doit être spécifié pour un retour de type 'issue'"
                )
            if not data.get('severity'):
                raise serializers.ValidationError(
                    "La sévérité doit être spécifiée pour un retour de type 'issue'"
                )

        return data


class TeacherDashboardSerializer(serializers.Serializer):
    """Serializer pour le dashboard enseignant"""
    teacher = TeacherSerializer()

    # Statistiques générales
    total_courses = serializers.IntegerField()
    total_sessions = serializers.IntegerField()
    total_hours_per_week = serializers.FloatField()

    # Sessions à venir
    upcoming_sessions = serializers.ListField()

    # Préférences et indisponibilités
    active_preferences_count = serializers.IntegerField()
    pending_unavailabilities_count = serializers.IntegerField()

    # Demandes de modification
    pending_requests_count = serializers.IntegerField()
    recent_requests = TeacherScheduleRequestSerializer(many=True)

    # Retours récents
    recent_feedbacks = SessionFeedbackSerializer(many=True)

    # Conflits éventuels
    conflicts_count = serializers.IntegerField()
    conflicts = serializers.ListField()