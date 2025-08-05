#!/usr/bin/env python3
"""
OAPET Schedule Seeder - Nouveau fichier de génération de données
Crée des données complètes et réalistes pour le système d'emploi du temps
"""

import os
import sys
from datetime import date, time, datetime, timedelta

# Configuration Django AVANT les imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oapet_schedule_backend.settings')

# Configurer Django
import django
django.setup()

# Maintenant on peut importer Django
from django.utils import timezone
from django.contrib.auth.models import User

from courses.models import (
    Department, Teacher, Course, Curriculum, CurriculumCourse, Student, CourseEnrollment
)
from rooms.models import Building, RoomType, Room
from schedules.models import (
    AcademicPeriod, TimeSlot, Schedule, ScheduleSession, Conflict
)


class OAPETSeeder:
    """Classe principale pour le seeding des données OAPET"""
    
    def __init__(self):
        self.users = {}
        self.departments = {}
        self.teachers = {}
        self.courses = {}
        self.curricula = {}
        self.buildings = {}
        self.room_types = {}
        self.rooms = {}
        self.academic_period = None
        self.time_slots = {}
        self.schedules = {}
        
    def clear_database(self):
        """Vide complètement la base de données"""
        print("[CLEAN]  Suppression de toutes les données existantes...")
        
        # Ordre important pour éviter les erreurs de clés étrangères
        ScheduleSession.objects.all().delete()
        Conflict.objects.all().delete()
        Schedule.objects.all().delete()
        TimeSlot.objects.all().delete()
        AcademicPeriod.objects.all().delete()
        
        CourseEnrollment.objects.all().delete()
        CurriculumCourse.objects.all().delete()
        Student.objects.all().delete()
        Course.objects.all().delete()
        Curriculum.objects.all().delete()
        Teacher.objects.all().delete()
        
        Room.objects.all().delete()
        RoomType.objects.all().delete()
        Building.objects.all().delete()
        Department.objects.all().delete()
        
        # Supprimer tous les utilisateurs sauf les superusers
        User.objects.filter(is_superuser=False).delete()
        
        print("[OK] Base de données nettoyée")
    
    def create_users(self):
        """Crée les utilisateurs du système"""
        print("[USERS] Création des utilisateurs...")
        
        # Admin principal
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@oapet.edu.cm',
                'first_name': 'Admin',
                'last_name': 'OAPET',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True
            }
        )
        if created:
            admin.set_password('admin123')
            admin.save()
        self.users['admin'] = admin
        
        # Utilisateurs enseignants
        teachers_data = [
            {'username': 'dr.mballa', 'first_name': 'Jean-Paul', 'last_name': 'Mballa', 'email': 'mballa@oapet.edu.cm'},
            {'username': 'dr.nguema', 'first_name': 'Marie-Claire', 'last_name': 'Nguema', 'email': 'nguema@oapet.edu.cm'},
            {'username': 'pr.fotso', 'first_name': 'Bernard', 'last_name': 'Fotso', 'email': 'fotso@oapet.edu.cm'},
            {'username': 'dr.atangana', 'first_name': 'Alice', 'last_name': 'Atangana', 'email': 'atangana@oapet.edu.cm'},
            {'username': 'pr.kamga', 'first_name': 'Paul', 'last_name': 'Kamga', 'email': 'kamga@oapet.edu.cm'},
            {'username': 'dr.essomba', 'first_name': 'Grace', 'last_name': 'Essomba', 'email': 'essomba@oapet.edu.cm'},
        ]
        
        for teacher_data in teachers_data:
            user, created = User.objects.get_or_create(
                username=teacher_data['username'],
                defaults={
                    'email': teacher_data['email'],
                    'first_name': teacher_data['first_name'],
                    'last_name': teacher_data['last_name'],
                    'is_staff': True,
                    'is_active': True
                }
            )
            if created:
                user.set_password('teacher123')
                user.save()
            self.users[teacher_data['username']] = user
        
        print(f"[OK] {len(self.users)} utilisateurs créés")
    
    def create_departments(self):
        """Crée les départements"""
        print("[DEPT]  Création des départements...")
        
        departments_data = [
            {
                'code': 'MED',
                'name': 'Médecine',
                'description': 'Faculté de Médecine et des Sciences Biomédicales',
                'head': 'admin'
            },
            {
                'code': 'PHAR',
                'name': 'Pharmacie', 
                'description': 'Faculté de Pharmacie',
                'head': 'admin'
            },
            {
                'code': 'BIO',
                'name': 'Biologie',
                'description': 'Département de Biologie et Sciences de la Vie',
                'head': 'admin'
            },
            {
                'code': 'CHIM',
                'name': 'Chimie',
                'description': 'Département de Chimie',
                'head': 'admin'
            }
        ]
        
        for dept_data in departments_data:
            dept, created = Department.objects.get_or_create(
                code=dept_data['code'],
                defaults={
                    'name': dept_data['name'],
                    'description': dept_data['description'],
                    'head_of_department': self.users[dept_data['head']],
                    'is_active': True
                }
            )
            self.departments[dept_data['code']] = dept
        
        print(f"[OK] {len(self.departments)} départements créés")
    
    def create_teachers(self):
        """Crée les enseignants"""
        print("[TEACHERS] Création des enseignants...")
        
        teachers_data = [
            {
                'user': 'dr.mballa',
                'employee_id': 'T001',
                'department': 'MED',
                'specializations': ['Anatomie', 'Histologie'],
                'max_hours': 20,
                'preferred_days': ['monday', 'tuesday', 'wednesday', 'thursday']
            },
            {
                'user': 'dr.nguema',
                'employee_id': 'T002',
                'department': 'MED',
                'specializations': ['Physiologie', 'Biophysique'],
                'max_hours': 18,
                'preferred_days': ['monday', 'wednesday', 'thursday', 'friday']
            },
            {
                'user': 'pr.fotso',
                'employee_id': 'T003',
                'department': 'PHAR',
                'specializations': ['Pharmacologie', 'Toxicologie'],
                'max_hours': 22,
                'preferred_days': ['tuesday', 'wednesday', 'thursday', 'friday']
            },
            {
                'user': 'dr.atangana',
                'employee_id': 'T004',
                'department': 'BIO',
                'specializations': ['Microbiologie', 'Immunologie'],
                'max_hours': 16,
                'preferred_days': ['monday', 'tuesday', 'thursday', 'friday']
            },
            {
                'user': 'pr.kamga',
                'employee_id': 'T005',
                'department': 'MED',
                'specializations': ['Chirurgie', 'Urgences Médicales'],
                'max_hours': 15,
                'preferred_days': ['monday', 'wednesday', 'friday']
            },
            {
                'user': 'dr.essomba',
                'employee_id': 'T006',
                'department': 'CHIM',
                'specializations': ['Chimie Organique', 'Chimie Analytique'],
                'max_hours': 20,
                'preferred_days': ['tuesday', 'wednesday', 'thursday', 'friday']
            }
        ]
        
        for teacher_data in teachers_data:
            teacher, created = Teacher.objects.get_or_create(
                user=self.users[teacher_data['user']],
                defaults={
                    'employee_id': teacher_data['employee_id'],
                    'department': self.departments[teacher_data['department']],
                    'specializations': teacher_data['specializations'],
                    'max_hours_per_week': teacher_data['max_hours'],
                    'preferred_days': teacher_data['preferred_days'],
                    'is_active': True
                }
            )
            self.teachers[teacher_data['employee_id']] = teacher
        
        print(f"[OK] {len(self.teachers)} enseignants créés")
    
    def create_buildings_and_rooms(self):
        """Crée les bâtiments et salles"""
        print("[BUILDINGS] Création des bâtiments et salles...")
        
        # Bâtiments
        buildings_data = [
            {
                'code': 'BAT-PRINCIPAL',
                'name': 'Bâtiment Principal',
                'address': 'Campus OAPET, Douala',
                'floors': 4
            },
            {
                'code': 'BAT-SCIENCES',
                'name': 'Bâtiment des Sciences',
                'address': 'Campus OAPET, Douala',
                'floors': 3
            },
            {
                'code': 'BAT-MEDECINE',
                'name': 'Bâtiment Médecine',
                'address': 'Campus OAPET, Douala', 
                'floors': 5
            }
        ]
        
        for building_data in buildings_data:
            building, created = Building.objects.get_or_create(
                code=building_data['code'],
                defaults={
                    'name': building_data['name'],
                    'address': building_data['address'],
                    'total_floors': building_data['floors'],
                    'is_active': True
                }
            )
            self.buildings[building_data['code']] = building
        
        # Types de salles
        room_types_data = [
            {'name': 'Amphithéâtre', 'description': 'Grande salle pour cours magistraux'},
            {'name': 'Salle de cours', 'description': 'Salle de cours standard'},
            {'name': 'Laboratoire', 'description': 'Laboratoire pour travaux pratiques'},
            {'name': 'Salle de TD', 'description': 'Salle pour travaux dirigés'},
            {'name': 'Salle d\'examen', 'description': 'Salle dédiée aux examens'}
        ]
        
        for room_type_data in room_types_data:
            room_type, created = RoomType.objects.get_or_create(
                name=room_type_data['name'],
                defaults={'description': room_type_data['description']}
            )
            self.room_types[room_type_data['name']] = room_type
        
        # Salles
        rooms_data = [
            # Amphithéâtres
            {'code': 'AMPHI-A', 'name': 'Amphithéâtre A', 'building': 'BAT-PRINCIPAL', 'type': 'Amphithéâtre', 'capacity': 250, 'floor': 1, 'projector': True, 'computer': False, 'lab': False, 'audio': True},
            {'code': 'AMPHI-B', 'name': 'Amphithéâtre B', 'building': 'BAT-PRINCIPAL', 'type': 'Amphithéâtre', 'capacity': 200, 'floor': 1, 'projector': True, 'computer': False, 'lab': False, 'audio': True},
            {'code': 'AMPHI-MED', 'name': 'Amphithéâtre Médecine', 'building': 'BAT-MEDECINE', 'type': 'Amphithéâtre', 'capacity': 300, 'floor': 1, 'projector': True, 'computer': True, 'lab': False, 'audio': True},
            
            # Salles de cours
            {'code': 'SALLE-101', 'name': 'Salle 101', 'building': 'BAT-PRINCIPAL', 'type': 'Salle de cours', 'capacity': 60, 'floor': 1, 'projector': True, 'computer': True, 'lab': False, 'audio': False},
            {'code': 'SALLE-102', 'name': 'Salle 102', 'building': 'BAT-PRINCIPAL', 'type': 'Salle de cours', 'capacity': 50, 'floor': 1, 'projector': True, 'computer': True, 'lab': False, 'audio': False},
            {'code': 'SALLE-201', 'name': 'Salle 201', 'building': 'BAT-PRINCIPAL', 'type': 'Salle de cours', 'capacity': 45, 'floor': 2, 'projector': True, 'computer': False, 'lab': False, 'audio': False},
            {'code': 'SALLE-MED-101', 'name': 'Salle Médecine 101', 'building': 'BAT-MEDECINE', 'type': 'Salle de cours', 'capacity': 80, 'floor': 1, 'projector': True, 'computer': True, 'lab': False, 'audio': True},
            
            # Laboratoires
            {'code': 'LABO-BIO-1', 'name': 'Laboratoire Biologie 1', 'building': 'BAT-SCIENCES', 'type': 'Laboratoire', 'capacity': 24, 'floor': 1, 'projector': False, 'computer': True, 'lab': True, 'audio': False},
            {'code': 'LABO-CHIM-1', 'name': 'Laboratoire Chimie 1', 'building': 'BAT-SCIENCES', 'type': 'Laboratoire', 'capacity': 20, 'floor': 2, 'projector': False, 'computer': True, 'lab': True, 'audio': False},
            {'code': 'LABO-ANAT', 'name': 'Laboratoire Anatomie', 'building': 'BAT-MEDECINE', 'type': 'Laboratoire', 'capacity': 30, 'floor': 2, 'projector': True, 'computer': True, 'lab': True, 'audio': True},
            
            # Salles TD
            {'code': 'TD-101', 'name': 'TD 101', 'building': 'BAT-PRINCIPAL', 'type': 'Salle de TD', 'capacity': 35, 'floor': 2, 'projector': True, 'computer': True, 'lab': False, 'audio': False},
            {'code': 'TD-102', 'name': 'TD 102', 'building': 'BAT-PRINCIPAL', 'type': 'Salle de TD', 'capacity': 30, 'floor': 2, 'projector': True, 'computer': True, 'lab': False, 'audio': False}
        ]
        
        for room_data in rooms_data:
            room, created = Room.objects.get_or_create(
                code=room_data['code'],
                defaults={
                    'name': room_data['name'],
                    'building': self.buildings[room_data['building']],
                    'room_type': self.room_types[room_data['type']],
                    'capacity': room_data['capacity'],
                    'floor': room_data['floor'],
                    'has_projector': room_data['projector'],
                    'has_computer': room_data['computer'],
                    'is_laboratory': room_data['lab'],
                    'has_audio_system': room_data['audio'],
                    'is_active': True
                }
            )
            self.rooms[room_data['code']] = room
        
        print(f"[OK] {len(self.buildings)} bâtiments et {len(self.rooms)} salles créés")
    
    def create_courses(self):
        """Crée les cours"""
        print("[COURSES] Création des cours...")
        
        courses_data = [
            # Médecine L1
            {'code': 'MED-L1-001', 'name': 'Anatomie Générale', 'dept': 'MED', 'teacher': 'T001', 'type': 'CM', 'level': 'L1', 'credits': 6, 'hours_week': 4, 'total_hours': 60, 'max_students': 150, 'projector': True, 'lab': False},
            {'code': 'MED-L1-002', 'name': 'Physiologie Humaine', 'dept': 'MED', 'teacher': 'T002', 'type': 'CM', 'level': 'L1', 'credits': 5, 'hours_week': 3, 'total_hours': 45, 'max_students': 150, 'projector': True, 'lab': False},
            {'code': 'MED-L1-003', 'name': 'Histologie Pratique', 'dept': 'MED', 'teacher': 'T001', 'type': 'TP', 'level': 'L1', 'credits': 4, 'hours_week': 2, 'total_hours': 30, 'max_students': 30, 'projector': False, 'lab': True},
            {'code': 'MED-L1-004', 'name': 'Biophysique', 'dept': 'MED', 'teacher': 'T002', 'type': 'TD', 'level': 'L1', 'credits': 3, 'hours_week': 2, 'total_hours': 30, 'max_students': 50, 'projector': True, 'lab': False},
            
            # Médecine L2
            {'code': 'MED-L2-001', 'name': 'Anatomie Pathologique', 'dept': 'MED', 'teacher': 'T001', 'type': 'CM', 'level': 'L2', 'credits': 5, 'hours_week': 3, 'total_hours': 45, 'max_students': 120, 'projector': True, 'lab': False},
            {'code': 'MED-L2-002', 'name': 'Pharmacologie Générale', 'dept': 'MED', 'teacher': 'T003', 'type': 'CM', 'level': 'L2', 'credits': 4, 'hours_week': 3, 'total_hours': 45, 'max_students': 120, 'projector': True, 'lab': False},
            {'code': 'MED-L2-003', 'name': 'Microbiologie Médicale', 'dept': 'MED', 'teacher': 'T004', 'type': 'TP', 'level': 'L2', 'credits': 4, 'hours_week': 2, 'total_hours': 30, 'max_students': 24, 'projector': False, 'lab': True},
            
            # Médecine L3
            {'code': 'MED-L3-001', 'name': 'Chirurgie Générale', 'dept': 'MED', 'teacher': 'T005', 'type': 'CM', 'level': 'L3', 'credits': 6, 'hours_week': 4, 'total_hours': 60, 'max_students': 100, 'projector': True, 'lab': False},
            {'code': 'MED-L3-002', 'name': 'Médecine d\'Urgence', 'dept': 'MED', 'teacher': 'T005', 'type': 'TD', 'level': 'L3', 'credits': 4, 'hours_week': 2, 'total_hours': 30, 'max_students': 40, 'projector': True, 'lab': False},
            
            # Pharmacie
            {'code': 'PHAR-L1-001', 'name': 'Chimie Pharmaceutique', 'dept': 'PHAR', 'teacher': 'T003', 'type': 'CM', 'level': 'L1', 'credits': 5, 'hours_week': 3, 'total_hours': 45, 'max_students': 80, 'projector': True, 'lab': False},
            {'code': 'PHAR-L1-002', 'name': 'Galénique', 'dept': 'PHAR', 'teacher': 'T003', 'type': 'TP', 'level': 'L1', 'credits': 4, 'hours_week': 2, 'total_hours': 30, 'max_students': 20, 'projector': False, 'lab': True},
            
            # Biologie
            {'code': 'BIO-L1-001', 'name': 'Biologie Cellulaire', 'dept': 'BIO', 'teacher': 'T004', 'type': 'CM', 'level': 'L1', 'credits': 5, 'hours_week': 3, 'total_hours': 45, 'max_students': 60, 'projector': True, 'lab': False},
            {'code': 'BIO-L1-002', 'name': 'Microbiologie Pratique', 'dept': 'BIO', 'teacher': 'T004', 'type': 'TP', 'level': 'L1', 'credits': 4, 'hours_week': 2, 'total_hours': 30, 'max_students': 24, 'projector': False, 'lab': True},
            
            # Chimie
            {'code': 'CHIM-L1-001', 'name': 'Chimie Organique', 'dept': 'CHIM', 'teacher': 'T006', 'type': 'CM', 'level': 'L1', 'credits': 5, 'hours_week': 3, 'total_hours': 45, 'max_students': 50, 'projector': True, 'lab': False},
            {'code': 'CHIM-L1-002', 'name': 'Chimie Analytique TP', 'dept': 'CHIM', 'teacher': 'T006', 'type': 'TP', 'level': 'L1', 'credits': 4, 'hours_week': 2, 'total_hours': 30, 'max_students': 20, 'projector': False, 'lab': True}
        ]
        
        for course_data in courses_data:
            course, created = Course.objects.get_or_create(
                code=course_data['code'],
                defaults={
                    'name': course_data['name'],
                    'department': self.departments[course_data['dept']],
                    'teacher': self.teachers[course_data['teacher']],
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
                    'academic_year': '2024-2025',
                    'is_active': True
                }
            )
            self.courses[course_data['code']] = course
        
        print(f"[OK] {len(self.courses)} cours créés")
    
    def create_curricula(self):
        """Crée les curriculums et associations"""
        print("[CURRICULUM] Création des curriculums...")
        
        curricula_data = [
            {'code': 'MED-L1', 'name': 'Médecine - Licence 1', 'dept': 'MED', 'level': 'L1', 'credits': 60},
            {'code': 'MED-L2', 'name': 'Médecine - Licence 2', 'dept': 'MED', 'level': 'L2', 'credits': 60},
            {'code': 'MED-L3', 'name': 'Médecine - Licence 3', 'dept': 'MED', 'level': 'L3', 'credits': 60},
            {'code': 'PHAR-L1', 'name': 'Pharmacie - Licence 1', 'dept': 'PHAR', 'level': 'L1', 'credits': 60},
            {'code': 'BIO-L1', 'name': 'Biologie - Licence 1', 'dept': 'BIO', 'level': 'L1', 'credits': 60},
            {'code': 'CHIM-L1', 'name': 'Chimie - Licence 1', 'dept': 'CHIM', 'level': 'L1', 'credits': 60}
        ]
        
        for curriculum_data in curricula_data:
            curriculum, created = Curriculum.objects.get_or_create(
                code=curriculum_data['code'],
                defaults={
                    'name': curriculum_data['name'],
                    'department': self.departments[curriculum_data['dept']],
                    'level': curriculum_data['level'],
                    'total_credits': curriculum_data['credits'],
                    'academic_year': '2024-2025',
                    'is_active': True
                }
            )
            self.curricula[curriculum_data['code']] = curriculum
        
        # Association cours-curriculum
        associations = [
            # Médecine L1
            ('MED-L1', ['MED-L1-001', 'MED-L1-002', 'MED-L1-003', 'MED-L1-004']),
            # Médecine L2
            ('MED-L2', ['MED-L2-001', 'MED-L2-002', 'MED-L2-003']),
            # Médecine L3
            ('MED-L3', ['MED-L3-001', 'MED-L3-002']),
            # Pharmacie L1
            ('PHAR-L1', ['PHAR-L1-001', 'PHAR-L1-002']),
            # Biologie L1
            ('BIO-L1', ['BIO-L1-001', 'BIO-L1-002']),
            # Chimie L1
            ('CHIM-L1', ['CHIM-L1-001', 'CHIM-L1-002'])
        ]
        
        for curriculum_code, course_codes in associations:
            for i, course_code in enumerate(course_codes):
                CurriculumCourse.objects.get_or_create(
                    curriculum=self.curricula[curriculum_code],
                    course=self.courses[course_code],
                    defaults={'semester': 'S1', 'order': i + 1}
                )
        
        print(f"[OK] {len(self.curricula)} curriculums créés")
    
    def create_academic_period_and_time_slots(self):
        """Crée la période académique et les créneaux horaires"""
        print("[SCHEDULE] Création de la période académique et créneaux...")
        
        # Période académique courante
        self.academic_period, created = AcademicPeriod.objects.get_or_create(
            name='Semestre 1 - 2024/2025',
            defaults={
                'start_date': date(2024, 9, 1),
                'end_date': date(2025, 1, 31),
                'is_current': True,
                'academic_year': '2024-2025',
                'semester': 'S1'
            }
        )
        
        # Créneaux horaires
        time_slots_data = [
            # Lundi
            {'day': 'monday', 'start': time(8, 0), 'end': time(10, 0), 'name': 'Lundi 08h-10h'},
            {'day': 'monday', 'start': time(10, 30), 'end': time(12, 30), 'name': 'Lundi 10h30-12h30'},
            {'day': 'monday', 'start': time(14, 0), 'end': time(16, 0), 'name': 'Lundi 14h-16h'},
            {'day': 'monday', 'start': time(16, 30), 'end': time(18, 30), 'name': 'Lundi 16h30-18h30'},
            {'day': 'monday', 'start': time(19, 0), 'end': time(21, 0), 'name': 'Lundi 19h-21h'},
            
            # Mardi
            {'day': 'tuesday', 'start': time(8, 0), 'end': time(10, 0), 'name': 'Mardi 08h-10h'},
            {'day': 'tuesday', 'start': time(10, 30), 'end': time(12, 30), 'name': 'Mardi 10h30-12h30'},
            {'day': 'tuesday', 'start': time(14, 0), 'end': time(16, 0), 'name': 'Mardi 14h-16h'},
            {'day': 'tuesday', 'start': time(16, 30), 'end': time(18, 30), 'name': 'Mardi 16h30-18h30'},
            {'day': 'tuesday', 'start': time(19, 0), 'end': time(21, 0), 'name': 'Mardi 19h-21h'},
            
            # Mercredi
            {'day': 'wednesday', 'start': time(8, 0), 'end': time(10, 0), 'name': 'Mercredi 08h-10h'},
            {'day': 'wednesday', 'start': time(10, 30), 'end': time(12, 30), 'name': 'Mercredi 10h30-12h30'},
            {'day': 'wednesday', 'start': time(14, 0), 'end': time(16, 0), 'name': 'Mercredi 14h-16h'},
            {'day': 'wednesday', 'start': time(16, 30), 'end': time(18, 30), 'name': 'Mercredi 16h30-18h30'},
            
            # Jeudi
            {'day': 'thursday', 'start': time(8, 0), 'end': time(10, 0), 'name': 'Jeudi 08h-10h'},
            {'day': 'thursday', 'start': time(10, 30), 'end': time(12, 30), 'name': 'Jeudi 10h30-12h30'},
            {'day': 'thursday', 'start': time(14, 0), 'end': time(16, 0), 'name': 'Jeudi 14h-16h'},
            {'day': 'thursday', 'start': time(16, 30), 'end': time(18, 30), 'name': 'Jeudi 16h30-18h30'},
            {'day': 'thursday', 'start': time(19, 0), 'end': time(21, 0), 'name': 'Jeudi 19h-21h'},
            
            # Vendredi
            {'day': 'friday', 'start': time(8, 0), 'end': time(10, 0), 'name': 'Vendredi 08h-10h'},
            {'day': 'friday', 'start': time(10, 30), 'end': time(12, 30), 'name': 'Vendredi 10h30-12h30'},
            {'day': 'friday', 'start': time(14, 0), 'end': time(16, 0), 'name': 'Vendredi 14h-16h'},
            {'day': 'friday', 'start': time(16, 30), 'end': time(18, 30), 'name': 'Vendredi 16h30-18h30'},
            
            # Samedi (optionnel)
            {'day': 'saturday', 'start': time(8, 0), 'end': time(10, 0), 'name': 'Samedi 08h-10h'},
            {'day': 'saturday', 'start': time(10, 30), 'end': time(12, 30), 'name': 'Samedi 10h30-12h30'}
        ]
        
        for slot_data in time_slots_data:
            slot, created = TimeSlot.objects.get_or_create(
                day_of_week=slot_data['day'],
                start_time=slot_data['start'],
                end_time=slot_data['end'],
                defaults={
                    'name': slot_data['name'],
                    'is_active': True
                }            
            )
            self.time_slots[f"{slot_data['day']}_{slot_data['start']}"] = slot
        
        print(f"[OK] Période académique et {len(self.time_slots)} créneaux créés")
    
    def create_schedules_and_sessions(self):
        """Crée les emplois du temps et leurs sessions"""
        print("[CURRICULUM] Création des emplois du temps et sessions...")
        
        # Emplois du temps
        schedules_data = [
            {'code': 'MED-L1-S1', 'name': 'Emploi du temps Médecine L1 - S1 2024/2025', 'curriculum': 'MED-L1', 'level': 'L1'},
            {'code': 'MED-L2-S1', 'name': 'Emploi du temps Médecine L2 - S1 2024/2025', 'curriculum': 'MED-L2', 'level': 'L2'},
            {'code': 'MED-L3-S1', 'name': 'Emploi du temps Médecine L3 - S1 2024/2025', 'curriculum': 'MED-L3', 'level': 'L3'},
            {'code': 'PHAR-L1-S1', 'name': 'Emploi du temps Pharmacie L1 - S1 2024/2025', 'curriculum': 'PHAR-L1', 'level': 'L1'},
            {'code': 'BIO-L1-S1', 'name': 'Emploi du temps Biologie L1 - S1 2024/2025', 'curriculum': 'BIO-L1', 'level': 'L1'},
            {'code': 'CHIM-L1-S1', 'name': 'Emploi du temps Chimie L1 - S1 2024/2025', 'curriculum': 'CHIM-L1', 'level': 'L1'}
        ]
        
        for schedule_data in schedules_data:
            schedule, created = Schedule.objects.get_or_create(
                name=schedule_data['name'],
                defaults={
                    'academic_period': self.academic_period,
                    'curriculum': self.curricula[schedule_data['curriculum']],
                    'level': schedule_data['level'],
                    'description': f"Planning pour les étudiants {schedule_data['level']}",
                    'created_by': self.users['admin'],
                    'is_published': True,
                    'published_at': timezone.now(),
                    'status': 'published'
                }
            )
            self.schedules[schedule_data['code']] = schedule
        
        # Sessions spécifiques pour le 05/08/2025 (lundi)
        today_date = date(2025, 8, 5)
        today_sessions = [
            # 08h-10h: Anatomie Générale (CM) - Médecine L1
            {
                'schedule': 'MED-L1-S1',
                'course': 'MED-L1-001',
                'room': 'AMPHI-MED',
                'teacher': 'T001',
                'date': today_date,
                'start': time(8, 0),
                'end': time(10, 0),
                'type': 'CM',
                'students': 150
            },
            # 10h30-12h30: Physiologie Humaine (CM) - Médecine L1  
            {
                'schedule': 'MED-L1-S1',
                'course': 'MED-L1-002',
                'room': 'AMPHI-A',
                'teacher': 'T002',
                'date': today_date,
                'start': time(10, 30),
                'end': time(12, 30),
                'type': 'CM',
                'students': 150
            },
            # 14h-16h: Histologie Pratique (TP) - Médecine L1
            {
                'schedule': 'MED-L1-S1',
                'course': 'MED-L1-003',
                'room': 'LABO-ANAT',
                'teacher': 'T001',
                'date': today_date,
                'start': time(14, 0),
                'end': time(16, 0),
                'type': 'TP',
                'students': 30
            },
            # 16h30-18h30: Anatomie Pathologique (CM) - Médecine L2
            {
                'schedule': 'MED-L2-S1',
                'course': 'MED-L2-001',
                'room': 'AMPHI-B',
                'teacher': 'T001',
                'date': today_date,
                'start': time(16, 30),
                'end': time(18, 30),
                'type': 'CM',
                'students': 120
            },
            # 19h-21h: Pharmacologie Générale (EXAMEN) - Médecine L2
            {
                'schedule': 'MED-L2-S1',
                'course': 'MED-L2-002',
                'room': 'AMPHI-MED',
                'teacher': 'T003',
                'date': today_date,
                'start': time(19, 0),
                'end': time(21, 0),
                'type': 'EXAM',
                'students': 120
            },
            # Sessions supplémentaires pour d'autres filières
            # 08h-10h: Chimie Organique (CM) - Chimie L1
            {
                'schedule': 'CHIM-L1-S1',
                'course': 'CHIM-L1-001',
                'room': 'SALLE-101',
                'teacher': 'T006',
                'date': today_date,
                'start': time(8, 0),
                'end': time(10, 0),
                'type': 'CM',
                'students': 50
            },
            # 14h-16h: Biologie Cellulaire (CM) - Biologie L1
            {
                'schedule': 'BIO-L1-S1',
                'course': 'BIO-L1-001',
                'room': 'SALLE-102',
                'teacher': 'T004',
                'date': today_date,
                'start': time(14, 0),
                'end': time(16, 0),
                'type': 'CM',
                'students': 60
            }
        ]
        
        # Créer les sessions pour aujourd'hui
        for session_data in today_sessions:
            # Trouver le time_slot par défaut (on n'en a pas besoin avec specific_date)
            default_slot = list(self.time_slots.values())[0]
            
            session, created = ScheduleSession.objects.get_or_create(
                schedule=self.schedules[session_data['schedule']],
                course=self.courses[session_data['course']],
                room=self.rooms[session_data['room']],
                teacher=self.teachers[session_data['teacher']],
                specific_date=session_data['date'],
                specific_start_time=session_data['start'],
                specific_end_time=session_data['end'],
                defaults={
                    'session_type': session_data['type'],
                    'expected_students': session_data['students'],
                    'difficulty_score': 0.6,
                    'complexity_level': 'Moyenne',
                    'scheduling_priority': 3 if session_data['type'] == 'EXAM' else 2,
                    'time_slot': default_slot,  # Obligatoire mais pas utilisé avec specific_date
                    'is_cancelled': False
                }
            )
        
        print(f"[OK] {len(self.schedules)} emplois du temps et {len(today_sessions)} sessions pour le 05/08/2025 créés")
    
    def create_students(self):
        """Crée quelques étudiants pour les tests"""
        print("[STUDENTS] Création d'étudiants...")
        
        students_data = [
            {'username': 'etudiant.med1', 'first_name': 'Pierre', 'last_name': 'Ngono', 'student_id': 'MED24001', 'curriculum': 'MED-L1'},
            {'username': 'etudiant.med2', 'first_name': 'Marie', 'last_name': 'Ateba', 'student_id': 'MED24002', 'curriculum': 'MED-L1'},
            {'username': 'etudiant.med3', 'first_name': 'Joseph', 'last_name': 'Essomba', 'student_id': 'MED23001', 'curriculum': 'MED-L2'},
            {'username': 'etudiant.phar1', 'first_name': 'Grace', 'last_name': 'Mengue', 'student_id': 'PHAR24001', 'curriculum': 'PHAR-L1'},
            {'username': 'etudiant.bio1', 'first_name': 'Paul', 'last_name': 'Owona', 'student_id': 'BIO24001', 'curriculum': 'BIO-L1'},
        ]
        
        for student_data in students_data:
            user, created = User.objects.get_or_create(
                username=student_data['username'],
                defaults={
                    'email': f"{student_data['username']}@student.oapet.edu.cm",
                    'first_name': student_data['first_name'],
                    'last_name': student_data['last_name'],
                    'is_active': True
                }
            )
            if created:
                user.set_password('student123')
                user.save()
            
            student, created = Student.objects.get_or_create(
                user=user,
                defaults={
                    'student_id': student_data['student_id'],
                    'curriculum': self.curricula[student_data['curriculum']],
                    'current_level': student_data['curriculum'].split('-')[1],
                    'entry_year': 2024 if '24' in student_data['student_id'] else 2023,
                    'is_active': True
                }
            )
        
        print(f"[OK] {len(students_data)} étudiants créés")
    
    def run_seed(self):
        """Lance le processus complet de seeding"""
        print("[SEED] DEMARRAGE DU SEEDING OAPET")
        print("=" * 50)
        
        try:
            self.clear_database()
            self.create_users()
            self.create_departments()
            self.create_teachers()
            self.create_buildings_and_rooms()
            self.create_courses()
            self.create_curricula()
            self.create_academic_period_and_time_slots()
            self.create_schedules_and_sessions()
            self.create_students()
            
            print("\n" + "=" * 50)
            print("[SUCCESS] SEEDING TERMINE AVEC SUCCES!")
            print("\n[RESUME] DONNEES CREEES:")
            print(f"   • {User.objects.count()} utilisateurs")
            print(f"   • {Department.objects.count()} départements")
            print(f"   • {Teacher.objects.count()} enseignants")
            print(f"   • {Building.objects.count()} bâtiments")
            print(f"   • {Room.objects.count()} salles")
            print(f"   • {Course.objects.count()} cours")
            print(f"   • {Curriculum.objects.count()} curriculums")
            print(f"   • {Schedule.objects.count()} emplois du temps")
            print(f"   • {ScheduleSession.objects.count()} sessions programmées")
            print(f"   • {Student.objects.count()} étudiants")
            print(f"   • {AcademicPeriod.objects.count()} période académique")
            print(f"   • {TimeSlot.objects.count()} créneaux horaires")
            
            print("\n[COMPTES] ACCES SYSTEME:")
            print("   • Admin: admin / admin123")
            print("   • Enseignants: dr.mballa, dr.nguema, pr.fotso, etc. / teacher123")
            print("   • Étudiants: etudiant.med1, etudiant.med2, etc. / student123")
            
            print("\n[SESSIONS] COURS POUR LE 05/08/2025:")
            today_sessions = ScheduleSession.objects.filter(specific_date=date(2025, 8, 5))
            for session in today_sessions:
                print(f"   • {session.specific_start_time}-{session.specific_end_time}: {session.course.name} ({session.session_type}) - {session.room.code}")
            
        except Exception as e:
            print(f"\n[ERREUR] ECHEC DU SEEDING: {str(e)}")
            raise


def main():
    """Point d'entrée principal"""
    seeder = OAPETSeeder()
    seeder.run_seed()


if __name__ == '__main__':
    main()