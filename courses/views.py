# courses/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg

from .models import (
    Department, Teacher, Course, Curriculum, CurriculumCourse,
    Student, CourseEnrollment, CoursePrerequisite
)
from .serializers import (
    DepartmentSerializer, TeacherSerializer, CourseSerializer, CurriculumSerializer,
    StudentSerializer, CourseEnrollmentSerializer, CoursePrerequisiteSerializer,
    TeacherCreateSerializer, StudentCreateSerializer, CourseDetailSerializer,
    CurriculumDetailSerializer
)


class DepartmentViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des départements"""
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Statistiques d'un département"""
        department = self.get_object()
        
        stats = {
            'teachers_count': department.teachers.filter(is_active=True).count(),
            'courses_count': department.courses.filter(is_active=True).count(),
            'curricula_count': department.curricula.filter(is_active=True).count(),
            'total_students': Student.objects.filter(
                curriculum__department=department,
                is_active=True
            ).count()
        }
        
        return Response(stats)


class TeacherViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des enseignants"""
    queryset = Teacher.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TeacherCreateSerializer
        return TeacherSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        department_id = self.request.query_params.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        return queryset.filter(is_active=True)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques des enseignants"""
        total_teachers = Teacher.objects.filter(is_active=True).count()
        
        # Par département
        by_department = Teacher.objects.filter(is_active=True).values(
            'department__name', 'department__code'
        ).annotate(count=Count('id'))
        
        # Charge de travail moyenne
        avg_hours = Teacher.objects.filter(is_active=True).aggregate(
            avg_max_hours=Avg('max_hours_per_week')
        )
        
        return Response({
            'total_teachers': total_teachers,
            'by_department': list(by_department),
            'averages': avg_hours
        })
    
    @action(detail=True, methods=['get'])
    def schedule(self, request, pk=None):
        """Planning d'un enseignant"""
        from schedules.models import ScheduleSession
        teacher = self.get_object()
        
        # Sessions programmées
        sessions = ScheduleSession.objects.filter(
            teacher=teacher,
            is_cancelled=False
        ).select_related('course', 'room', 'time_slot')
        
        data = []
        for session in sessions:
            data.append({
                'id': session.id,
                'course_name': session.course.name,
                'course_code': session.course.code,
                'room': session.room.code,
                'day': session.time_slot.day_of_week,
                'start_time': session.time_slot.start_time,
                'end_time': session.time_slot.end_time,
                'session_type': session.session_type
            })
        
        return Response({
            'teacher': teacher.user.get_full_name(),
            'total_sessions': len(data),
            'sessions': data
        })


class CourseViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des cours"""
    queryset = Course.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CourseDetailSerializer
        return CourseSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtres
        department_id = self.request.query_params.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        
        level = self.request.query_params.get('level')
        if level:
            queryset = queryset.filter(level=level)
        
        course_type = self.request.query_params.get('type')
        if course_type:
            queryset = queryset.filter(course_type=course_type)
        
        # Filtre de recherche
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) |
                models.Q(code__icontains=search) |
                models.Q(description__icontains=search) |
                models.Q(teacher__user__first_name__icontains=search) |
                models.Q(teacher__user__last_name__icontains=search)
            )
        
        return queryset.filter(is_active=True)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques générales des cours"""
        total_courses = Course.objects.filter(is_active=True).count()
        
        # Répartition par type
        by_type = Course.objects.filter(is_active=True).values('course_type').annotate(
            count=Count('id')
        )
        
        # Répartition par niveau
        by_level = Course.objects.filter(is_active=True).values('level').annotate(
            count=Count('id')
        )
        
        # Répartition par département
        by_department = Course.objects.filter(is_active=True).values(
            'department__name', 'department__code'
        ).annotate(count=Count('id'))
        
        # Moyennes
        avg_hours = Course.objects.filter(is_active=True).aggregate(
            avg_hours_per_week=Avg('hours_per_week'),
            avg_total_hours=Avg('total_hours'),
            avg_credits=Avg('credits')
        )
        
        return Response({
            'total_courses': total_courses,
            'by_type': list(by_type),
            'by_level': list(by_level),
            'by_department': list(by_department),
            'averages': avg_hours
        })
    
    @action(detail=True, methods=['get'])
    def enrollments(self, request, pk=None):
        """Inscriptions pour un cours spécifique"""
        course = self.get_object()
        enrollments = CourseEnrollment.objects.filter(
            course=course, 
            is_active=True
        ).select_related('student__user')
        
        data = []
        for enrollment in enrollments:
            data.append({
                'id': enrollment.id,
                'student_id': enrollment.student.student_id,
                'student_name': enrollment.student.user.get_full_name(),
                'enrollment_date': enrollment.enrollment_date,
                'semester': enrollment.semester,
                'academic_year': enrollment.academic_year
            })
        
        return Response({
            'course': course.name,
            'total_enrollments': len(data),
            'enrollments': data
        })
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Dupliquer un cours"""
        original_course = self.get_object()
        
        # Créer une copie du cours
        new_course = Course.objects.create(
            name=f"{original_course.name} (Copie)",
            code=f"{original_course.code}_COPY",
            description=original_course.description,
            department=original_course.department,
            teacher=original_course.teacher,
            course_type=original_course.course_type,
            level=original_course.level,
            credits=original_course.credits,
            hours_per_week=original_course.hours_per_week,
            total_hours=original_course.total_hours,
            max_students=original_course.max_students,
            min_room_capacity=original_course.min_room_capacity,
            requires_computer=original_course.requires_computer,
            requires_projector=original_course.requires_projector,
            requires_laboratory=original_course.requires_laboratory,
            semester=original_course.semester,
            academic_year=original_course.academic_year,
            min_sessions_per_week=original_course.min_sessions_per_week,
            max_sessions_per_week=original_course.max_sessions_per_week,
            preferred_times=original_course.preferred_times,
            unavailable_times=original_course.unavailable_times
        )
        
        serializer = self.get_serializer(new_course)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def toggle_status(self, request, pk=None):
        """Activer/désactiver un cours"""
        course = self.get_object()
        course.is_active = not course.is_active
        course.save()
        
        return Response({
            'id': course.id,
            'is_active': course.is_active,
            'message': f"Cours {'activé' if course.is_active else 'désactivé'} avec succès"
        })
    
    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """Mise à jour en lot de cours"""
        course_ids = request.data.get('course_ids', [])
        update_data = request.data.get('update_data', {})
        
        if not course_ids:
            return Response({'error': 'Aucun cours spécifié'}, status=status.HTTP_400_BAD_REQUEST)
        
        courses = Course.objects.filter(id__in=course_ids)
        updated_count = 0
        
        for course in courses:
            for field, value in update_data.items():
                if hasattr(course, field):
                    setattr(course, field, value)
            course.save()
            updated_count += 1
        
        return Response({
            'updated_count': updated_count,
            'message': f"{updated_count} cours mis à jour avec succès"
        })
    
    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """Suppression en lot de cours"""
        course_ids = request.data.get('course_ids', [])
        
        if not course_ids:
            return Response({'error': 'Aucun cours spécifié'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Soft delete - marquer comme inactif plutôt que supprimer
        updated_count = Course.objects.filter(id__in=course_ids).update(is_active=False)
        
        return Response({
            'deleted_count': updated_count,
            'message': f"{updated_count} cours supprimés avec succès"
        })
    
    @action(detail=True, methods=['get'])
    def conflicts(self, request, pk=None):
        """Détecter les conflits pour un cours spécifique"""
        from schedules.models import ScheduleSession
        course = self.get_object()
        
        # Récupérer les sessions du cours
        sessions = ScheduleSession.objects.filter(
            course=course,
            is_cancelled=False
        ).select_related('time_slot', 'room', 'teacher')
        
        conflicts = []
        
        for session in sessions:
            # Vérifier les conflits de salle
            room_conflicts = ScheduleSession.objects.filter(
                time_slot=session.time_slot,
                room=session.room,
                is_cancelled=False
            ).exclude(id=session.id)
            
            # Vérifier les conflits d'enseignant
            teacher_conflicts = ScheduleSession.objects.filter(
                time_slot=session.time_slot,
                teacher=session.teacher,
                is_cancelled=False
            ).exclude(id=session.id)
            
            if room_conflicts.exists() or teacher_conflicts.exists():
                conflicts.append({
                    'session_id': session.id,
                    'time_slot': {
                        'day': session.time_slot.day_of_week,
                        'start_time': session.time_slot.start_time,
                        'end_time': session.time_slot.end_time
                    },
                    'room_conflicts': [
                        {
                            'course_name': conf.course.name,
                            'teacher': conf.teacher.user.get_full_name()
                        } for conf in room_conflicts
                    ],
                    'teacher_conflicts': [
                        {
                            'course_name': conf.course.name,
                            'room': conf.room.code
                        } for conf in teacher_conflicts
                    ]
                })
        
        return Response({
            'course': course.name,
            'total_conflicts': len(conflicts),
            'conflicts': conflicts
        })


class CurriculumViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des curriculums"""
    queryset = Curriculum.objects.all()
    permission_classes = []  # Temporairement désactivé pour les tests
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CurriculumDetailSerializer
        return CurriculumSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        department_id = self.request.query_params.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        return queryset.filter(is_active=True)


class StudentViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des étudiants"""
    queryset = Student.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return StudentCreateSerializer
        return StudentSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        curriculum_id = self.request.query_params.get('curriculum')
        if curriculum_id:
            queryset = queryset.filter(curriculum_id=curriculum_id)
        return queryset.filter(is_active=True)


class CourseEnrollmentViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des inscriptions"""
    queryset = CourseEnrollment.objects.all()
    serializer_class = CourseEnrollmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        student_id = self.request.query_params.get('student')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        
        course_id = self.request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        
        return queryset.filter(is_active=True)


class CoursePrerequisiteViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des prérequis"""
    queryset = CoursePrerequisite.objects.all()
    serializer_class = CoursePrerequisiteSerializer
    permission_classes = [IsAuthenticated]
