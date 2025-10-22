# courses/views_class.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db import models

from core.mixins import ImportExportMixin
from .models_class import StudentClass, ClassCourse
from .models import Course
from .serializers_class import (
    StudentClassListSerializer,
    StudentClassDetailSerializer,
    StudentClassCreateSerializer,
    ClassCourseSerializer,
    ClassCourseCreateSerializer,
    BulkAssignCoursesSerializer
)


class StudentClassViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour gérer les classes d'étudiants"""
    queryset = StudentClass.objects.all()
    permission_classes = [IsAuthenticated]

    # Champs pour l'export/import
    export_fields = ['id', 'name', 'code', 'level', 'section', 'department', 'curriculum', 'academic_year', 'student_count', 'max_capacity', 'is_active']
    import_fields = ['name', 'code', 'level', 'section', 'department', 'curriculum', 'academic_year', 'student_count', 'max_capacity']

    def get_serializer_class(self):
        if self.action == 'list':
            return StudentClassListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return StudentClassCreateSerializer
        return StudentClassDetailSerializer

    def get_queryset(self):
        queryset = StudentClass.objects.select_related(
            'department', 'curriculum'
        ).prefetch_related('class_courses__course')

        # Filtres
        level = self.request.query_params.get('level')
        department = self.request.query_params.get('department')
        academic_year = self.request.query_params.get('academic_year')
        is_active = self.request.query_params.get('is_active')
        teacher_id = self.request.query_params.get('teacher')

        if level:
            queryset = queryset.filter(level=level)
        if department:
            queryset = queryset.filter(department_id=department)
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        # Filtrer par enseignant - classes où l'enseignant a des sessions programmées
        if teacher_id:
            from schedules.models import ScheduleSession
            # Récupérer les classes où l'enseignant a au moins une session
            class_ids = ScheduleSession.objects.filter(
                teacher_id=teacher_id
            ).values_list('schedule__student_class_id', flat=True).distinct()
            queryset = queryset.filter(id__in=class_ids)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def courses(self, request, pk=None):
        """Récupère les cours d'une classe"""
        student_class = self.get_object()
        class_courses = student_class.class_courses.filter(
            is_active=True
        ).select_related('course', 'course__teacher__user')

        serializer = ClassCourseSerializer(class_courses, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def assign_course(self, request, pk=None):
        """Assigne un cours à une classe"""
        student_class = self.get_object()
        serializer = ClassCourseCreateSerializer(data={
            **request.data,
            'student_class': student_class.id
        })

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def assign_courses_bulk(self, request, pk=None):
        """Assigne plusieurs cours à une classe en une fois"""
        student_class = self.get_object()
        serializer = BulkAssignCoursesSerializer(data={
            **request.data,
            'student_class': student_class.id
        })

        if serializer.is_valid():
            course_ids = serializer.validated_data['courses']
            is_mandatory = serializer.validated_data.get('is_mandatory', True)
            semester = serializer.validated_data.get('semester', 'S1')

            created_assignments = []
            errors = []

            with transaction.atomic():
                for course_id in course_ids:
                    try:
                        course = Course.objects.get(id=course_id, is_active=True)

                        # Vérifie si déjà assigné
                        existing = ClassCourse.objects.filter(
                            student_class=student_class,
                            course=course
                        ).first()

                        if existing:
                            if not existing.is_active:
                                existing.is_active = True
                                existing.save()
                                created_assignments.append(existing)
                        else:
                            class_course = ClassCourse.objects.create(
                                student_class=student_class,
                                course=course,
                                is_mandatory=is_mandatory,
                                semester=semester
                            )
                            created_assignments.append(class_course)

                    except Course.DoesNotExist:
                        errors.append(f"Cours {course_id} introuvable")

            return Response({
                'success': True,
                'assigned': len(created_assignments),
                'errors': errors,
                'assignments': ClassCourseSerializer(created_assignments, many=True).data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'])
    def remove_course(self, request, pk=None):
        """Retire un cours d'une classe"""
        student_class = self.get_object()
        course_id = request.data.get('course_id')

        if not course_id:
            return Response(
                {'error': 'course_id est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            class_course = ClassCourse.objects.get(
                student_class=student_class,
                course_id=course_id
            )
            class_course.delete()

            return Response({
                'success': True,
                'message': 'Cours retiré de la classe'
            })

        except ClassCourse.DoesNotExist:
            return Response(
                {'error': 'Ce cours n\'est pas assigné à cette classe'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistiques sur les classes"""
        from django.db.models import Sum, Avg, Count

        stats = StudentClass.objects.filter(is_active=True).aggregate(
            total_classes=Count('id'),
            total_students=Sum('student_count'),
            avg_students_per_class=Avg('student_count'),
            avg_occupancy_rate=Avg(
                models.F('student_count') * 100.0 / models.F('max_capacity')
            )
        )

        # Stats par niveau
        by_level = StudentClass.objects.filter(is_active=True).values('level').annotate(
            count=Count('id'),
            total_students=Sum('student_count')
        ).order_by('level')

        return Response({
            'global': stats,
            'by_level': list(by_level)
        })


class ClassCourseViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour gérer les assignations cours-classe"""
    queryset = ClassCourse.objects.all()
    permission_classes = [IsAuthenticated]

    # Champs pour l'export/import
    export_fields = ['id', 'student_class', 'course', 'is_mandatory', 'semester', 'is_active']
    import_fields = ['student_class', 'course', 'is_mandatory', 'semester']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ClassCourseCreateSerializer
        return ClassCourseSerializer

    def get_queryset(self):
        queryset = ClassCourse.objects.select_related(
            'student_class', 'course', 'course__teacher__user'
        )

        # Filtres
        student_class = self.request.query_params.get('student_class')
        course = self.request.query_params.get('course')
        semester = self.request.query_params.get('semester')

        if student_class:
            queryset = queryset.filter(student_class_id=student_class)
        if course:
            queryset = queryset.filter(course_id=course)
        if semester:
            queryset = queryset.filter(semester=semester)

        return queryset
