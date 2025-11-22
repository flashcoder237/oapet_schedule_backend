# oapet_schedule_backend/search_views.py
"""
Endpoint de recherche global avec filtrage par rôle utilisateur
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q, Value, CharField
from django.db.models.functions import Concat

from courses.models import Course, Teacher, Student, Department
from schedules.models import Schedule, ScheduleSession
from rooms.models import Room, Building


def get_user_role(user):
    """Récupère le rôle de l'utilisateur"""
    if user.is_superuser or user.is_staff:
        return 'admin'

    if hasattr(user, 'profile'):
        return user.profile.role

    # Vérifier si c'est un enseignant
    if hasattr(user, 'teacher_profile'):
        return 'teacher'

    # Vérifier si c'est un étudiant
    if hasattr(user, 'student_profile'):
        return 'student'

    return 'student'  # Par défaut


def get_teacher_id(user):
    """Récupère l'ID de l'enseignant lié à l'utilisateur"""
    if hasattr(user, 'teacher_profile'):
        return user.teacher_profile.id

    # Rechercher par user directement
    teacher = Teacher.objects.filter(user=user).first()
    if teacher:
        return teacher.id

    # Rechercher par email via la relation user
    teacher = Teacher.objects.filter(user__email=user.email).first()
    if teacher:
        return teacher.id

    return None


def get_student_id(user):
    """Récupère l'ID de l'étudiant lié à l'utilisateur"""
    if hasattr(user, 'student_profile'):
        return user.student_profile.id

    # Rechercher par user directement
    student = Student.objects.filter(user=user).first()
    if student:
        return student.id

    # Rechercher par email via la relation user
    student = Student.objects.filter(user__email=user.email).first()
    if student:
        return student.id

    return None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def global_search(request):
    """
    Endpoint de recherche globale avec filtrage par rôle.

    Query params:
    - q: Terme de recherche (requis)
    - type: Type de résultat à filtrer (course, teacher, room, schedule, student, department)
    - limit: Nombre maximum de résultats par catégorie (défaut: 10)
    """
    query = request.query_params.get('q', '').strip()
    result_type = request.query_params.get('type', 'all')
    limit = min(int(request.query_params.get('limit', 10)), 50)

    if not query or len(query) < 2:
        return Response({
            'results': [],
            'total': 0,
            'message': 'La recherche doit contenir au moins 2 caractères'
        })

    user = request.user
    role = get_user_role(user)
    teacher_id = get_teacher_id(user)
    student_id = get_student_id(user)

    results = []

    # === RECHERCHE DES COURS ===
    if result_type in ['all', 'course']:
        courses_query = Course.objects.filter(is_active=True)

        # Filtre de recherche
        courses_query = courses_query.filter(
            Q(name__icontains=query) |
            Q(code__icontains=query) |
            Q(description__icontains=query) |
            Q(teacher__user__first_name__icontains=query) |
            Q(teacher__user__last_name__icontains=query)
        )

        # Filtrage par rôle
        if role == 'teacher' and teacher_id:
            # Enseignant: seulement ses cours
            courses_query = courses_query.filter(teacher_id=teacher_id)
        elif role == 'student' and student_id:
            # Étudiant: seulement les cours auxquels il est inscrit
            courses_query = courses_query.filter(
                Q(enrollments__student_id=student_id) |
                Q(curriculum__students__id=student_id)
            ).distinct()
        # Admin: tous les cours (pas de filtre supplémentaire)

        for course in courses_query[:limit]:
            results.append({
                'id': f'course-{course.id}',
                'title': course.name,
                'description': f'{course.code} - {course.level or ""}',
                'type': 'course',
                'category': course.department.name if course.department else 'Non assigné',
                'relevance': 0.9,
                'metadata': {
                    'id': course.id,
                    'code': course.code,
                    'level': course.level,
                    'teacher': f'{course.teacher.user.first_name} {course.teacher.user.last_name}' if course.teacher else None,
                    'department': course.department.code if course.department else None,
                    'credits': course.credits,
                    'hours_per_week': course.hours_per_week,
                    'total_hours': course.total_hours,
                    'href': f'/courses/{course.id}'
                }
            })

    # === RECHERCHE DES ENSEIGNANTS ===
    if result_type in ['all', 'teacher']:
        teachers_query = Teacher.objects.filter(is_active=True)

        # Filtre de recherche
        teachers_query = teachers_query.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(department__name__icontains=query)
        )

        # Filtrage par rôle
        if role == 'teacher' and teacher_id:
            # Enseignant: seulement lui-même et les collègues du même département
            current_teacher = Teacher.objects.filter(id=teacher_id).first()
            if current_teacher and current_teacher.department:
                teachers_query = teachers_query.filter(department=current_teacher.department)
        elif role == 'student' and student_id:
            # Étudiant: seulement les enseignants de ses cours
            teachers_query = teachers_query.filter(
                courses__enrollments__student_id=student_id
            ).distinct()
        # Admin: tous les enseignants

        for teacher in teachers_query.select_related('user', 'department')[:limit]:
            results.append({
                'id': f'teacher-{teacher.id}',
                'title': f'{teacher.user.first_name} {teacher.user.last_name}',
                'description': teacher.department.name if teacher.department else 'Sans département',
                'type': 'teacher',
                'category': 'Enseignant',
                'relevance': 0.85,
                'metadata': {
                    'id': teacher.id,
                    'email': teacher.user.email,
                    'phone': teacher.phone,
                    'department': teacher.department.code if teacher.department else None,
                    'department_name': teacher.department.name if teacher.department else None,
                    'employee_id': teacher.employee_id,
                    'href': f'/teachers/{teacher.id}'
                }
            })

    # === RECHERCHE DES SALLES ===
    if result_type in ['all', 'room']:
        rooms_query = Room.objects.filter(is_active=True)

        # Filtre de recherche
        rooms_query = rooms_query.filter(
            Q(name__icontains=query) |
            Q(code__icontains=query) |
            Q(building__name__icontains=query) |
            Q(room_type__name__icontains=query)
        )

        # Les salles sont accessibles à tous les rôles
        for room in rooms_query[:limit]:
            results.append({
                'id': f'room-{room.id}',
                'title': room.name,
                'description': f'{room.building.name if room.building else ""} - Capacité: {room.capacity}',
                'type': 'room',
                'category': room.room_type.name if room.room_type else 'Salle',
                'relevance': 0.8,
                'metadata': {
                    'id': room.id,
                    'code': room.code,
                    'capacity': room.capacity,
                    'building': room.building.name if room.building else None,
                    'building_code': room.building.code if room.building else None,
                    'room_type': room.room_type.name if room.room_type else None,
                    'floor': room.floor,
                    'href': f'/rooms/{room.id}'
                }
            })

    # === RECHERCHE DES SESSIONS/EMPLOIS DU TEMPS ===
    if result_type in ['all', 'schedule']:
        sessions_query = ScheduleSession.objects.filter(is_cancelled=False)

        # Filtre de recherche
        sessions_query = sessions_query.filter(
            Q(course__name__icontains=query) |
            Q(course__code__icontains=query) |
            Q(room__name__icontains=query) |
            Q(teacher__user__first_name__icontains=query) |
            Q(teacher__user__last_name__icontains=query)
        )

        # Filtrage par rôle
        if role == 'teacher' and teacher_id:
            sessions_query = sessions_query.filter(teacher_id=teacher_id)
        elif role == 'student' and student_id:
            # Étudiant: sessions de ses cours
            sessions_query = sessions_query.filter(
                Q(course__enrollments__student_id=student_id) |
                Q(schedule__curriculum__students__id=student_id)
            ).distinct()

        for session in sessions_query.select_related('course', 'room', 'teacher', 'teacher__user', 'time_slot')[:limit]:
            # Le jour de la semaine est stocké dans time_slot
            day_names_map = {
                'monday': 'Lundi', 'tuesday': 'Mardi', 'wednesday': 'Mercredi',
                'thursday': 'Jeudi', 'friday': 'Vendredi', 'saturday': 'Samedi', 'sunday': 'Dimanche'
            }
            day_of_week = session.time_slot.day_of_week if session.time_slot else ''
            day_name = day_names_map.get(day_of_week, day_of_week)
            start_time = session.time_slot.start_time if session.time_slot else None
            end_time = session.time_slot.end_time if session.time_slot else None

            results.append({
                'id': f'session-{session.id}',
                'title': session.course.name if session.course else 'Session',
                'description': f'{day_name} {start_time.strftime("%H:%M") if start_time else ""}-{end_time.strftime("%H:%M") if end_time else ""} - {session.room.name if session.room else "Salle non définie"}',
                'type': 'schedule',
                'category': session.session_type or 'Cours',
                'relevance': 0.75,
                'metadata': {
                    'id': session.id,
                    'course_id': session.course.id if session.course else None,
                    'course_code': session.course.code if session.course else None,
                    'room_id': session.room.id if session.room else None,
                    'room_name': session.room.name if session.room else None,
                    'teacher_id': session.teacher.id if session.teacher else None,
                    'teacher_name': f'{session.teacher.user.first_name} {session.teacher.user.last_name}' if session.teacher else None,
                    'day_of_week': day_of_week,
                    'day_name': day_name,
                    'start_time': start_time.strftime("%H:%M") if start_time else None,
                    'end_time': end_time.strftime("%H:%M") if end_time else None,
                    'session_type': session.session_type,
                    'href': f'/schedule?session={session.id}'
                }
            })

    # === RECHERCHE DES ÉTUDIANTS (Admin seulement) ===
    if result_type in ['all', 'student'] and role == 'admin':
        students_query = Student.objects.filter(is_active=True)

        # Filtre de recherche
        students_query = students_query.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(student_id__icontains=query)
        )

        for student in students_query.select_related('user')[:limit]:
            results.append({
                'id': f'student-{student.id}',
                'title': f'{student.user.first_name} {student.user.last_name}',
                'description': f'Matricule: {student.student_id}' if student.student_id else 'Étudiant',
                'type': 'student',
                'category': 'Étudiant',
                'relevance': 0.7,
                'metadata': {
                    'id': student.id,
                    'email': student.user.email,
                    'student_id': student.student_id,
                    'level': student.current_level if hasattr(student, 'current_level') else None,
                    'href': f'/students/{student.id}'
                }
            })

    # === RECHERCHE DES DÉPARTEMENTS (Admin seulement) ===
    if result_type in ['all', 'department'] and role in ['admin', 'department_head']:
        departments_query = Department.objects.filter(is_active=True)

        # Filtre de recherche
        departments_query = departments_query.filter(
            Q(name__icontains=query) |
            Q(code__icontains=query) |
            Q(description__icontains=query)
        )

        for dept in departments_query[:limit]:
            teacher_count = dept.teachers.filter(is_active=True).count()
            course_count = dept.courses.filter(is_active=True).count()

            results.append({
                'id': f'department-{dept.id}',
                'title': dept.name,
                'description': f'{teacher_count} enseignants, {course_count} cours',
                'type': 'department',
                'category': 'Département',
                'relevance': 0.65,
                'metadata': {
                    'id': dept.id,
                    'code': dept.code,
                    'teacher_count': teacher_count,
                    'course_count': course_count,
                    'href': f'/departments/{dept.id}'
                }
            })

    # Trier par pertinence
    results.sort(key=lambda x: x['relevance'], reverse=True)

    return Response({
        'results': results,
        'total': len(results),
        'query': query,
        'type': result_type,
        'user_role': role
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_suggestions(request):
    """
    Endpoint pour les suggestions de recherche basées sur le rôle.

    Query params:
    - q: Terme de recherche partiel (optionnel)
    """
    query = request.query_params.get('q', '').strip()
    user = request.user
    role = get_user_role(user)
    teacher_id = get_teacher_id(user)
    student_id = get_student_id(user)

    suggestions = []

    if not query:
        # Suggestions populaires basées sur le rôle
        if role == 'admin':
            suggestions = [
                {'id': 's1', 'text': 'Cours non assignés', 'type': 'suggestion', 'category': 'Cours'},
                {'id': 's2', 'text': 'Conflits d\'emploi du temps', 'type': 'popular', 'category': 'Planning'},
                {'id': 's3', 'text': 'Salles disponibles', 'type': 'popular', 'category': 'Salles'},
                {'id': 's4', 'text': 'Enseignants par département', 'type': 'suggestion', 'category': 'Enseignants'},
                {'id': 's5', 'text': 'Statistiques étudiants', 'type': 'suggestion', 'category': 'Étudiants'},
            ]
        elif role in ['teacher', 'professor']:
            suggestions = [
                {'id': 's1', 'text': 'Mes cours aujourd\'hui', 'type': 'popular', 'category': 'Mes cours'},
                {'id': 's2', 'text': 'Mon emploi du temps', 'type': 'popular', 'category': 'Planning'},
                {'id': 's3', 'text': 'Salles libres', 'type': 'suggestion', 'category': 'Salles'},
                {'id': 's4', 'text': 'Mes étudiants', 'type': 'suggestion', 'category': 'Étudiants'},
            ]
        elif role == 'student':
            suggestions = [
                {'id': 's1', 'text': 'Mon emploi du temps', 'type': 'popular', 'category': 'Planning'},
                {'id': 's2', 'text': 'Mes cours', 'type': 'popular', 'category': 'Cours'},
                {'id': 's3', 'text': 'Prochains examens', 'type': 'suggestion', 'category': 'Planning'},
                {'id': 's4', 'text': 'Mes enseignants', 'type': 'suggestion', 'category': 'Enseignants'},
            ]
    else:
        # Suggestions basées sur la requête partielle
        # Récupérer quelques noms de cours correspondants
        courses = Course.objects.filter(
            Q(name__icontains=query) | Q(code__icontains=query),
            is_active=True
        )[:3]

        for i, course in enumerate(courses):
            suggestions.append({
                'id': f'course-{course.id}',
                'text': course.name,
                'type': 'suggestion',
                'category': 'Cours'
            })

        # Récupérer quelques noms d'enseignants correspondants
        teachers = Teacher.objects.filter(
            Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query),
            is_active=True
        ).select_related('user')[:2]

        for teacher in teachers:
            suggestions.append({
                'id': f'teacher-{teacher.id}',
                'text': f'{teacher.user.first_name} {teacher.user.last_name}',
                'type': 'suggestion',
                'category': 'Enseignant'
            })

        # Récupérer quelques salles correspondantes
        rooms = Room.objects.filter(
            Q(name__icontains=query) | Q(code__icontains=query),
            is_active=True
        )[:2]

        for room in rooms:
            suggestions.append({
                'id': f'room-{room.id}',
                'text': room.name,
                'type': 'suggestion',
                'category': 'Salle'
            })

    return Response({
        'suggestions': suggestions,
        'query': query,
        'user_role': role
    })
