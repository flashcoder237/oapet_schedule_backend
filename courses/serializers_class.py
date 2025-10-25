# courses/serializers_class.py
from rest_framework import serializers
from .models_class import StudentClass, ClassCourse, ClassRoomPreference
from .models import Course, Department, Curriculum
from rooms.models import Room


class ClassCourseSerializer(serializers.ModelSerializer):
    """Serializer pour les cours d'une classe"""
    course_code = serializers.CharField(source='course.code', read_only=True)
    course_name = serializers.CharField(source='course.name', read_only=True)
    course_type = serializers.CharField(source='course.course_type', read_only=True)
    teacher_name = serializers.CharField(source='course.teacher.user.get_full_name', read_only=True)
    effective_student_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ClassCourse
        fields = [
            'id', 'course', 'course_code', 'course_name', 'course_type',
            'teacher_name', 'is_mandatory', 'semester', 'order',
            'specific_student_count', 'effective_student_count',
            'is_active', 'created_at'
        ]


class ClassRoomPreferenceSerializer(serializers.ModelSerializer):
    """Serializer pour les préférences de salle par classe"""
    room_details = serializers.SerializerMethodField()
    class_details = serializers.SerializerMethodField()
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = ClassRoomPreference
        fields = [
            'id', 'student_class', 'class_details', 'room', 'room_details',
            'priority', 'priority_display', 'notes',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')

    def get_room_details(self, obj):
        """Retourne les détails de la salle"""
        room = obj.room
        return {
            'id': room.id,
            'code': room.code,
            'name': room.name,
            'capacity': room.capacity,
            'building': room.building.name if room.building else None,
            'building_code': room.building.code if room.building else None,
            'has_computer': room.has_computer,
            'has_projector': room.has_projector,
            'is_laboratory': room.is_laboratory,
        }

    def get_class_details(self, obj):
        """Retourne les détails de la classe"""
        student_class = obj.student_class
        return {
            'id': student_class.id,
            'code': student_class.code,
            'name': student_class.name,
            'level': student_class.level,
        }


class ClassRoomPreferenceCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer/modifier une préférence de salle"""

    class Meta:
        model = ClassRoomPreference
        fields = [
            'student_class', 'room', 'priority', 'notes', 'is_active'
        ]

    def validate(self, data):
        """Vérifie qu'une préférence n'existe pas déjà pour cette combinaison classe-salle"""
        student_class = data.get('student_class')
        room = data.get('room')

        # Si c'est une modification (instance existe), exclure l'instance actuelle
        if self.instance:
            existing = ClassRoomPreference.objects.filter(
                student_class=student_class,
                room=room
            ).exclude(id=self.instance.id)
        else:
            existing = ClassRoomPreference.objects.filter(
                student_class=student_class,
                room=room
            )

        if existing.exists():
            raise serializers.ValidationError({
                'room': 'Une préférence existe déjà pour cette salle et cette classe'
            })

        return data


class StudentClassListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des classes"""
    department_name = serializers.CharField(source='department.name', read_only=True)
    curriculum_name = serializers.CharField(source='curriculum.name', read_only=True)
    occupancy_rate = serializers.FloatField(read_only=True)
    courses_count = serializers.SerializerMethodField()
    room_preferences_count = serializers.SerializerMethodField()

    class Meta:
        model = StudentClass
        fields = [
            'id', 'code', 'name', 'level', 'department', 'department_name',
            'curriculum', 'curriculum_name', 'student_count', 'max_capacity',
            'occupancy_rate', 'academic_year', 'is_active',
            'courses_count', 'room_preferences_count', 'created_at'
        ]

    def get_courses_count(self, obj):
        return obj.class_courses.filter(is_active=True).count()

    def get_room_preferences_count(self, obj):
        return obj.room_preferences.filter(is_active=True).count()


class StudentClassDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour une classe"""
    department_name = serializers.CharField(source='department.name', read_only=True)
    curriculum_name = serializers.CharField(source='curriculum.name', read_only=True)
    occupancy_rate = serializers.FloatField(read_only=True)
    courses = ClassCourseSerializer(source='class_courses', many=True, read_only=True)
    room_preferences = ClassRoomPreferenceSerializer(many=True, read_only=True)

    class Meta:
        model = StudentClass
        fields = [
            'id', 'code', 'name', 'level', 'department', 'department_name',
            'curriculum', 'curriculum_name', 'student_count', 'max_capacity',
            'occupancy_rate', 'academic_year', 'description',
            'notes', 'is_active', 'courses', 'room_preferences',
            'created_at', 'updated_at'
        ]


class StudentClassCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer/modifier une classe"""

    class Meta:
        model = StudentClass
        fields = [
            'code', 'name', 'level', 'department', 'curriculum',
            'student_count', 'max_capacity', 'academic_year',
            'description', 'notes', 'is_active'
        ]

    def validate_student_count(self, value):
        if value < 0:
            raise serializers.ValidationError("Le nombre d'étudiants ne peut pas être négatif")
        return value

    def validate_max_capacity(self, value):
        if value < 0:
            raise serializers.ValidationError("La capacité maximale ne peut pas être négative")
        return value

    def validate(self, data):
        # Vérifie que student_count <= max_capacity
        student_count = data.get('student_count', 0)
        max_capacity = data.get('max_capacity', 50)

        if student_count > max_capacity:
            raise serializers.ValidationError({
                'student_count': f"Le nombre d'étudiants ({student_count}) dépasse la capacité maximale ({max_capacity})"
            })

        return data


class ClassCourseCreateSerializer(serializers.ModelSerializer):
    """Serializer pour assigner un cours à une classe"""

    class Meta:
        model = ClassCourse
        fields = [
            'student_class', 'course', 'is_mandatory', 'semester',
            'order', 'specific_student_count', 'is_active'
        ]

    def validate_specific_student_count(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Le nombre d'étudiants ne peut pas être négatif")
        return value


class BulkAssignCoursesSerializer(serializers.Serializer):
    """Serializer pour assigner plusieurs cours à une classe en une fois"""
    student_class = serializers.IntegerField()
    courses = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="Liste des IDs de cours à assigner"
    )
    is_mandatory = serializers.BooleanField(default=True)
    semester = serializers.CharField(default='S1')
