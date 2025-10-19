# courses/serializers_class.py
from rest_framework import serializers
from .models_class import StudentClass, ClassCourse
from .models import Course, Department, Curriculum


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


class StudentClassListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des classes"""
    department_name = serializers.CharField(source='department.name', read_only=True)
    curriculum_name = serializers.CharField(source='curriculum.name', read_only=True)
    occupancy_rate = serializers.FloatField(read_only=True)
    courses_count = serializers.SerializerMethodField()

    class Meta:
        model = StudentClass
        fields = [
            'id', 'code', 'name', 'level', 'department', 'department_name',
            'curriculum', 'curriculum_name', 'student_count', 'max_capacity',
            'occupancy_rate', 'academic_year', 'semester', 'is_active',
            'courses_count', 'created_at'
        ]

    def get_courses_count(self, obj):
        return obj.class_courses.filter(is_active=True).count()


class StudentClassDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour une classe"""
    department_name = serializers.CharField(source='department.name', read_only=True)
    curriculum_name = serializers.CharField(source='curriculum.name', read_only=True)
    occupancy_rate = serializers.FloatField(read_only=True)
    courses = ClassCourseSerializer(source='class_courses', many=True, read_only=True)

    class Meta:
        model = StudentClass
        fields = [
            'id', 'code', 'name', 'level', 'department', 'department_name',
            'curriculum', 'curriculum_name', 'student_count', 'max_capacity',
            'occupancy_rate', 'academic_year', 'semester', 'description',
            'notes', 'is_active', 'courses', 'created_at', 'updated_at'
        ]


class StudentClassCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer/modifier une classe"""

    class Meta:
        model = StudentClass
        fields = [
            'code', 'name', 'level', 'department', 'curriculum',
            'student_count', 'max_capacity', 'academic_year', 'semester',
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
