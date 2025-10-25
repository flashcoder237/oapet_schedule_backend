# courses/views_class.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db import models

from core.mixins import ImportExportMixin
from .models_class import StudentClass, ClassCourse, ClassRoomPreference
from .models import Course
from .serializers_class import (
    StudentClassListSerializer,
    StudentClassDetailSerializer,
    StudentClassCreateSerializer,
    ClassCourseSerializer,
    ClassCourseCreateSerializer,
    BulkAssignCoursesSerializer,
    ClassRoomPreferenceSerializer,
    ClassRoomPreferenceCreateSerializer
)
from rooms.models import Room


class StudentClassViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour gérer les classes d'étudiants"""
    queryset = StudentClass.objects.all()
    permission_classes = [IsAuthenticated]

    # Champs pour l'export/import
    export_fields = ['id', 'name', 'code', 'level', 'department', 'curriculum', 'academic_year', 'student_count', 'max_capacity', 'is_active']
    import_fields = ['name', 'code', 'level', 'department', 'curriculum', 'academic_year', 'student_count', 'max_capacity']

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


class ClassRoomPreferenceViewSet(viewsets.ModelViewSet):
    """ViewSet pour gérer les préférences de salle par classe"""
    queryset = ClassRoomPreference.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ClassRoomPreferenceCreateSerializer
        return ClassRoomPreferenceSerializer

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'student_class', 'room', 'room__building'
        )

        class_id = self.request.query_params.get('class_id')
        if class_id:
            queryset = queryset.filter(student_class_id=class_id)

        room_id = self.request.query_params.get('room_id')
        if room_id:
            queryset = queryset.filter(room_id=room_id)

        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        active_only = self.request.query_params.get('active_only')
        if active_only == 'true':
            queryset = queryset.filter(is_active=True)

        return queryset.order_by('student_class__code', 'priority', 'room__code')

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Créer plusieurs préférences en une fois"""
        preferences = request.data.get('preferences', [])

        if not preferences:
            return Response({'error': 'Aucune préférence fournie'}, status=status.HTTP_400_BAD_REQUEST)

        created_preferences = []
        errors = []

        with transaction.atomic():
            for pref_data in preferences:
                serializer = ClassRoomPreferenceCreateSerializer(data=pref_data)
                if serializer.is_valid():
                    pref = serializer.save()
                    created_preferences.append(ClassRoomPreferenceSerializer(pref).data)
                else:
                    errors.append({'data': pref_data, 'errors': serializer.errors})

        return Response({
            'created': len(created_preferences),
            'failed': len(errors),
            'preferences': created_preferences,
            'errors': errors
        }, status=status.HTTP_201_CREATED if created_preferences else status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def by_class(self, request):
        """Récupère toutes les préférences pour une classe"""
        class_id = request.query_params.get('class_id')

        if not class_id:
            return Response({'error': 'class_id est requis'}, status=status.HTTP_400_BAD_REQUEST)

        preferences = self.get_queryset().filter(student_class_id=class_id)
        serializer = self.get_serializer(preferences, many=True)

        grouped = {'obligatoire': [], 'preferee': [], 'acceptable': []}

        for pref in serializer.data:
            priority = pref['priority']
            if priority == 1:
                grouped['obligatoire'].append(pref)
            elif priority == 2:
                grouped['preferee'].append(pref)
            elif priority == 3:
                grouped['acceptable'].append(pref)

        return Response({
            'class_id': class_id,
            'total': preferences.count(),
            'grouped_by_priority': grouped,
            'preferences': serializer.data
        })

    @action(detail=False, methods=['get'])
    def available_rooms(self, request):
        """Liste des salles disponibles pour créer une préférence"""
        class_id = request.query_params.get('class_id')

        if not class_id:
            return Response({'error': 'class_id est requis'}, status=status.HTTP_400_BAD_REQUEST)

        used_room_ids = ClassRoomPreference.objects.filter(
            student_class_id=class_id
        ).values_list('room_id', flat=True)

        available_rooms = Room.objects.filter(
            is_active=True
        ).exclude(
            id__in=used_room_ids
        ).select_related('building').order_by('building__code', 'code')

        rooms_data = [{
            'id': room.id,
            'code': room.code,
            'name': room.name,
            'building': room.building.name if room.building else None,
            'building_code': room.building.code if room.building else None,
            'capacity': room.capacity,
            'has_computer': room.has_computer,
            'has_projector': room.has_projector,
            'is_laboratory': room.is_laboratory,
        } for room in available_rooms]

        return Response({'count': len(rooms_data), 'rooms': rooms_data})
