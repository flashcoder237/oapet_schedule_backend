# courses/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg

from core.mixins import ImportExportMixin
from .models import (
    Department, Teacher, Course, Curriculum, CurriculumCourse,
    Student, CourseEnrollment, CoursePrerequisite,
    TeacherPreference, TeacherUnavailability, TeacherScheduleRequest, SessionFeedback
)
from .serializers import (
    DepartmentSerializer, TeacherSerializer, CourseSerializer, CurriculumSerializer,
    StudentSerializer, CourseEnrollmentSerializer, CoursePrerequisiteSerializer,
    TeacherCreateSerializer, StudentCreateSerializer, CourseDetailSerializer,
    CurriculumDetailSerializer, TeacherPreferenceSerializer, TeacherPreferenceCreateSerializer,
    TeacherUnavailabilitySerializer, TeacherUnavailabilityCreateSerializer,
    TeacherDetailWithPreferencesSerializer, TeacherScheduleRequestSerializer,
    TeacherScheduleRequestCreateSerializer, SessionFeedbackSerializer,
    SessionFeedbackCreateSerializer, TeacherDashboardSerializer
)


class DepartmentViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des départements"""
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'name', 'code', 'description', 'is_active']
    import_fields = ['name', 'code', 'description']
    
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


class TeacherViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des enseignants"""
    queryset = Teacher.objects.all()
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'employee_id', 'department', 'specialization', 'max_hours_per_week', 'is_active']
    import_fields = ['employee_id', 'department', 'specialization', 'max_hours_per_week']
    
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

    @action(detail=True, methods=['get'])
    def dashboard(self, request, pk=None):
        """Dashboard complet pour un enseignant"""
        from schedules.models import ScheduleSession, Conflict
        from django.utils import timezone
        from datetime import timedelta

        teacher = self.get_object()

        # Statistiques générales
        total_courses = teacher.courses.filter(is_active=True).count()
        sessions = ScheduleSession.objects.filter(teacher=teacher, is_cancelled=False)
        total_sessions = sessions.count()
        total_hours_per_week = sum(session.get_duration_hours() for session in sessions)

        # Sessions à venir (cette semaine)
        today = timezone.now().date()
        week_end = today + timedelta(days=7)
        upcoming_sessions = []
        for session in sessions.select_related('course', 'room', 'time_slot')[:10]:
            upcoming_sessions.append({
                'id': session.id,
                'course_name': session.course.name,
                'course_code': session.course.code,
                'room': session.room.code,
                'day': session.time_slot.get_day_of_week_display(),
                'start_time': session.time_slot.start_time.strftime('%H:%M'),
                'end_time': session.time_slot.end_time.strftime('%H:%M'),
                'session_type': session.get_session_type_display()
            })

        # Préférences et indisponibilités
        active_preferences_count = teacher.preferences.filter(is_active=True).count()
        pending_unavailabilities_count = teacher.unavailabilities.filter(is_approved=False).count()

        # Demandes de modification
        pending_requests_count = teacher.schedule_requests.filter(status='pending').count()
        recent_requests = teacher.schedule_requests.all()[:5]

        # Retours récents
        recent_feedbacks = teacher.session_feedbacks.all()[:5]

        # Conflits
        conflicts = []
        conflicts_count = 0
        for session in sessions:
            session_conflicts = session.get_conflicts()
            if session_conflicts.exists():
                conflicts_count += session_conflicts.count()
                for conflict in session_conflicts[:3]:  # Limiter à 3 conflits par session
                    conflicts.append({
                        'id': conflict.id,
                        'type': conflict.get_conflict_type_display(),
                        'severity': conflict.get_severity_display(),
                        'description': conflict.description,
                        'session_id': session.id,
                        'course': session.course.name
                    })

        # Assembler les données du dashboard
        dashboard_data = {
            'teacher': TeacherSerializer(teacher).data,
            'total_courses': total_courses,
            'total_sessions': total_sessions,
            'total_hours_per_week': round(total_hours_per_week, 2),
            'upcoming_sessions': upcoming_sessions,
            'active_preferences_count': active_preferences_count,
            'pending_unavailabilities_count': pending_unavailabilities_count,
            'pending_requests_count': pending_requests_count,
            'recent_requests': TeacherScheduleRequestSerializer(recent_requests, many=True).data,
            'recent_feedbacks': SessionFeedbackSerializer(recent_feedbacks, many=True).data,
            'conflicts_count': conflicts_count,
            'conflicts': conflicts[:10]  # Limiter à 10 conflits
        }

        return Response(dashboard_data)


class CourseViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des cours"""
    queryset = Course.objects.all()
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'name', 'code', 'department', 'teacher', 'course_type', 'level', 'credits', 'hours_per_week', 'total_hours', 'semester', 'academic_year']
    import_fields = ['name', 'code', 'department', 'teacher', 'course_type', 'level', 'credits', 'hours_per_week', 'total_hours', 'semester', 'academic_year']
    
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


class CurriculumViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des curriculums"""
    queryset = Curriculum.objects.all()
    permission_classes = []  # Temporairement désactivé pour les tests

    export_fields = ['id', 'name', 'code', 'department', 'level', 'duration_semesters', 'is_active']
    import_fields = ['name', 'code', 'department', 'level', 'duration_semesters']
    
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


class StudentViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des étudiants"""
    queryset = Student.objects.all()
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'student_id', 'curriculum', 'current_semester', 'enrollment_year', 'is_active']
    import_fields = ['student_id', 'curriculum', 'current_semester', 'enrollment_year']
    
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


class CourseEnrollmentViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des inscriptions"""
    queryset = CourseEnrollment.objects.all()
    serializer_class = CourseEnrollmentSerializer
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'student', 'course', 'semester', 'academic_year', 'enrollment_date']
    import_fields = ['student', 'course', 'semester', 'academic_year']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        student_id = self.request.query_params.get('student')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        
        course_id = self.request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        
        return queryset.filter(is_active=True)


class CoursePrerequisiteViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des prérequis"""
    queryset = CoursePrerequisite.objects.all()
    serializer_class = CoursePrerequisiteSerializer
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'course', 'prerequisite_course', 'is_mandatory']
    import_fields = ['course', 'prerequisite_course', 'is_mandatory']


class TeacherPreferenceViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des préférences des enseignants"""
    queryset = TeacherPreference.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TeacherPreferenceCreateSerializer
        return TeacherPreferenceSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrer par enseignant
        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        # Filtrer par type de préférence
        preference_type = self.request.query_params.get('preference_type')
        if preference_type:
            queryset = queryset.filter(preference_type=preference_type)

        # Filtrer par priorité
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        # Filtrer par statut actif
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)

        return queryset.order_by('teacher', 'priority', 'preference_type')

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Active/désactive une préférence"""
        preference = self.get_object()
        preference.is_active = not preference.is_active
        preference.save()

        return Response({
            'message': f'Préférence {"activée" if preference.is_active else "désactivée"}',
            'is_active': preference.is_active
        })

    @action(detail=False, methods=['get'])
    def by_teacher(self, request):
        """Récupère toutes les préférences groupées par enseignant"""
        from django.db.models import Q

        teacher_id = request.query_params.get('teacher_id')
        if not teacher_id:
            return Response({
                'error': 'teacher_id est requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        preferences = TeacherPreference.objects.filter(
            teacher_id=teacher_id,
            is_active=True
        )

        # Grouper par type
        grouped = {}
        for pref in preferences:
            pref_type = pref.get_preference_type_display()
            if pref_type not in grouped:
                grouped[pref_type] = []
            grouped[pref_type].append(TeacherPreferenceSerializer(pref).data)

        return Response({
            'teacher_id': teacher_id,
            'preferences': grouped
        })


class TeacherUnavailabilityViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des indisponibilités des enseignants"""
    queryset = TeacherUnavailability.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TeacherUnavailabilityCreateSerializer
        return TeacherUnavailabilitySerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrer par enseignant
        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        # Filtrer par type d'indisponibilité
        unavailability_type = self.request.query_params.get('unavailability_type')
        if unavailability_type:
            queryset = queryset.filter(unavailability_type=unavailability_type)

        # Filtrer par statut d'approbation
        is_approved = self.request.query_params.get('is_approved')
        if is_approved is not None:
            is_approved_bool = is_approved.lower() == 'true'
            queryset = queryset.filter(is_approved=is_approved_bool)

        return queryset.order_by('-created_at')

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approuve une indisponibilité"""
        unavailability = self.get_object()

        if unavailability.is_approved:
            return Response({
                'message': 'Cette indisponibilité est déjà approuvée'
            }, status=status.HTTP_400_BAD_REQUEST)

        unavailability.is_approved = True
        unavailability.approved_by = request.user
        unavailability.save()

        return Response({
            'message': 'Indisponibilité approuvée avec succès',
            'data': TeacherUnavailabilitySerializer(unavailability).data
        })

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Rejette une indisponibilité"""
        unavailability = self.get_object()

        if unavailability.is_approved:
            return Response({
                'message': 'Cette indisponibilité est déjà approuvée'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Supprimer l'indisponibilité rejetée
        unavailability.delete()

        return Response({
            'message': 'Indisponibilité rejetée et supprimée'
        })

    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        """Récupère les indisponibilités en attente d'approbation"""
        pending = TeacherUnavailability.objects.filter(is_approved=False)
        serializer = self.get_serializer(pending, many=True)

        return Response({
            'count': pending.count(),
            'unavailabilities': serializer.data
        })

    @action(detail=False, methods=['get'])
    def by_teacher(self, request):
        """Récupère toutes les indisponibilités d'un enseignant"""
        teacher_id = request.query_params.get('teacher_id')
        if not teacher_id:
            return Response({
                'error': 'teacher_id est requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        unavailabilities = TeacherUnavailability.objects.filter(
            teacher_id=teacher_id,
            is_approved=True
        )

        # Grouper par type
        grouped = {}
        for unavail in unavailabilities:
            unavail_type = unavail.get_unavailability_type_display()
            if unavail_type not in grouped:
                grouped[unavail_type] = []
            grouped[unavail_type].append(TeacherUnavailabilitySerializer(unavail).data)

        return Response({
            'teacher_id': teacher_id,
            'unavailabilities': grouped
        })


class TeacherScheduleRequestViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des demandes de modification d'emploi du temps"""
    queryset = TeacherScheduleRequest.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TeacherScheduleRequestCreateSerializer
        return TeacherScheduleRequestSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrer par enseignant
        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        # Filtrer par type de demande
        request_type = self.request.query_params.get('request_type')
        if request_type:
            queryset = queryset.filter(request_type=request_type)

        # Filtrer par statut
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filtrer par priorité
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        return queryset.select_related('teacher__user', 'session', 'reviewed_by')

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approuve une demande de modification"""
        from django.utils import timezone

        schedule_request = self.get_object()

        if schedule_request.status in ['approved', 'completed']:
            return Response({
                'message': 'Cette demande a déjà été approuvée'
            }, status=status.HTTP_400_BAD_REQUEST)

        schedule_request.status = 'approved'
        schedule_request.reviewed_by = request.user
        schedule_request.reviewed_at = timezone.now()
        schedule_request.review_notes = request.data.get('review_notes', '')
        schedule_request.save()

        return Response({
            'message': 'Demande approuvée avec succès',
            'data': TeacherScheduleRequestSerializer(schedule_request).data
        })

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Rejette une demande de modification"""
        from django.utils import timezone

        schedule_request = self.get_object()

        if schedule_request.status in ['approved', 'completed']:
            return Response({
                'message': 'Cette demande a déjà été traitée'
            }, status=status.HTTP_400_BAD_REQUEST)

        schedule_request.status = 'rejected'
        schedule_request.reviewed_by = request.user
        schedule_request.reviewed_at = timezone.now()
        schedule_request.review_notes = request.data.get('review_notes', 'Demande rejetée')
        schedule_request.save()

        return Response({
            'message': 'Demande rejetée',
            'data': TeacherScheduleRequestSerializer(schedule_request).data
        })

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Marque une demande comme complétée après implémentation"""
        schedule_request = self.get_object()

        if schedule_request.status != 'approved':
            return Response({
                'message': 'Seules les demandes approuvées peuvent être marquées comme complétées'
            }, status=status.HTTP_400_BAD_REQUEST)

        schedule_request.status = 'completed'
        schedule_request.save()

        return Response({
            'message': 'Demande marquée comme complétée',
            'data': TeacherScheduleRequestSerializer(schedule_request).data
        })

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Récupère toutes les demandes en attente"""
        pending_requests = TeacherScheduleRequest.objects.filter(status='pending')
        serializer = self.get_serializer(pending_requests, many=True)

        return Response({
            'count': pending_requests.count(),
            'requests': serializer.data
        })

    @action(detail=False, methods=['get'])
    def by_teacher(self, request):
        """Récupère toutes les demandes d'un enseignant"""
        teacher_id = request.query_params.get('teacher_id')
        if not teacher_id:
            return Response({
                'error': 'teacher_id est requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        requests = TeacherScheduleRequest.objects.filter(teacher_id=teacher_id)

        # Grouper par statut
        grouped = {}
        for req in requests:
            req_status = req.get_status_display()
            if req_status not in grouped:
                grouped[req_status] = []
            grouped[req_status].append(TeacherScheduleRequestSerializer(req).data)

        return Response({
            'teacher_id': teacher_id,
            'total_requests': requests.count(),
            'requests_by_status': grouped
        })


class SessionFeedbackViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des retours sur les sessions"""
    queryset = SessionFeedback.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SessionFeedbackCreateSerializer
        return SessionFeedbackSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrer par enseignant
        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        # Filtrer par session
        session_id = self.request.query_params.get('session')
        if session_id:
            queryset = queryset.filter(session_id=session_id)

        # Filtrer par type de retour
        feedback_type = self.request.query_params.get('feedback_type')
        if feedback_type:
            queryset = queryset.filter(feedback_type=feedback_type)

        # Filtrer par statut de résolution
        is_resolved = self.request.query_params.get('is_resolved')
        if is_resolved is not None:
            is_resolved_bool = is_resolved.lower() == 'true'
            queryset = queryset.filter(is_resolved=is_resolved_bool)

        return queryset.select_related('teacher__user', 'session', 'resolved_by')

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Marque un retour comme résolu"""
        from django.utils import timezone

        feedback = self.get_object()

        if feedback.is_resolved:
            return Response({
                'message': 'Ce retour est déjà résolu'
            }, status=status.HTTP_400_BAD_REQUEST)

        feedback.is_resolved = True
        feedback.resolved_by = request.user
        feedback.resolved_at = timezone.now()
        feedback.resolution_notes = request.data.get('resolution_notes', '')
        feedback.save()

        return Response({
            'message': 'Retour marqué comme résolu',
            'data': SessionFeedbackSerializer(feedback).data
        })

    @action(detail=False, methods=['get'])
    def unresolved(self, request):
        """Récupère tous les retours non résolus"""
        unresolved_feedbacks = SessionFeedback.objects.filter(is_resolved=False)

        # Filtrer par sévérité si spécifié
        severity = request.query_params.get('severity')
        if severity:
            unresolved_feedbacks = unresolved_feedbacks.filter(severity=severity)

        # Trier par sévérité critique d'abord
        severity_order = {'critical': 1, 'high': 2, 'medium': 3, 'low': 4}
        unresolved_list = list(unresolved_feedbacks)
        unresolved_list.sort(key=lambda x: severity_order.get(x.severity, 5))

        serializer = self.get_serializer(unresolved_list, many=True)

        return Response({
            'count': len(unresolved_list),
            'feedbacks': serializer.data
        })

    @action(detail=False, methods=['get'])
    def by_teacher(self, request):
        """Récupère tous les retours d'un enseignant"""
        teacher_id = request.query_params.get('teacher_id')
        if not teacher_id:
            return Response({
                'error': 'teacher_id est requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        feedbacks = SessionFeedback.objects.filter(teacher_id=teacher_id)

        # Grouper par type
        grouped = {}
        for feedback in feedbacks:
            fb_type = feedback.get_feedback_type_display()
            if fb_type not in grouped:
                grouped[fb_type] = []
            grouped[fb_type].append(SessionFeedbackSerializer(feedback).data)

        return Response({
            'teacher_id': teacher_id,
            'total_feedbacks': feedbacks.count(),
            'feedbacks_by_type': grouped
        })

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistiques sur les retours"""
        total_feedbacks = SessionFeedback.objects.count()
        resolved_count = SessionFeedback.objects.filter(is_resolved=True).count()
        unresolved_count = SessionFeedback.objects.filter(is_resolved=False).count()

        # Par type
        by_type = {}
        for choice in SessionFeedback.FEEDBACK_TYPE_CHOICES:
            type_code = choice[0]
            type_label = choice[1]
            count = SessionFeedback.objects.filter(feedback_type=type_code).count()
            by_type[type_label] = count

        # Par sévérité (pour les problèmes uniquement)
        by_severity = {}
        issues = SessionFeedback.objects.filter(feedback_type='issue')
        for severity_choice in [('low', 'Faible'), ('medium', 'Moyenne'), ('high', 'Élevée'), ('critical', 'Critique')]:
            sev_code = severity_choice[0]
            sev_label = severity_choice[1]
            count = issues.filter(severity=sev_code).count()
            by_severity[sev_label] = count

        return Response({
            'total_feedbacks': total_feedbacks,
            'resolved_count': resolved_count,
            'unresolved_count': unresolved_count,
            'resolution_rate': round((resolved_count / total_feedbacks * 100) if total_feedbacks > 0 else 0, 2),
            'by_type': by_type,
            'by_severity': by_severity
        })
