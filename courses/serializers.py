# courses/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Department, Teacher, Course, Curriculum, CurriculumCourse,
    Student, CourseEnrollment, CoursePrerequisite
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