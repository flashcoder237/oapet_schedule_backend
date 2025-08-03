#!/usr/bin/env python3
"""
Script pour créer des données de test pour le système OAPET
"""
import os
import sys
import django
from datetime import date, time, datetime, timedelta
from django.utils import timezone

# Configuration Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oapet_schedule_backend.settings')
django.setup()

from django.contrib.auth.models import User
from courses.models import (
    Department, Teacher, Course, Curriculum, CurriculumCourse,
    Student, CourseEnrollment
)
from rooms.models import Building, RoomType, Room
from schedules.models import (
    AcademicPeriod, TimeSlot, Schedule, ScheduleSession
)
from users.models import UserProfile

def create_test_data():
    """Crée des données de test complètes"""
    print("🚀 Création des données de test OAPET...")
    
    # 1. Utilisateurs
    print("👥 Création des utilisateurs...")
    admin_user, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'admin@oapet.com',
            'first_name': 'Admin',
            'last_name': 'OAPET',
            'is_staff': True,
            'is_superuser': True
        }
    )
    if created:
        admin_user.set_password('admin123')
        admin_user.save()
        # Définir le rôle admin
        if hasattr(admin_user, 'profile'):
            admin_user.profile.role = 'admin'
            admin_user.profile.save()
        print("✓ Admin créé")
    
    # 2. Départements
    print("🏛️ Création des départements...")
    dept_medecine, _ = Department.objects.get_or_create(
        code='MED',
        defaults={
            'name': 'Médecine',
            'description': 'Faculté de Médecine et des Sciences Biomédicales',
            'head_of_department': admin_user
        }
    )
    
    dept_pharmacie, _ = Department.objects.get_or_create(
        code='PHAR',
        defaults={
            'name': 'Pharmacie',
            'description': 'Faculté de Pharmacie',
            'head_of_department': admin_user
        }
    )
    
    dept_biologie, _ = Department.objects.get_or_create(
        code='BIO',
        defaults={
            'name': 'Biologie',
            'description': 'Département de Biologie',
            'head_of_department': admin_user
        }
    )
    
    # 3. Enseignants
    print("👨‍🏫 Création des enseignants...")
    teachers_data = [
        {'username': 'dr.kamga', 'first_name': 'Paul', 'last_name': 'Kamga', 'dept': dept_medecine, 'emp_id': 'T001', 'spec': ['Anatomie', 'Histologie']},
        {'username': 'dr.mbarga', 'first_name': 'Marie', 'last_name': 'Mbarga', 'dept': dept_medecine, 'emp_id': 'T002', 'spec': ['Physiologie', 'Biophysique']},
        {'username': 'dr.fotso', 'first_name': 'Jean', 'last_name': 'Fotso', 'dept': dept_pharmacie, 'emp_id': 'T003', 'spec': ['Pharmacologie', 'Toxicologie']},
        {'username': 'dr.nguema', 'first_name': 'Alice', 'last_name': 'Nguema', 'dept': dept_biologie, 'emp_id': 'T004', 'spec': ['Microbiologie', 'Immunologie']},
        {'username': 'pr.tsala', 'first_name': 'Bernard', 'last_name': 'Tsala', 'dept': dept_medecine, 'emp_id': 'T005', 'spec': ['Chirurgie', 'Urgences']},
    ]
    
    teachers = []
    for teacher_data in teachers_data:
        user, created = User.objects.get_or_create(
            username=teacher_data['username'],
            defaults={
                'email': f"{teacher_data['username']}@oapet.com",
                'first_name': teacher_data['first_name'],
                'last_name': teacher_data['last_name'],
                'is_staff': False
            }
        )
        if created:
            user.set_password('teacher123')
            user.save()
        
        teacher, _ = Teacher.objects.get_or_create(
            user=user,
            defaults={
                'employee_id': teacher_data['emp_id'],
                'department': teacher_data['dept'],
                'specializations': teacher_data['spec'],
                'max_hours_per_week': 20,
                'preferred_days': ['monday', 'tuesday', 'wednesday', 'thursday']
            }
        )
        teachers.append(teacher)
    
    # 4. Bâtiments et salles
    print("🏢 Création des bâtiments et salles...")
    
    # Bâtiments
    batiment_a, _ = Building.objects.get_or_create(
        code='BAT-A',
        defaults={
            'name': 'Bâtiment Principal A',
            'address': 'Campus Universitaire, Douala',
            'total_floors': 3
        }
    )
    
    batiment_b, _ = Building.objects.get_or_create(
        code='BAT-B',
        defaults={
            'name': 'Bâtiment Sciences B',
            'address': 'Campus Universitaire, Douala',
            'total_floors': 2
        }
    )
    
    # Types de salles
    type_amphi, _ = RoomType.objects.get_or_create(
        name='Amphithéâtre',
        defaults={'description': 'Grande salle pour cours magistraux'}
    )
    
    type_salle_cours, _ = RoomType.objects.get_or_create(
        name='Salle de cours',
        defaults={'description': 'Salle de cours standard'}
    )
    
    type_labo, _ = RoomType.objects.get_or_create(
        name='Laboratoire',
        defaults={'description': 'Laboratoire de travaux pratiques'}
    )
    
    # Salles
    rooms_data = [
        {'code': 'AMPHI-A', 'building': batiment_a, 'type': type_amphi, 'capacity': 200, 'floor': 1, 'projector': True, 'computer': False, 'lab': False, 'audio': True},
        {'code': 'AMPHI-B', 'building': batiment_a, 'type': type_amphi, 'capacity': 150, 'floor': 1, 'projector': True, 'computer': False, 'lab': False, 'audio': True},
        {'code': 'SALLE-101', 'building': batiment_a, 'type': type_salle_cours, 'capacity': 50, 'floor': 1, 'projector': True, 'computer': True, 'lab': False, 'audio': False},
        {'code': 'SALLE-102', 'building': batiment_a, 'type': type_salle_cours, 'capacity': 40, 'floor': 1, 'projector': True, 'computer': True, 'lab': False, 'audio': False},
        {'code': 'SALLE-201', 'building': batiment_a, 'type': type_salle_cours, 'capacity': 60, 'floor': 2, 'projector': True, 'computer': False, 'lab': False, 'audio': False},
        {'code': 'LABO-BIO-1', 'building': batiment_b, 'type': type_labo, 'capacity': 24, 'floor': 1, 'projector': False, 'computer': True, 'lab': True, 'audio': False},
        {'code': 'LABO-CHIM-1', 'building': batiment_b, 'type': type_labo, 'capacity': 20, 'floor': 2, 'projector': False, 'computer': True, 'lab': True, 'audio': False},
    ]
    
    rooms = []
    for room_data in rooms_data:
        room, _ = Room.objects.get_or_create(
            code=room_data['code'],
            defaults={
                'name': f"Salle {room_data['code']}",
                'building': room_data['building'],
                'room_type': room_data['type'],
                'capacity': room_data['capacity'],
                'floor': room_data['floor'],
                'has_projector': room_data['projector'],
                'has_computer': room_data['computer'],
                'is_laboratory': room_data['lab'],
                'has_audio_system': room_data['audio']
            }
        )
        rooms.append(room)
    
    # 5. Cours
    print("📚 Création des cours...")
    courses_data = [
        # Médecine L1
        {'code': 'MED-L1-001', 'name': 'Anatomie Générale', 'dept': dept_medecine, 'teacher': teachers[0], 'type': 'CM', 'level': 'L1', 'credits': 6, 'hours_week': 4, 'total_hours': 60, 'max_students': 120, 'projector': True, 'lab': False},
        {'code': 'MED-L1-002', 'name': 'Physiologie Humaine', 'dept': dept_medecine, 'teacher': teachers[1], 'type': 'CM', 'level': 'L1', 'credits': 5, 'hours_week': 3, 'total_hours': 45, 'max_students': 120, 'projector': True, 'lab': False},
        {'code': 'MED-L1-003', 'name': 'Histologie', 'dept': dept_medecine, 'teacher': teachers[0], 'type': 'TP', 'level': 'L1', 'credits': 4, 'hours_week': 2, 'total_hours': 30, 'max_students': 24, 'projector': False, 'lab': True},
        {'code': 'MED-L1-004', 'name': 'Biophysique', 'dept': dept_medecine, 'teacher': teachers[1], 'type': 'TD', 'level': 'L1', 'credits': 3, 'hours_week': 2, 'total_hours': 30, 'max_students': 50, 'projector': True, 'lab': False},
        
        # Médecine L2
        {'code': 'MED-L2-001', 'name': 'Anatomie Pathologique', 'dept': dept_medecine, 'teacher': teachers[0], 'type': 'CM', 'level': 'L2', 'credits': 5, 'hours_week': 3, 'total_hours': 45, 'max_students': 100, 'projector': True, 'lab': False},
        {'code': 'MED-L2-002', 'name': 'Pharmacologie Générale', 'dept': dept_medecine, 'teacher': teachers[2], 'type': 'CM', 'level': 'L2', 'credits': 4, 'hours_week': 3, 'total_hours': 45, 'max_students': 100, 'projector': True, 'lab': False},
        {'code': 'MED-L2-003', 'name': 'Microbiologie', 'dept': dept_medecine, 'teacher': teachers[3], 'type': 'TP', 'level': 'L2', 'credits': 4, 'hours_week': 2, 'total_hours': 30, 'max_students': 20, 'projector': False, 'lab': True},
        
        # Médecine L3
        {'code': 'MED-L3-001', 'name': 'Chirurgie Générale', 'dept': dept_medecine, 'teacher': teachers[4], 'type': 'CM', 'level': 'L3', 'credits': 6, 'hours_week': 4, 'total_hours': 60, 'max_students': 80, 'projector': True, 'lab': False},
        {'code': 'MED-L3-002', 'name': 'Médecine d\'Urgence', 'dept': dept_medecine, 'teacher': teachers[4], 'type': 'TD', 'level': 'L3', 'credits': 4, 'hours_week': 2, 'total_hours': 30, 'max_students': 40, 'projector': True, 'lab': False},
        
        # Pharmacie
        {'code': 'PHAR-L1-001', 'name': 'Chimie Pharmaceutique', 'dept': dept_pharmacie, 'teacher': teachers[2], 'type': 'CM', 'level': 'L1', 'credits': 5, 'hours_week': 3, 'total_hours': 45, 'max_students': 60, 'projector': True, 'lab': False},
        {'code': 'PHAR-L1-002', 'name': 'Galénique', 'dept': dept_pharmacie, 'teacher': teachers[2], 'type': 'TP', 'level': 'L1', 'credits': 4, 'hours_week': 2, 'total_hours': 30, 'max_students': 20, 'projector': False, 'lab': True},
    ]
    
    courses = []
    for course_data in courses_data:
        course, _ = Course.objects.get_or_create(
            code=course_data['code'],
            defaults={
                'name': course_data['name'],
                'department': course_data['dept'],
                'teacher': course_data['teacher'],
                'course_type': course_data['type'],
                'level': course_data['level'],
                'credits': course_data['credits'],
                'hours_per_week': course_data['hours_week'],
                'total_hours': course_data['total_hours'],
                'max_students': course_data['max_students'],
                'min_room_capacity': course_data['max_students'] + 10,
                'requires_projector': course_data['projector'],
                'requires_laboratory': course_data['lab'],
                'semester': 'S1',
                'academic_year': '2024-2025'
            }
        )
        courses.append(course)
    
    # 6. Curriculum
    print("📋 Création des curriculums...")
    
    curriculum_med_l1, _ = Curriculum.objects.get_or_create(
        code='MED-L1',
        defaults={
            'name': 'Médecine - Licence 1',
            'department': dept_medecine,
            'level': 'L1',
            'total_credits': 60,
            'academic_year': '2024-2025'
        }
    )
    
    curriculum_med_l2, _ = Curriculum.objects.get_or_create(
        code='MED-L2',
        defaults={
            'name': 'Médecine - Licence 2',
            'department': dept_medecine,
            'level': 'L2',
            'total_credits': 60,
            'academic_year': '2024-2025'
        }
    )
    
    curriculum_med_l3, _ = Curriculum.objects.get_or_create(
        code='MED-L3',
        defaults={
            'name': 'Médecine - Licence 3',
            'department': dept_medecine,
            'level': 'L3',
            'total_credits': 60,
            'academic_year': '2024-2025'
        }
    )
    
    curriculum_phar_l1, _ = Curriculum.objects.get_or_create(
        code='PHAR-L1',
        defaults={
            'name': 'Pharmacie - Licence 1',
            'department': dept_pharmacie,
            'level': 'L1',
            'total_credits': 60,
            'academic_year': '2024-2025'
        }
    )
    
    # Association cours-curriculum
    # Médecine L1
    for i, course in enumerate([c for c in courses if c.level == 'L1' and c.department == dept_medecine]):
        CurriculumCourse.objects.get_or_create(
            curriculum=curriculum_med_l1,
            course=course,
            defaults={'semester': 'S1', 'order': i+1}
        )
    
    # Médecine L2
    for i, course in enumerate([c for c in courses if c.level == 'L2' and c.department == dept_medecine]):
        CurriculumCourse.objects.get_or_create(
            curriculum=curriculum_med_l2,
            course=course,
            defaults={'semester': 'S1', 'order': i+1}
        )
    
    # Médecine L3
    for i, course in enumerate([c for c in courses if c.level == 'L3' and c.department == dept_medecine]):
        CurriculumCourse.objects.get_or_create(
            curriculum=curriculum_med_l3,
            course=course,
            defaults={'semester': 'S1', 'order': i+1}
        )
    
    # Pharmacie L1
    for i, course in enumerate([c for c in courses if c.level == 'L1' and c.department == dept_pharmacie]):
        CurriculumCourse.objects.get_or_create(
            curriculum=curriculum_phar_l1,
            course=course,
            defaults={'semester': 'S1', 'order': i+1}
        )
    
    # 7. Étudiants
    print("🎓 Création des étudiants...")
    
    students_data = [
        {'username': 'etudiant1', 'first_name': 'Pierre', 'last_name': 'Ngono', 'student_id': 'MED001', 'curriculum': curriculum_med_l1, 'level': 'L1'},
        {'username': 'etudiant2', 'first_name': 'Marie', 'last_name': 'Ateba', 'student_id': 'MED002', 'curriculum': curriculum_med_l1, 'level': 'L1'},
        {'username': 'etudiant3', 'first_name': 'Joseph', 'last_name': 'Essomba', 'student_id': 'MED003', 'curriculum': curriculum_med_l2, 'level': 'L2'},
        {'username': 'etudiant4', 'first_name': 'Grace', 'last_name': 'Mengue', 'student_id': 'MED004', 'curriculum': curriculum_med_l3, 'level': 'L3'},
        {'username': 'etudiant5', 'first_name': 'Paul', 'last_name': 'Owona', 'student_id': 'PHAR001', 'curriculum': curriculum_phar_l1, 'level': 'L1'},
    ]
    
    students = []
    for student_data in students_data:
        user, created = User.objects.get_or_create(
            username=student_data['username'],
            defaults={
                'email': f"{student_data['username']}@oapet.com",
                'first_name': student_data['first_name'],
                'last_name': student_data['last_name'],
                'is_staff': False
            }
        )
        if created:
            user.set_password('student123')
            user.save()
        
        student, _ = Student.objects.get_or_create(
            user=user,
            defaults={
                'student_id': student_data['student_id'],
                'curriculum': student_data['curriculum'],
                'current_level': student_data['level'],
                'entry_year': 2024
            }
        )
        students.append(student)
    
    # 8. Périodes académiques
    print("📅 Création des périodes académiques...")
    
    current_period, _ = AcademicPeriod.objects.get_or_create(
        name='Semestre 1 - 2024/2025',
        defaults={
            'start_date': date(2024, 9, 1),
            'end_date': date(2025, 1, 31),
            'is_current': True,
            'academic_year': '2024-2025',
            'semester': 'S1'
        }
    )
    
    # 9. Créneaux horaires
    print("⏰ Création des créneaux horaires...")
    
    time_slots_data = [
        # Lundi
        {'day': 'monday', 'start': time(8, 0), 'end': time(10, 0), 'name': 'Lundi 08h-10h'},
        {'day': 'monday', 'start': time(10, 30), 'end': time(12, 30), 'name': 'Lundi 10h30-12h30'},
        {'day': 'monday', 'start': time(14, 0), 'end': time(16, 0), 'name': 'Lundi 14h-16h'},
        {'day': 'monday', 'start': time(16, 30), 'end': time(18, 30), 'name': 'Lundi 16h30-18h30'},
        
        # Mardi
        {'day': 'tuesday', 'start': time(8, 0), 'end': time(10, 0), 'name': 'Mardi 08h-10h'},
        {'day': 'tuesday', 'start': time(10, 30), 'end': time(12, 30), 'name': 'Mardi 10h30-12h30'},
        {'day': 'tuesday', 'start': time(14, 0), 'end': time(16, 0), 'name': 'Mardi 14h-16h'},
        {'day': 'tuesday', 'start': time(16, 30), 'end': time(18, 30), 'name': 'Mardi 16h30-18h30'},
        
        # Mercredi
        {'day': 'wednesday', 'start': time(8, 0), 'end': time(10, 0), 'name': 'Mercredi 08h-10h'},
        {'day': 'wednesday', 'start': time(10, 30), 'end': time(12, 30), 'name': 'Mercredi 10h30-12h30'},
        {'day': 'wednesday', 'start': time(14, 0), 'end': time(16, 0), 'name': 'Mercredi 14h-16h'},
        
        # Jeudi
        {'day': 'thursday', 'start': time(8, 0), 'end': time(10, 0), 'name': 'Jeudi 08h-10h'},
        {'day': 'thursday', 'start': time(10, 30), 'end': time(12, 30), 'name': 'Jeudi 10h30-12h30'},
        {'day': 'thursday', 'start': time(14, 0), 'end': time(16, 0), 'name': 'Jeudi 14h-16h'},
        {'day': 'thursday', 'start': time(16, 30), 'end': time(18, 30), 'name': 'Jeudi 16h30-18h30'},
        
        # Vendredi
        {'day': 'friday', 'start': time(8, 0), 'end': time(10, 0), 'name': 'Vendredi 08h-10h'},
        {'day': 'friday', 'start': time(10, 30), 'end': time(12, 30), 'name': 'Vendredi 10h30-12h30'},
        {'day': 'friday', 'start': time(14, 0), 'end': time(16, 0), 'name': 'Vendredi 14h-16h'},
    ]
    
    time_slots = []
    for slot_data in time_slots_data:
        slot, _ = TimeSlot.objects.get_or_create(
            day_of_week=slot_data['day'],
            start_time=slot_data['start'],
            end_time=slot_data['end'],
            defaults={'name': slot_data['name']}
        )
        time_slots.append(slot)
    
    # 10. Emplois du temps
    print("📋 Création des emplois du temps...")
    
    schedule_med_l1, _ = Schedule.objects.get_or_create(
        name='Emploi du temps Médecine L1 - S1 2024/2025',
        defaults={
            'academic_period': current_period,
            'curriculum': curriculum_med_l1,
            'level': 'L1',
            'description': 'Planning pour les étudiants de première année médecine',
            'created_by': admin_user,
            'is_published': True,
            'published_at': timezone.now()
        }
    )
    
    schedule_med_l2, _ = Schedule.objects.get_or_create(
        name='Emploi du temps Médecine L2 - S1 2024/2025',
        defaults={
            'academic_period': current_period,
            'curriculum': curriculum_med_l2,
            'level': 'L2',
            'description': 'Planning pour les étudiants de deuxième année médecine',
            'created_by': admin_user,
            'is_published': True,
            'published_at': timezone.now()
        }
    )
    
    # 11. Sessions d'emploi du temps (exemples)
    print("📅 Création des sessions d'emploi du temps...")
    
    # Quelques sessions pour Médecine L1
    sessions_data = [
        # Lundi
        {'schedule': schedule_med_l1, 'course': courses[0], 'room': rooms[0], 'teacher': teachers[0], 'slot': time_slots[0], 'type': 'CM'},  # Anatomie Amphi A
        {'schedule': schedule_med_l1, 'course': courses[1], 'room': rooms[1], 'teacher': teachers[1], 'slot': time_slots[1], 'type': 'CM'},  # Physiologie Amphi B
        
        # Mardi  
        {'schedule': schedule_med_l1, 'course': courses[2], 'room': rooms[5], 'teacher': teachers[0], 'slot': time_slots[4], 'type': 'TP'},  # Histologie Labo
        {'schedule': schedule_med_l1, 'course': courses[3], 'room': rooms[2], 'teacher': teachers[1], 'slot': time_slots[5], 'type': 'TD'},  # Biophysique
        
        # Mercredi
        {'schedule': schedule_med_l1, 'course': courses[0], 'room': rooms[0], 'teacher': teachers[0], 'slot': time_slots[8], 'type': 'CM'},  # Anatomie
        
        # Jeudi
        {'schedule': schedule_med_l1, 'course': courses[1], 'room': rooms[1], 'teacher': teachers[1], 'slot': time_slots[11], 'type': 'CM'},  # Physiologie
        
        # Sessions pour Médecine L2
        {'schedule': schedule_med_l2, 'course': courses[4], 'room': rooms[1], 'teacher': teachers[0], 'slot': time_slots[0], 'type': 'CM'},  # Anatomie Pathologique
        {'schedule': schedule_med_l2, 'course': courses[5], 'room': rooms[2], 'teacher': teachers[2], 'slot': time_slots[4], 'type': 'CM'},  # Pharmacologie
        {'schedule': schedule_med_l2, 'course': courses[6], 'room': rooms[5], 'teacher': teachers[3], 'slot': time_slots[8], 'type': 'TP'},  # Microbiologie
    ]
    
    for session_data in sessions_data:
        session, _ = ScheduleSession.objects.get_or_create(
            schedule=session_data['schedule'],
            course=session_data['course'],
            room=session_data['room'],
            teacher=session_data['teacher'],
            time_slot=session_data['slot'],
            defaults={
                'session_type': session_data['type'],
                'expected_students': session_data['course'].max_students,
                'difficulty_score': 0.5,  # Score par défaut
                'complexity_level': 'Moyenne',
                'scheduling_priority': 2
            }
        )
    
    print("✅ Données de test créées avec succès!")
    print(f"   • {Department.objects.count()} départements")
    print(f"   • {Teacher.objects.count()} enseignants")
    print(f"   • {Course.objects.count()} cours")
    print(f"   • {Room.objects.count()} salles")
    print(f"   • {Student.objects.count()} étudiants")
    print(f"   • {Schedule.objects.count()} emplois du temps")
    print(f"   • {ScheduleSession.objects.count()} sessions programmées")
    print("\n🔑 Comptes créés:")
    print("   • Admin: admin / admin123")
    print("   • Enseignants: dr.kamga, dr.mbarga, etc. / teacher123")
    print("   • Étudiants: etudiant1, etudiant2, etc. / student123")

if __name__ == '__main__':
    create_test_data()