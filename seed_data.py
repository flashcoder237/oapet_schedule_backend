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
            # Médecine avec plusieurs classes par niveau
            {'code': 'MED-L1-A', 'name': 'Médecine - Licence 1 Classe A', 'dept': 'MED', 'level': 'L1', 'credits': 60},
            {'code': 'MED-L1-B', 'name': 'Médecine - Licence 1 Classe B', 'dept': 'MED', 'level': 'L1', 'credits': 60},
            {'code': 'MED-L1-C', 'name': 'Médecine - Licence 1 Classe C', 'dept': 'MED', 'level': 'L1', 'credits': 60},
            {'code': 'MED-L2-A', 'name': 'Médecine - Licence 2 Classe A', 'dept': 'MED', 'level': 'L2', 'credits': 60},
            {'code': 'MED-L2-B', 'name': 'Médecine - Licence 2 Classe B', 'dept': 'MED', 'level': 'L2', 'credits': 60},
            {'code': 'MED-L3-A', 'name': 'Médecine - Licence 3 Classe A', 'dept': 'MED', 'level': 'L3', 'credits': 60},
            {'code': 'MED-L3-B', 'name': 'Médecine - Licence 3 Classe B', 'dept': 'MED', 'level': 'L3', 'credits': 60},
            {'code': 'MED-M1', 'name': 'Médecine - Master 1', 'dept': 'MED', 'level': 'M1', 'credits': 60},
            {'code': 'MED-M2', 'name': 'Médecine - Master 2', 'dept': 'MED', 'level': 'M2', 'credits': 60},
            # Autres filières
            {'code': 'PHAR-L1', 'name': 'Pharmacie - Licence 1', 'dept': 'PHAR', 'level': 'L1', 'credits': 60},
            {'code': 'PHAR-L2', 'name': 'Pharmacie - Licence 2', 'dept': 'PHAR', 'level': 'L2', 'credits': 60},
            {'code': 'BIO-L1', 'name': 'Biologie - Licence 1', 'dept': 'BIO', 'level': 'L1', 'credits': 60},
            {'code': 'BIO-L2', 'name': 'Biologie - Licence 2', 'dept': 'BIO', 'level': 'L2', 'credits': 60},
            {'code': 'CHIM-L1', 'name': 'Chimie - Licence 1', 'dept': 'CHIM', 'level': 'L1', 'credits': 60},
            {'code': 'CHIM-L2', 'name': 'Chimie - Licence 2', 'dept': 'CHIM', 'level': 'L2', 'credits': 60}
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
            # Médecine L1 - toutes les classes ont les mêmes cours de base
            ('MED-L1-A', ['MED-L1-001', 'MED-L1-002', 'MED-L1-003', 'MED-L1-004']),
            ('MED-L1-B', ['MED-L1-001', 'MED-L1-002', 'MED-L1-003', 'MED-L1-004']),
            ('MED-L1-C', ['MED-L1-001', 'MED-L1-002', 'MED-L1-003', 'MED-L1-004']),
            # Médecine L2
            ('MED-L2-A', ['MED-L2-001', 'MED-L2-002', 'MED-L2-003']),
            ('MED-L2-B', ['MED-L2-001', 'MED-L2-002', 'MED-L2-003']),
            # Médecine L3
            ('MED-L3-A', ['MED-L3-001', 'MED-L3-002']),
            ('MED-L3-B', ['MED-L3-001', 'MED-L3-002']),
            # Médecine Master
            ('MED-M1', ['MED-L3-001', 'MED-L3-002']),
            ('MED-M2', ['MED-L3-001', 'MED-L3-002']),
            # Pharmacie
            ('PHAR-L1', ['PHAR-L1-001', 'PHAR-L1-002']),
            ('PHAR-L2', ['PHAR-L1-001', 'PHAR-L1-002']),
            # Biologie
            ('BIO-L1', ['BIO-L1-001', 'BIO-L1-002']),
            ('BIO-L2', ['BIO-L1-001', 'BIO-L1-002']),
            # Chimie
            ('CHIM-L1', ['CHIM-L1-001', 'CHIM-L1-002']),
            ('CHIM-L2', ['CHIM-L1-001', 'CHIM-L1-002'])
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
        print("[SCHEDULES] Création des emplois du temps et sessions...")
        
        # Emplois du temps pour toutes les classes
        schedules_data = [
            # Médecine L1
            {'code': 'MED-L1-A-S1', 'name': 'Emploi du temps Médecine L1 Classe A - S1 2024/2025', 'curriculum': 'MED-L1-A', 'level': 'L1'},
            {'code': 'MED-L1-B-S1', 'name': 'Emploi du temps Médecine L1 Classe B - S1 2024/2025', 'curriculum': 'MED-L1-B', 'level': 'L1'},
            {'code': 'MED-L1-C-S1', 'name': 'Emploi du temps Médecine L1 Classe C - S1 2024/2025', 'curriculum': 'MED-L1-C', 'level': 'L1'},
            # Médecine L2
            {'code': 'MED-L2-A-S1', 'name': 'Emploi du temps Médecine L2 Classe A - S1 2024/2025', 'curriculum': 'MED-L2-A', 'level': 'L2'},
            {'code': 'MED-L2-B-S1', 'name': 'Emploi du temps Médecine L2 Classe B - S1 2024/2025', 'curriculum': 'MED-L2-B', 'level': 'L2'},
            # Médecine L3
            {'code': 'MED-L3-A-S1', 'name': 'Emploi du temps Médecine L3 Classe A - S1 2024/2025', 'curriculum': 'MED-L3-A', 'level': 'L3'},
            {'code': 'MED-L3-B-S1', 'name': 'Emploi du temps Médecine L3 Classe B - S1 2024/2025', 'curriculum': 'MED-L3-B', 'level': 'L3'},
            # Médecine Master
            {'code': 'MED-M1-S1', 'name': 'Emploi du temps Médecine M1 - S1 2024/2025', 'curriculum': 'MED-M1', 'level': 'M1'},
            {'code': 'MED-M2-S1', 'name': 'Emploi du temps Médecine M2 - S1 2024/2025', 'curriculum': 'MED-M2', 'level': 'M2'},
            # Autres filières
            {'code': 'PHAR-L1-S1', 'name': 'Emploi du temps Pharmacie L1 - S1 2024/2025', 'curriculum': 'PHAR-L1', 'level': 'L1'},
            {'code': 'PHAR-L2-S1', 'name': 'Emploi du temps Pharmacie L2 - S1 2024/2025', 'curriculum': 'PHAR-L2', 'level': 'L2'},
            {'code': 'BIO-L1-S1', 'name': 'Emploi du temps Biologie L1 - S1 2024/2025', 'curriculum': 'BIO-L1', 'level': 'L1'},
            {'code': 'BIO-L2-S1', 'name': 'Emploi du temps Biologie L2 - S1 2024/2025', 'curriculum': 'BIO-L2', 'level': 'L2'},
            {'code': 'CHIM-L1-S1', 'name': 'Emploi du temps Chimie L1 - S1 2024/2025', 'curriculum': 'CHIM-L1', 'level': 'L1'},
            {'code': 'CHIM-L2-S1', 'name': 'Emploi du temps Chimie L2 - S1 2024/2025', 'curriculum': 'CHIM-L2', 'level': 'L2'}
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
        
        # Sessions pour toute la semaine du 5 au 9 août 2025
        week_sessions = []
        
        # Lundi 5 août 2025
        monday_sessions = [
            # Médecine L1-A
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-001', 'room': 'AMPHI-MED', 'teacher': 'T001', 'date': date(2025, 8, 5), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-002', 'room': 'SALLE-MED-101', 'teacher': 'T002', 'date': date(2025, 8, 5), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TD', 'students': 50},
            # Médecine L1-B
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-001', 'room': 'AMPHI-A', 'teacher': 'T001', 'date': date(2025, 8, 5), 'start': time(10, 30), 'end': time(12, 30), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-003', 'room': 'LABO-ANAT', 'teacher': 'T001', 'date': date(2025, 8, 5), 'start': time(16, 30), 'end': time(18, 30), 'type': 'TP', 'students': 30},
            # Médecine L1-C
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-002', 'room': 'AMPHI-B', 'teacher': 'T002', 'date': date(2025, 8, 5), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-004', 'room': 'TD-101', 'teacher': 'T002', 'date': date(2025, 8, 5), 'start': time(10, 30), 'end': time(12, 30), 'type': 'TD', 'students': 35},
            # Médecine L2-A
            {'schedule': 'MED-L2-A-S1', 'course': 'MED-L2-001', 'room': 'SALLE-201', 'teacher': 'T001', 'date': date(2025, 8, 5), 'start': time(14, 0), 'end': time(16, 0), 'type': 'CM', 'students': 40},
            {'schedule': 'MED-L2-A-S1', 'course': 'MED-L2-003', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 5), 'start': time(19, 0), 'end': time(21, 0), 'type': 'TP', 'students': 24},
            # Médecine L2-B  
            {'schedule': 'MED-L2-B-S1', 'course': 'MED-L2-002', 'room': 'SALLE-101', 'teacher': 'T003', 'date': date(2025, 8, 5), 'start': time(16, 30), 'end': time(18, 30), 'type': 'CM', 'students': 40},
            # Autres filières
            {'schedule': 'PHAR-L1-S1', 'course': 'PHAR-L1-001', 'room': 'SALLE-102', 'teacher': 'T003', 'date': date(2025, 8, 5), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 40},
            {'schedule': 'BIO-L1-S1', 'course': 'BIO-L1-001', 'room': 'TD-102', 'teacher': 'T004', 'date': date(2025, 8, 5), 'start': time(14, 0), 'end': time(16, 0), 'type': 'CM', 'students': 30}
        ]
        
        # Mardi 6 août 2025
        tuesday_sessions = [
            # Médecine L1-A
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-003', 'room': 'LABO-ANAT', 'teacher': 'T001', 'date': date(2025, 8, 6), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TP', 'students': 30},
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-004', 'room': 'TD-101', 'teacher': 'T002', 'date': date(2025, 8, 6), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TD', 'students': 35},
            # Médecine L1-B
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-002', 'room': 'AMPHI-A', 'teacher': 'T002', 'date': date(2025, 8, 6), 'start': time(10, 30), 'end': time(12, 30), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-004', 'room': 'TD-102', 'teacher': 'T002', 'date': date(2025, 8, 6), 'start': time(16, 30), 'end': time(18, 30), 'type': 'TD', 'students': 30},
            # Médecine L1-C
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-001', 'room': 'AMPHI-B', 'teacher': 'T001', 'date': date(2025, 8, 6), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-003', 'room': 'LABO-ANAT', 'teacher': 'T001', 'date': date(2025, 8, 6), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TP', 'students': 30},
            # Médecine L2
            {'schedule': 'MED-L2-A-S1', 'course': 'MED-L2-002', 'room': 'SALLE-MED-101', 'teacher': 'T003', 'date': date(2025, 8, 6), 'start': time(10, 30), 'end': time(12, 30), 'type': 'CM', 'students': 40},
            {'schedule': 'MED-L2-B-S1', 'course': 'MED-L2-001', 'room': 'SALLE-201', 'teacher': 'T001', 'date': date(2025, 8, 6), 'start': time(19, 0), 'end': time(21, 0), 'type': 'CM', 'students': 40},
            # Médecine L3
            {'schedule': 'MED-L3-A-S1', 'course': 'MED-L3-001', 'room': 'AMPHI-MED', 'teacher': 'T005', 'date': date(2025, 8, 6), 'start': time(16, 30), 'end': time(18, 30), 'type': 'CM', 'students': 50},
            # Autres filières
            {'schedule': 'CHIM-L1-S1', 'course': 'CHIM-L1-001', 'room': 'SALLE-101', 'teacher': 'T006', 'date': date(2025, 8, 6), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 25},
            {'schedule': 'CHIM-L1-S1', 'course': 'CHIM-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T006', 'date': date(2025, 8, 6), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TP', 'students': 20}
        ]
        
        # Mercredi 7 août 2025
        wednesday_sessions = [
            # Médecine L1 - Révisions et examens
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-001', 'room': 'AMPHI-A', 'teacher': 'T001', 'date': date(2025, 8, 7), 'start': time(8, 0), 'end': time(10, 0), 'type': 'EXAM', 'students': 50},
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-001', 'room': 'AMPHI-B', 'teacher': 'T001', 'date': date(2025, 8, 7), 'start': time(10, 30), 'end': time(12, 30), 'type': 'EXAM', 'students': 50},
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-002', 'room': 'AMPHI-MED', 'teacher': 'T002', 'date': date(2025, 8, 7), 'start': time(14, 0), 'end': time(16, 0), 'type': 'EXAM', 'students': 50},
            # Médecine L2 - Cours normaux
            {'schedule': 'MED-L2-A-S1', 'course': 'MED-L2-003', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 7), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TP', 'students': 24},
            {'schedule': 'MED-L2-B-S1', 'course': 'MED-L2-002', 'room': 'SALLE-MED-101', 'teacher': 'T003', 'date': date(2025, 8, 7), 'start': time(14, 0), 'end': time(16, 0), 'type': 'CM', 'students': 40},
            # Médecine L3
            {'schedule': 'MED-L3-A-S1', 'course': 'MED-L3-002', 'room': 'TD-101', 'teacher': 'T005', 'date': date(2025, 8, 7), 'start': time(10, 30), 'end': time(12, 30), 'type': 'TD', 'students': 35},
            {'schedule': 'MED-L3-B-S1', 'course': 'MED-L3-001', 'room': 'SALLE-201', 'teacher': 'T005', 'date': date(2025, 8, 7), 'start': time(16, 30), 'end': time(18, 30), 'type': 'CM', 'students': 45},
            # Autres filières
            {'schedule': 'PHAR-L1-S1', 'course': 'PHAR-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T003', 'date': date(2025, 8, 7), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TP', 'students': 20},
            {'schedule': 'BIO-L1-S1', 'course': 'BIO-L1-002', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 7), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TP', 'students': 24}
        ]
        
        # Jeudi 8 août 2025 - Journée très dense
        thursday_sessions = [
            # Médecine L1 - Sessions complètes
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-002', 'room': 'AMPHI-MED', 'teacher': 'T002', 'date': date(2025, 8, 8), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-003', 'room': 'LABO-ANAT', 'teacher': 'T001', 'date': date(2025, 8, 8), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TP', 'students': 30},
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-004', 'room': 'TD-101', 'teacher': 'T002', 'date': date(2025, 8, 8), 'start': time(10, 30), 'end': time(12, 30), 'type': 'TD', 'students': 30},
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-001', 'room': 'SALLE-MED-101', 'teacher': 'T001', 'date': date(2025, 8, 8), 'start': time(14, 0), 'end': time(16, 0), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-004', 'room': 'TD-102', 'teacher': 'T002', 'date': date(2025, 8, 8), 'start': time(16, 30), 'end': time(18, 30), 'type': 'TD', 'students': 35},
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-002', 'room': 'AMPHI-A', 'teacher': 'T002', 'date': date(2025, 8, 8), 'start': time(19, 0), 'end': time(21, 0), 'type': 'CM', 'students': 50},
            
            # Médecine L2 - Sessions intensives
            {'schedule': 'MED-L2-A-S1', 'course': 'MED-L2-001', 'room': 'AMPHI-B', 'teacher': 'T001', 'date': date(2025, 8, 8), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 40},
            {'schedule': 'MED-L2-B-S1', 'course': 'MED-L2-002', 'room': 'SALLE-201', 'teacher': 'T003', 'date': date(2025, 8, 8), 'start': time(10, 30), 'end': time(12, 30), 'type': 'CM', 'students': 40},
            {'schedule': 'MED-L2-A-S1', 'course': 'MED-L2-003', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 8), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TP', 'students': 24},
            {'schedule': 'MED-L2-B-S1', 'course': 'MED-L2-001', 'room': 'SALLE-101', 'teacher': 'T001', 'date': date(2025, 8, 8), 'start': time(16, 30), 'end': time(18, 30), 'type': 'CM', 'students': 40},
            {'schedule': 'MED-L2-A-S1', 'course': 'MED-L2-002', 'room': 'SALLE-102', 'teacher': 'T003', 'date': date(2025, 8, 8), 'start': time(19, 0), 'end': time(21, 0), 'type': 'CM', 'students': 40},
            
            # Médecine L3 et Master - Sessions avancées
            {'schedule': 'MED-L3-A-S1', 'course': 'MED-L3-001', 'room': 'SALLE-MED-101', 'teacher': 'T005', 'date': date(2025, 8, 8), 'start': time(10, 30), 'end': time(12, 30), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L3-B-S1', 'course': 'MED-L3-002', 'room': 'TD-101', 'teacher': 'T005', 'date': date(2025, 8, 8), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TD', 'students': 35},
            {'schedule': 'MED-M1-S1', 'course': 'MED-L3-001', 'room': 'SALLE-201', 'teacher': 'T005', 'date': date(2025, 8, 8), 'start': time(16, 30), 'end': time(18, 30), 'type': 'CM', 'students': 30},
            {'schedule': 'MED-M2-S1', 'course': 'MED-L3-002', 'room': 'TD-102', 'teacher': 'T005', 'date': date(2025, 8, 8), 'start': time(19, 0), 'end': time(21, 0), 'type': 'TD', 'students': 25},
            
            # Autres filières - Sessions complètes
            {'schedule': 'PHAR-L1-S1', 'course': 'PHAR-L1-001', 'room': 'SALLE-101', 'teacher': 'T003', 'date': date(2025, 8, 8), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 35},
            {'schedule': 'PHAR-L2-S1', 'course': 'PHAR-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T003', 'date': date(2025, 8, 8), 'start': time(10, 30), 'end': time(12, 30), 'type': 'TP', 'students': 20},
            {'schedule': 'PHAR-L1-S1', 'course': 'PHAR-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T003', 'date': date(2025, 8, 8), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TP', 'students': 20},
            
            {'schedule': 'BIO-L1-S1', 'course': 'BIO-L1-001', 'room': 'SALLE-102', 'teacher': 'T004', 'date': date(2025, 8, 8), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 30},
            {'schedule': 'BIO-L2-S1', 'course': 'BIO-L1-002', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 8), 'start': time(16, 30), 'end': time(18, 30), 'type': 'TP', 'students': 24},
            {'schedule': 'BIO-L1-S1', 'course': 'BIO-L1-002', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 8), 'start': time(10, 30), 'end': time(12, 30), 'type': 'TP', 'students': 24},
            
            {'schedule': 'CHIM-L1-S1', 'course': 'CHIM-L1-001', 'room': 'AMPHI-A', 'teacher': 'T006', 'date': date(2025, 8, 8), 'start': time(14, 0), 'end': time(16, 0), 'type': 'CM', 'students': 25},
            {'schedule': 'CHIM-L2-S1', 'course': 'CHIM-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T006', 'date': date(2025, 8, 8), 'start': time(16, 30), 'end': time(18, 30), 'type': 'TP', 'students': 20},
            {'schedule': 'CHIM-L1-S1', 'course': 'CHIM-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T006', 'date': date(2025, 8, 8), 'start': time(19, 0), 'end': time(21, 0), 'type': 'TP', 'students': 20}
        ]
        
        # Vendredi 9 août 2025 - Journée très chargée
        friday_sessions = [
            # Médecine L1 - Sessions du matin
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-003', 'room': 'LABO-ANAT', 'teacher': 'T001', 'date': date(2025, 8, 9), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TP', 'students': 30},
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-004', 'room': 'TD-101', 'teacher': 'T002', 'date': date(2025, 8, 9), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TD', 'students': 35},
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-001', 'room': 'AMPHI-MED', 'teacher': 'T001', 'date': date(2025, 8, 9), 'start': time(10, 30), 'end': time(12, 30), 'type': 'CM', 'students': 50},
            
            # Médecine L1 - Sessions de l'après-midi
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-002', 'room': 'SALLE-MED-101', 'teacher': 'T002', 'date': date(2025, 8, 9), 'start': time(14, 0), 'end': time(16, 0), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-001', 'room': 'AMPHI-A', 'teacher': 'T001', 'date': date(2025, 8, 9), 'start': time(16, 30), 'end': time(18, 30), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-003', 'room': 'LABO-ANAT', 'teacher': 'T001', 'date': date(2025, 8, 9), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TP', 'students': 30},
            
            # Médecine L2 - Sessions complètes
            {'schedule': 'MED-L2-A-S1', 'course': 'MED-L2-002', 'room': 'AMPHI-B', 'teacher': 'T003', 'date': date(2025, 8, 9), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 40},
            {'schedule': 'MED-L2-B-S1', 'course': 'MED-L2-001', 'room': 'SALLE-201', 'teacher': 'T001', 'date': date(2025, 8, 9), 'start': time(10, 30), 'end': time(12, 30), 'type': 'CM', 'students': 40},
            {'schedule': 'MED-L2-A-S1', 'course': 'MED-L2-003', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 9), 'start': time(16, 30), 'end': time(18, 30), 'type': 'TP', 'students': 24},
            
            # Médecine L3 - Séminaires intensifs
            {'schedule': 'MED-L3-A-S1', 'course': 'MED-L3-002', 'room': 'TD-102', 'teacher': 'T005', 'date': date(2025, 8, 9), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TD', 'students': 30},
            {'schedule': 'MED-L3-B-S1', 'course': 'MED-L3-001', 'room': 'TD-101', 'teacher': 'T005', 'date': date(2025, 8, 9), 'start': time(14, 0), 'end': time(16, 0), 'type': 'CM', 'students': 45},
            {'schedule': 'MED-L3-A-S1', 'course': 'MED-L3-001', 'room': 'SALLE-101', 'teacher': 'T005', 'date': date(2025, 8, 9), 'start': time(16, 30), 'end': time(18, 30), 'type': 'CM', 'students': 50},
            
            # Master - Séminaires de recherche
            {'schedule': 'MED-M1-S1', 'course': 'MED-L3-001', 'room': 'SALLE-102', 'teacher': 'T005', 'date': date(2025, 8, 9), 'start': time(10, 30), 'end': time(12, 30), 'type': 'CM', 'students': 30},
            {'schedule': 'MED-M2-S1', 'course': 'MED-L3-002', 'room': 'TD-102', 'teacher': 'T005', 'date': date(2025, 8, 9), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TD', 'students': 25},
            
            # Autres filières - Sessions intensives de fin de semaine
            {'schedule': 'PHAR-L1-S1', 'course': 'PHAR-L1-001', 'room': 'SALLE-101', 'teacher': 'T003', 'date': date(2025, 8, 9), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 40},
            {'schedule': 'PHAR-L2-S1', 'course': 'PHAR-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T003', 'date': date(2025, 8, 9), 'start': time(10, 30), 'end': time(12, 30), 'type': 'TP', 'students': 20},
            {'schedule': 'PHAR-L1-S1', 'course': 'PHAR-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T003', 'date': date(2025, 8, 9), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TP', 'students': 20},
            
            {'schedule': 'BIO-L1-S1', 'course': 'BIO-L1-001', 'room': 'AMPHI-A', 'teacher': 'T004', 'date': date(2025, 8, 9), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 30},
            {'schedule': 'BIO-L2-S1', 'course': 'BIO-L1-002', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 9), 'start': time(10, 30), 'end': time(12, 30), 'type': 'TP', 'students': 24},
            {'schedule': 'BIO-L1-S1', 'course': 'BIO-L1-002', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 9), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TP', 'students': 24},
            
            {'schedule': 'CHIM-L1-S1', 'course': 'CHIM-L1-001', 'room': 'SALLE-102', 'teacher': 'T006', 'date': date(2025, 8, 9), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 30},
            {'schedule': 'CHIM-L2-S1', 'course': 'CHIM-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T006', 'date': date(2025, 8, 9), 'start': time(16, 30), 'end': time(18, 30), 'type': 'TP', 'students': 20},
            {'schedule': 'CHIM-L1-S1', 'course': 'CHIM-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T006', 'date': date(2025, 8, 9), 'start': time(10, 30), 'end': time(12, 30), 'type': 'TP', 'students': 20}
        ]
        
        # Samedi 10 août 2025 - Sessions supplémentaires
        saturday_sessions = [
            # Médecine L1 - Sessions de rattrapage et révisions
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-001', 'room': 'AMPHI-A', 'teacher': 'T001', 'date': date(2025, 8, 10), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-002', 'room': 'AMPHI-B', 'teacher': 'T002', 'date': date(2025, 8, 10), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-003', 'room': 'LABO-ANAT', 'teacher': 'T001', 'date': date(2025, 8, 10), 'start': time(10, 30), 'end': time(12, 30), 'type': 'TP', 'students': 30},
            
            # Médecine L2 - Examens pratiques
            {'schedule': 'MED-L2-A-S1', 'course': 'MED-L2-003', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 10), 'start': time(8, 0), 'end': time(10, 0), 'type': 'EXAM', 'students': 40},
            {'schedule': 'MED-L2-B-S1', 'course': 'MED-L2-002', 'room': 'AMPHI-MED', 'teacher': 'T003', 'date': date(2025, 8, 10), 'start': time(10, 30), 'end': time(12, 30), 'type': 'EXAM', 'students': 40},
            
            # Médecine L3 - Séminaires spéciaux samedi
            {'schedule': 'MED-L3-A-S1', 'course': 'MED-L3-001', 'room': 'SALLE-MED-101', 'teacher': 'T005', 'date': date(2025, 8, 10), 'start': time(14, 0), 'end': time(16, 0), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L3-B-S1', 'course': 'MED-L3-002', 'room': 'TD-101', 'teacher': 'T005', 'date': date(2025, 8, 10), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TD', 'students': 35},
            
            # Master - Conférences et séminaires de recherche
            {'schedule': 'MED-M1-S1', 'course': 'MED-L3-002', 'room': 'SALLE-201', 'teacher': 'T005', 'date': date(2025, 8, 10), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TD', 'students': 30},
            {'schedule': 'MED-M2-S1', 'course': 'MED-L3-001', 'room': 'TD-102', 'teacher': 'T005', 'date': date(2025, 8, 10), 'start': time(10, 30), 'end': time(12, 30), 'type': 'TD', 'students': 25},
            
            # Autres filières - Sessions de rattrapage
            {'schedule': 'PHAR-L1-S1', 'course': 'PHAR-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T003', 'date': date(2025, 8, 10), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TP', 'students': 20},
            {'schedule': 'PHAR-L2-S1', 'course': 'PHAR-L1-001', 'room': 'SALLE-102', 'teacher': 'T003', 'date': date(2025, 8, 10), 'start': time(10, 30), 'end': time(12, 30), 'type': 'CM', 'students': 35},
            
            {'schedule': 'BIO-L1-S1', 'course': 'BIO-L1-001', 'room': 'SALLE-101', 'teacher': 'T004', 'date': date(2025, 8, 10), 'start': time(14, 0), 'end': time(16, 0), 'type': 'CM', 'students': 30},
            {'schedule': 'BIO-L2-S1', 'course': 'BIO-L1-002', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 10), 'start': time(16, 30), 'end': time(18, 30), 'type': 'TP', 'students': 24},
            
            {'schedule': 'CHIM-L1-S1', 'course': 'CHIM-L1-001', 'room': 'SALLE-101', 'teacher': 'T006', 'date': date(2025, 8, 10), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 25},
            {'schedule': 'CHIM-L2-S1', 'course': 'CHIM-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T006', 'date': date(2025, 8, 10), 'start': time(16, 30), 'end': time(18, 30), 'type': 'TP', 'students': 20}
        ]
        
        # SEMAINE ACTUELLE (18-24 août 2025) - EMPLOI DU TEMPS TRÈS CHARGÉ
        
        # Lundi 18 août 2025 - Journée ultra-dense
        current_monday_sessions = [
            # Matin - Sessions simultanées multiples
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-001', 'room': 'AMPHI-MED', 'teacher': 'T001', 'date': date(2025, 8, 18), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-002', 'room': 'AMPHI-A', 'teacher': 'T002', 'date': date(2025, 8, 18), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-003', 'room': 'LABO-ANAT', 'teacher': 'T001', 'date': date(2025, 8, 18), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TP', 'students': 30},
            {'schedule': 'PHAR-L1-S1', 'course': 'PHAR-L1-001', 'room': 'SALLE-101', 'teacher': 'T003', 'date': date(2025, 8, 18), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 40},
            {'schedule': 'BIO-L1-S1', 'course': 'BIO-L1-001', 'room': 'SALLE-102', 'teacher': 'T004', 'date': date(2025, 8, 18), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 30},
            {'schedule': 'CHIM-L1-S1', 'course': 'CHIM-L1-001', 'room': 'TD-101', 'teacher': 'T006', 'date': date(2025, 8, 18), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TD', 'students': 25},
            
            # 8h30-10h30 - Chevauchement partiel
            {'schedule': 'MED-L2-A-S1', 'course': 'MED-L2-001', 'room': 'SALLE-MED-101', 'teacher': 'T001', 'date': date(2025, 8, 18), 'start': time(8, 30), 'end': time(10, 30), 'type': 'CM', 'students': 40},
            {'schedule': 'MED-L3-A-S1', 'course': 'MED-L3-001', 'room': 'SALLE-201', 'teacher': 'T005', 'date': date(2025, 8, 18), 'start': time(8, 30), 'end': time(10, 30), 'type': 'CM', 'students': 35},
            
            # 9h-11h
            {'schedule': 'PHAR-L2-S1', 'course': 'PHAR-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T003', 'date': date(2025, 8, 18), 'start': time(9, 0), 'end': time(11, 0), 'type': 'TP', 'students': 20},
            {'schedule': 'BIO-L2-S1', 'course': 'BIO-L1-002', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 18), 'start': time(9, 0), 'end': time(11, 0), 'type': 'TP', 'students': 24},
            
            # 10h-12h
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-004', 'room': 'TD-102', 'teacher': 'T002', 'date': date(2025, 8, 18), 'start': time(10, 0), 'end': time(12, 0), 'type': 'TD', 'students': 35},
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-001', 'room': 'AMPHI-B', 'teacher': 'T001', 'date': date(2025, 8, 18), 'start': time(10, 30), 'end': time(12, 30), 'type': 'CM', 'students': 50},
            
            # 11h-13h
            {'schedule': 'CHIM-L2-S1', 'course': 'CHIM-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T006', 'date': date(2025, 8, 18), 'start': time(11, 0), 'end': time(13, 0), 'type': 'TP', 'students': 20},
            
            # Après-midi - Sessions intensives
            {'schedule': 'MED-L2-B-S1', 'course': 'MED-L2-002', 'room': 'AMPHI-MED', 'teacher': 'T003', 'date': date(2025, 8, 18), 'start': time(14, 0), 'end': time(16, 0), 'type': 'CM', 'students': 40},
            {'schedule': 'MED-L3-B-S1', 'course': 'MED-L3-002', 'room': 'TD-101', 'teacher': 'T005', 'date': date(2025, 8, 18), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TD', 'students': 30},
            {'schedule': 'PHAR-L1-S1', 'course': 'PHAR-L1-002', 'room': 'LABO-ANAT', 'teacher': 'T003', 'date': date(2025, 8, 18), 'start': time(14, 30), 'end': time(16, 30), 'type': 'TP', 'students': 20},
            {'schedule': 'BIO-L1-S1', 'course': 'BIO-L1-002', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 18), 'start': time(15, 0), 'end': time(17, 0), 'type': 'TP', 'students': 24},
            
            # 16h-18h
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-002', 'room': 'SALLE-MED-101', 'teacher': 'T002', 'date': date(2025, 8, 18), 'start': time(16, 0), 'end': time(18, 0), 'type': 'CM', 'students': 50},
            {'schedule': 'CHIM-L1-S1', 'course': 'CHIM-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T006', 'date': date(2025, 8, 18), 'start': time(17, 0), 'end': time(19, 0), 'type': 'TP', 'students': 20},
            
            # Soirée - Sessions tardives
            {'schedule': 'MED-M1-S1', 'course': 'MED-L3-001', 'room': 'SALLE-201', 'teacher': 'T005', 'date': date(2025, 8, 18), 'start': time(18, 30), 'end': time(20, 30), 'type': 'CM', 'students': 25},
            {'schedule': 'MED-M2-S1', 'course': 'MED-L3-002', 'room': 'TD-102', 'teacher': 'T005', 'date': date(2025, 8, 18), 'start': time(19, 0), 'end': time(21, 0), 'type': 'TD', 'students': 20}
        ]
        
        # Mardi 19 août 2025 - Journée de TP intensifs
        current_tuesday_sessions = [
            # Matinée - Laboratoires en parallèle
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-003', 'room': 'LABO-ANAT', 'teacher': 'T001', 'date': date(2025, 8, 19), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TP', 'students': 30},
            {'schedule': 'PHAR-L1-S1', 'course': 'PHAR-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T003', 'date': date(2025, 8, 19), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TP', 'students': 20},
            {'schedule': 'BIO-L1-S1', 'course': 'BIO-L1-002', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 19), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TP', 'students': 24},
            {'schedule': 'MED-L2-A-S1', 'course': 'MED-L2-001', 'room': 'AMPHI-MED', 'teacher': 'T001', 'date': date(2025, 8, 19), 'start': time(8, 30), 'end': time(10, 30), 'type': 'CM', 'students': 40},
            {'schedule': 'CHIM-L1-S1', 'course': 'CHIM-L1-001', 'room': 'SALLE-101', 'teacher': 'T006', 'date': date(2025, 8, 19), 'start': time(9, 0), 'end': time(11, 0), 'type': 'CM', 'students': 25},
            
            # 10h-12h - Rotation des groupes
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-003', 'room': 'LABO-ANAT', 'teacher': 'T001', 'date': date(2025, 8, 19), 'start': time(10, 0), 'end': time(12, 0), 'type': 'TP', 'students': 30},
            {'schedule': 'PHAR-L2-S1', 'course': 'PHAR-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T003', 'date': date(2025, 8, 19), 'start': time(10, 0), 'end': time(12, 0), 'type': 'TP', 'students': 20},
            {'schedule': 'BIO-L2-S1', 'course': 'BIO-L1-002', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 19), 'start': time(10, 30), 'end': time(12, 30), 'type': 'TP', 'students': 24},
            {'schedule': 'MED-L3-A-S1', 'course': 'MED-L3-001', 'room': 'SALLE-MED-101', 'teacher': 'T005', 'date': date(2025, 8, 19), 'start': time(11, 0), 'end': time(13, 0), 'type': 'CM', 'students': 35},
            
            # Après-midi - Sessions mixtes
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-003', 'room': 'LABO-ANAT', 'teacher': 'T001', 'date': date(2025, 8, 19), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TP', 'students': 30},
            {'schedule': 'MED-L2-B-S1', 'course': 'MED-L2-003', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 19), 'start': time(14, 30), 'end': time(16, 30), 'type': 'TP', 'students': 24},
            {'schedule': 'CHIM-L2-S1', 'course': 'CHIM-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T006', 'date': date(2025, 8, 19), 'start': time(15, 0), 'end': time(17, 0), 'type': 'TP', 'students': 20},
            {'schedule': 'MED-L3-B-S1', 'course': 'MED-L3-002', 'room': 'TD-101', 'teacher': 'T005', 'date': date(2025, 8, 19), 'start': time(16, 0), 'end': time(18, 0), 'type': 'TD', 'students': 30},
            
            # Soirée - Sessions avancées
            {'schedule': 'MED-M1-S1', 'course': 'MED-L3-001', 'room': 'AMPHI-A', 'teacher': 'T005', 'date': date(2025, 8, 19), 'start': time(18, 0), 'end': time(20, 0), 'type': 'CM', 'students': 25},
            {'schedule': 'PHAR-L1-S1', 'course': 'PHAR-L1-001', 'room': 'SALLE-201', 'teacher': 'T003', 'date': date(2025, 8, 19), 'start': time(19, 0), 'end': time(21, 0), 'type': 'CM', 'students': 40}
        ]
        
        # Mercredi 20 août 2025 - Journée d'examens et cours magistraux
        current_wednesday_sessions = [
            # Matin - Examens simultanés
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-001', 'room': 'AMPHI-MED', 'teacher': 'T001', 'date': date(2025, 8, 20), 'start': time(8, 0), 'end': time(10, 0), 'type': 'EXAM', 'students': 50},
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-001', 'room': 'AMPHI-A', 'teacher': 'T001', 'date': date(2025, 8, 20), 'start': time(8, 0), 'end': time(10, 0), 'type': 'EXAM', 'students': 50},
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-001', 'room': 'AMPHI-B', 'teacher': 'T001', 'date': date(2025, 8, 20), 'start': time(8, 0), 'end': time(10, 0), 'type': 'EXAM', 'students': 50},
            {'schedule': 'PHAR-L1-S1', 'course': 'PHAR-L1-001', 'room': 'SALLE-101', 'teacher': 'T003', 'date': date(2025, 8, 20), 'start': time(8, 30), 'end': time(10, 30), 'type': 'EXAM', 'students': 40},
            {'schedule': 'BIO-L1-S1', 'course': 'BIO-L1-001', 'room': 'SALLE-102', 'teacher': 'T004', 'date': date(2025, 8, 20), 'start': time(9, 0), 'end': time(11, 0), 'type': 'EXAM', 'students': 30},
            
            # 10h-12h - Cours normaux pendant que d'autres passent les examens
            {'schedule': 'MED-L2-A-S1', 'course': 'MED-L2-002', 'room': 'SALLE-MED-101', 'teacher': 'T003', 'date': date(2025, 8, 20), 'start': time(10, 0), 'end': time(12, 0), 'type': 'CM', 'students': 40},
            {'schedule': 'MED-L3-A-S1', 'course': 'MED-L3-001', 'room': 'SALLE-201', 'teacher': 'T005', 'date': date(2025, 8, 20), 'start': time(10, 30), 'end': time(12, 30), 'type': 'CM', 'students': 35},
            {'schedule': 'CHIM-L1-S1', 'course': 'CHIM-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T006', 'date': date(2025, 8, 20), 'start': time(11, 0), 'end': time(13, 0), 'type': 'TP', 'students': 25},
            
            # Après-midi - Rattrapage et TD
            {'schedule': 'MED-L2-B-S1', 'course': 'MED-L2-001', 'room': 'TD-101', 'teacher': 'T001', 'date': date(2025, 8, 20), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TD', 'students': 40},
            {'schedule': 'MED-L3-B-S1', 'course': 'MED-L3-002', 'room': 'TD-102', 'teacher': 'T005', 'date': date(2025, 8, 20), 'start': time(14, 30), 'end': time(16, 30), 'type': 'TD', 'students': 30},
            {'schedule': 'PHAR-L2-S1', 'course': 'PHAR-L1-001', 'room': 'SALLE-102', 'teacher': 'T003', 'date': date(2025, 8, 20), 'start': time(15, 0), 'end': time(17, 0), 'type': 'CM', 'students': 30},
            {'schedule': 'BIO-L2-S1', 'course': 'BIO-L1-001', 'room': 'SALLE-MED-101', 'teacher': 'T004', 'date': date(2025, 8, 20), 'start': time(16, 0), 'end': time(18, 0), 'type': 'CM', 'students': 25},
            
            # Soirée - Cours de rattrapage
            {'schedule': 'CHIM-L2-S1', 'course': 'CHIM-L1-001', 'room': 'SALLE-201', 'teacher': 'T006', 'date': date(2025, 8, 20), 'start': time(18, 0), 'end': time(20, 0), 'type': 'CM', 'students': 20},
            {'schedule': 'MED-M1-S1', 'course': 'MED-L3-002', 'room': 'AMPHI-B', 'teacher': 'T005', 'date': date(2025, 8, 20), 'start': time(19, 0), 'end': time(21, 0), 'type': 'TD', 'students': 25}
        ]
        
        # Jeudi 21 août 2025 - Pic d'activité maximum
        current_thursday_sessions = [
            # Matin - Sessions ultra-intensives
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-002', 'room': 'AMPHI-MED', 'teacher': 'T002', 'date': date(2025, 8, 21), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-004', 'room': 'TD-101', 'teacher': 'T002', 'date': date(2025, 8, 21), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TD', 'students': 35},
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-003', 'room': 'LABO-ANAT', 'teacher': 'T001', 'date': date(2025, 8, 21), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TP', 'students': 30},
            {'schedule': 'MED-L2-A-S1', 'course': 'MED-L2-003', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 21), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TP', 'students': 24},
            {'schedule': 'MED-L3-A-S1', 'course': 'MED-L3-001', 'room': 'SALLE-MED-101', 'teacher': 'T005', 'date': date(2025, 8, 21), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 35},
            {'schedule': 'PHAR-L1-S1', 'course': 'PHAR-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T003', 'date': date(2025, 8, 21), 'start': time(8, 0), 'end': time(10, 0), 'type': 'TP', 'students': 20},
            {'schedule': 'BIO-L1-S1', 'course': 'BIO-L1-001', 'room': 'SALLE-101', 'teacher': 'T004', 'date': date(2025, 8, 21), 'start': time(8, 30), 'end': time(10, 30), 'type': 'CM', 'students': 30},
            {'schedule': 'CHIM-L1-S1', 'course': 'CHIM-L1-001', 'room': 'SALLE-102', 'teacher': 'T006', 'date': date(2025, 8, 21), 'start': time(9, 0), 'end': time(11, 0), 'type': 'CM', 'students': 25},
            
            # 10h-12h - Continuité
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-001', 'room': 'AMPHI-A', 'teacher': 'T001', 'date': date(2025, 8, 21), 'start': time(10, 0), 'end': time(12, 0), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L2-B-S1', 'course': 'MED-L2-002', 'room': 'SALLE-201', 'teacher': 'T003', 'date': date(2025, 8, 21), 'start': time(10, 30), 'end': time(12, 30), 'type': 'CM', 'students': 40},
            {'schedule': 'MED-L3-B-S1', 'course': 'MED-L3-002', 'room': 'TD-102', 'teacher': 'T005', 'date': date(2025, 8, 21), 'start': time(11, 0), 'end': time(13, 0), 'type': 'TD', 'students': 30},
            {'schedule': 'PHAR-L2-S1', 'course': 'PHAR-L1-001', 'room': 'AMPHI-B', 'teacher': 'T003', 'date': date(2025, 8, 21), 'start': time(11, 30), 'end': time(13, 30), 'type': 'CM', 'students': 30},
            
            # Après-midi - Sessions marathon
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-002', 'room': 'SALLE-MED-101', 'teacher': 'T002', 'date': date(2025, 8, 21), 'start': time(14, 0), 'end': time(16, 0), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-004', 'room': 'TD-101', 'teacher': 'T002', 'date': date(2025, 8, 21), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TD', 'students': 35},
            {'schedule': 'MED-L2-A-S1', 'course': 'MED-L2-001', 'room': 'AMPHI-MED', 'teacher': 'T001', 'date': date(2025, 8, 21), 'start': time(14, 30), 'end': time(16, 30), 'type': 'CM', 'students': 40},
            {'schedule': 'BIO-L2-S1', 'course': 'BIO-L1-002', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 21), 'start': time(15, 0), 'end': time(17, 0), 'type': 'TP', 'students': 24},
            {'schedule': 'CHIM-L2-S1', 'course': 'CHIM-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T006', 'date': date(2025, 8, 21), 'start': time(15, 30), 'end': time(17, 30), 'type': 'TP', 'students': 20},
            
            # 16h-18h - Rush final de la journée
            {'schedule': 'MED-L3-A-S1', 'course': 'MED-L3-001', 'room': 'SALLE-201', 'teacher': 'T005', 'date': date(2025, 8, 21), 'start': time(16, 0), 'end': time(18, 0), 'type': 'CM', 'students': 35},
            {'schedule': 'PHAR-L1-S1', 'course': 'PHAR-L1-001', 'room': 'SALLE-101', 'teacher': 'T003', 'date': date(2025, 8, 21), 'start': time(16, 30), 'end': time(18, 30), 'type': 'CM', 'students': 40},
            {'schedule': 'BIO-L1-S1', 'course': 'BIO-L1-001', 'room': 'SALLE-102', 'teacher': 'T004', 'date': date(2025, 8, 21), 'start': time(17, 0), 'end': time(19, 0), 'type': 'CM', 'students': 30},
            
            # Soirée - Sessions de pointe
            {'schedule': 'MED-M1-S1', 'course': 'MED-L3-001', 'room': 'AMPHI-A', 'teacher': 'T005', 'date': date(2025, 8, 21), 'start': time(18, 30), 'end': time(20, 30), 'type': 'CM', 'students': 25},
            {'schedule': 'MED-M2-S1', 'course': 'MED-L3-002', 'room': 'TD-102', 'teacher': 'T005', 'date': date(2025, 8, 21), 'start': time(19, 0), 'end': time(21, 0), 'type': 'TD', 'students': 20},
            {'schedule': 'CHIM-L1-S1', 'course': 'CHIM-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T006', 'date': date(2025, 8, 21), 'start': time(19, 30), 'end': time(21, 30), 'type': 'TP', 'students': 25}
        ]
        
        # Vendredi 22 août 2025 - Journée de synthèse intensive
        current_friday_sessions = [
            # Matin - Révisions et cours magistraux
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-001', 'room': 'AMPHI-MED', 'teacher': 'T001', 'date': date(2025, 8, 22), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-002', 'room': 'AMPHI-A', 'teacher': 'T002', 'date': date(2025, 8, 22), 'start': time(8, 0), 'end': time(10, 0), 'type': 'CM', 'students': 50},
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-004', 'room': 'TD-101', 'teacher': 'T002', 'date': date(2025, 8, 22), 'start': time(8, 30), 'end': time(10, 30), 'type': 'TD', 'students': 35},
            {'schedule': 'MED-L2-A-S1', 'course': 'MED-L2-002', 'room': 'SALLE-MED-101', 'teacher': 'T003', 'date': date(2025, 8, 22), 'start': time(9, 0), 'end': time(11, 0), 'type': 'CM', 'students': 40},
            {'schedule': 'PHAR-L1-S1', 'course': 'PHAR-L1-001', 'room': 'SALLE-101', 'teacher': 'T003', 'date': date(2025, 8, 22), 'start': time(9, 30), 'end': time(11, 30), 'type': 'CM', 'students': 40},
            
            # 10h-12h - TP de fin de semaine
            {'schedule': 'MED-L3-A-S1', 'course': 'MED-L3-001', 'room': 'SALLE-201', 'teacher': 'T005', 'date': date(2025, 8, 22), 'start': time(10, 0), 'end': time(12, 0), 'type': 'CM', 'students': 35},
            {'schedule': 'BIO-L1-S1', 'course': 'BIO-L1-002', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 22), 'start': time(10, 30), 'end': time(12, 30), 'type': 'TP', 'students': 24},
            {'schedule': 'CHIM-L1-S1', 'course': 'CHIM-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T006', 'date': date(2025, 8, 22), 'start': time(11, 0), 'end': time(13, 0), 'type': 'TP', 'students': 25},
            {'schedule': 'MED-L2-B-S1', 'course': 'MED-L2-003', 'room': 'LABO-ANAT', 'teacher': 'T001', 'date': date(2025, 8, 22), 'start': time(11, 30), 'end': time(13, 30), 'type': 'TP', 'students': 30},
            
            # Après-midi - Sessions finales de la semaine
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-003', 'room': 'LABO-ANAT', 'teacher': 'T001', 'date': date(2025, 8, 22), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TP', 'students': 30},
            {'schedule': 'MED-L3-B-S1', 'course': 'MED-L3-002', 'room': 'TD-102', 'teacher': 'T005', 'date': date(2025, 8, 22), 'start': time(14, 30), 'end': time(16, 30), 'type': 'TD', 'students': 30},
            {'schedule': 'PHAR-L2-S1', 'course': 'PHAR-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T003', 'date': date(2025, 8, 22), 'start': time(15, 0), 'end': time(17, 0), 'type': 'TP', 'students': 20},
            {'schedule': 'BIO-L2-S1', 'course': 'BIO-L1-001', 'room': 'SALLE-102', 'teacher': 'T004', 'date': date(2025, 8, 22), 'start': time(16, 0), 'end': time(18, 0), 'type': 'CM', 'students': 25},
            {'schedule': 'CHIM-L2-S1', 'course': 'CHIM-L1-001', 'room': 'AMPHI-B', 'teacher': 'T006', 'date': date(2025, 8, 22), 'start': time(16, 30), 'end': time(18, 30), 'type': 'CM', 'students': 20},
            
            # Soirée - Fin de semaine intensive
            {'schedule': 'MED-M1-S1', 'course': 'MED-L3-002', 'room': 'SALLE-MED-101', 'teacher': 'T005', 'date': date(2025, 8, 22), 'start': time(18, 0), 'end': time(20, 0), 'type': 'TD', 'students': 25},
            {'schedule': 'MED-M2-S1', 'course': 'MED-L3-001', 'room': 'SALLE-201', 'teacher': 'T005', 'date': date(2025, 8, 22), 'start': time(19, 0), 'end': time(21, 0), 'type': 'CM', 'students': 20}
        ]
        
        # Samedi 23 août 2025 - Journée de rattrapage et examens
        current_saturday_sessions = [
            # Matin - Examens de rattrapage
            {'schedule': 'MED-L1-A-S1', 'course': 'MED-L1-002', 'room': 'AMPHI-MED', 'teacher': 'T002', 'date': date(2025, 8, 23), 'start': time(8, 0), 'end': time(10, 0), 'type': 'EXAM', 'students': 50},
            {'schedule': 'MED-L1-B-S1', 'course': 'MED-L1-002', 'room': 'AMPHI-A', 'teacher': 'T002', 'date': date(2025, 8, 23), 'start': time(8, 0), 'end': time(10, 0), 'type': 'EXAM', 'students': 50},
            {'schedule': 'PHAR-L1-S1', 'course': 'PHAR-L1-002', 'room': 'LABO-CHIM-1', 'teacher': 'T003', 'date': date(2025, 8, 23), 'start': time(8, 30), 'end': time(10, 30), 'type': 'EXAM', 'students': 20},
            {'schedule': 'BIO-L1-S1', 'course': 'BIO-L1-002', 'room': 'LABO-BIO-1', 'teacher': 'T004', 'date': date(2025, 8, 23), 'start': time(9, 0), 'end': time(11, 0), 'type': 'EXAM', 'students': 24},
            {'schedule': 'CHIM-L1-S1', 'course': 'CHIM-L1-002', 'room': 'SALLE-101', 'teacher': 'T006', 'date': date(2025, 8, 23), 'start': time(9, 30), 'end': time(11, 30), 'type': 'EXAM', 'students': 25},
            
            # 10h-12h - Cours de soutien
            {'schedule': 'MED-L2-A-S1', 'course': 'MED-L2-001', 'room': 'SALLE-MED-101', 'teacher': 'T001', 'date': date(2025, 8, 23), 'start': time(10, 0), 'end': time(12, 0), 'type': 'TD', 'students': 40},
            {'schedule': 'MED-L3-A-S1', 'course': 'MED-L3-001', 'room': 'SALLE-201', 'teacher': 'T005', 'date': date(2025, 8, 23), 'start': time(10, 30), 'end': time(12, 30), 'type': 'TD', 'students': 35},
            {'schedule': 'MED-L1-C-S1', 'course': 'MED-L1-003', 'room': 'LABO-ANAT', 'teacher': 'T001', 'date': date(2025, 8, 23), 'start': time(11, 0), 'end': time(13, 0), 'type': 'TP', 'students': 30},
            
            # Après-midi - Sessions de fin de semaine
            {'schedule': 'MED-L2-B-S1', 'course': 'MED-L2-002', 'room': 'TD-101', 'teacher': 'T003', 'date': date(2025, 8, 23), 'start': time(14, 0), 'end': time(16, 0), 'type': 'TD', 'students': 40},
            {'schedule': 'MED-L3-B-S1', 'course': 'MED-L3-002', 'room': 'TD-102', 'teacher': 'T005', 'date': date(2025, 8, 23), 'start': time(14, 30), 'end': time(16, 30), 'type': 'TD', 'students': 30},
            {'schedule': 'PHAR-L2-S1', 'course': 'PHAR-L1-001', 'room': 'SALLE-102', 'teacher': 'T003', 'date': date(2025, 8, 23), 'start': time(15, 0), 'end': time(17, 0), 'type': 'CM', 'students': 30},
            {'schedule': 'BIO-L2-S1', 'course': 'BIO-L1-001', 'room': 'AMPHI-B', 'teacher': 'T004', 'date': date(2025, 8, 23), 'start': time(16, 0), 'end': time(18, 0), 'type': 'CM', 'students': 25},
            
            # Soirée - Séances de clôture de semaine
            {'schedule': 'MED-M1-S1', 'course': 'MED-L3-001', 'room': 'SALLE-MED-101', 'teacher': 'T005', 'date': date(2025, 8, 23), 'start': time(18, 0), 'end': time(20, 0), 'type': 'CM', 'students': 25},
            {'schedule': 'CHIM-L2-S1', 'course': 'CHIM-L1-001', 'room': 'SALLE-201', 'teacher': 'T006', 'date': date(2025, 8, 23), 'start': time(19, 0), 'end': time(21, 0), 'type': 'CM', 'students': 20}
        ]
        
        # SESSIONS COMBINÉES - Semaine historique (5-10 août) + Semaine actuelle (18-23 août)
        current_week_sessions = (current_monday_sessions + current_tuesday_sessions + 
                               current_wednesday_sessions + current_thursday_sessions + 
                               current_friday_sessions + current_saturday_sessions)
        
        # Combiner toutes les sessions : historique + actuelle
        week_sessions = (monday_sessions + tuesday_sessions + wednesday_sessions + 
                        thursday_sessions + friday_sessions + saturday_sessions + 
                        current_week_sessions)
        
        # Créer les sessions pour toute la semaine
        for i, session_data in enumerate(week_sessions):
            # Trouver un time_slot unique pour éviter les conflits
            day_mapping = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5
            }
            
            # Convertir la date en jour de la semaine
            weekday = session_data['date'].strftime('%A').lower()
            if weekday in day_mapping:
                # Trouver les time_slots pour ce jour
                day_slots = [slot for key, slot in self.time_slots.items() if key.startswith(weekday)]
                if day_slots:
                    # Utiliser un time_slot différent pour chaque session pour éviter les conflits
                    time_slot_index = i % len(day_slots)
                    selected_slot = day_slots[time_slot_index]
                else:
                    selected_slot = list(self.time_slots.values())[0]
            else:
                selected_slot = list(self.time_slots.values())[0]
            
            # Pour éviter les conflits de contraintes uniques, utiliser des salles différentes
            # pour les sessions qui se chevauchent
            available_rooms = list(self.rooms.keys())
            room_index = i % len(available_rooms)
            selected_room = available_rooms[room_index]
            
            # Vérifier s'il y a déjà une session avec la même contrainte unique
            schedule_obj = self.schedules[session_data['schedule']]
            room_obj = self.rooms[selected_room]
            
            # Si conflit, essayer avec une autre salle
            attempts = 0
            while attempts < len(available_rooms):
                existing = ScheduleSession.objects.filter(
                    schedule=schedule_obj,
                    time_slot=selected_slot,
                    room=room_obj
                ).exists()
                
                if not existing:
                    break
                    
                # Essayer la salle suivante
                room_index = (room_index + 1) % len(available_rooms)
                selected_room = available_rooms[room_index]
                room_obj = self.rooms[selected_room]
                attempts += 1
            
            # Créer une session unique
            try:
                session = ScheduleSession.objects.create(
                    schedule=schedule_obj,
                    course=self.courses[session_data['course']],
                    room=room_obj,
                    teacher=self.teachers[session_data['teacher']],
                    time_slot=selected_slot,  # Utiliser un time_slot unique
                    specific_date=session_data['date'],
                    specific_start_time=session_data['start'],
                    specific_end_time=session_data['end'],
                    session_type=session_data['type'],
                    expected_students=session_data['students'],
                    difficulty_score=0.6,
                    complexity_level='Moyenne',
                    scheduling_priority=3 if session_data['type'] == 'EXAM' else 2,
                    is_cancelled=False
                )
            except Exception as e:
                print(f"[WARNING] Impossible de créer la session {i+1}: {e}")
                continue
        
        print(f"[OK] {len(self.schedules)} emplois du temps et {len(week_sessions)} sessions créées:")
        print(f"   • Semaine historique (05-10/08/2025): {len(monday_sessions + tuesday_sessions + wednesday_sessions + thursday_sessions + friday_sessions + saturday_sessions)} sessions")
        print(f"   • Semaine actuelle (18-23/08/2025): {len(current_week_sessions)} sessions")
        print(f"   • TOTAL: {len(week_sessions)} sessions")
    
    def create_students(self):
        """Crée quelques étudiants pour les tests"""
        print("[STUDENTS] Création d'étudiants...")
        
        students_data = [
            {'username': 'etudiant.med1a', 'first_name': 'Pierre', 'last_name': 'Ngono', 'student_id': 'MED24001', 'curriculum': 'MED-L1-A'},
            {'username': 'etudiant.med1b', 'first_name': 'Marie', 'last_name': 'Ateba', 'student_id': 'MED24002', 'curriculum': 'MED-L1-B'},
            {'username': 'etudiant.med1c', 'first_name': 'Claude', 'last_name': 'Beka', 'student_id': 'MED24003', 'curriculum': 'MED-L1-C'},
            {'username': 'etudiant.med2a', 'first_name': 'Joseph', 'last_name': 'Essomba', 'student_id': 'MED23001', 'curriculum': 'MED-L2-A'},
            {'username': 'etudiant.med2b', 'first_name': 'Amélie', 'last_name': 'Tchoumi', 'student_id': 'MED23002', 'curriculum': 'MED-L2-B'},
            {'username': 'etudiant.med3a', 'first_name': 'Serge', 'last_name': 'Nkomo', 'student_id': 'MED22001', 'curriculum': 'MED-L3-A'},
            {'username': 'etudiant.medm1', 'first_name': 'Diane', 'last_name': 'Fokou', 'student_id': 'MED21001', 'curriculum': 'MED-M1'},
            {'username': 'etudiant.medm2', 'first_name': 'Roger', 'last_name': 'Kemajou', 'student_id': 'MED20001', 'curriculum': 'MED-M2'},
            {'username': 'etudiant.phar1', 'first_name': 'Grace', 'last_name': 'Mengue', 'student_id': 'PHAR24001', 'curriculum': 'PHAR-L1'},
            {'username': 'etudiant.phar2', 'first_name': 'Alain', 'last_name': 'Mvondo', 'student_id': 'PHAR23001', 'curriculum': 'PHAR-L2'},
            {'username': 'etudiant.bio1', 'first_name': 'Paul', 'last_name': 'Owona', 'student_id': 'BIO24001', 'curriculum': 'BIO-L1'},
            {'username': 'etudiant.bio2', 'first_name': 'Sarah', 'last_name': 'Ndongo', 'student_id': 'BIO23001', 'curriculum': 'BIO-L2'},
            {'username': 'etudiant.chim1', 'first_name': 'Eric', 'last_name': 'Mbarga', 'student_id': 'CHIM24001', 'curriculum': 'CHIM-L1'},
            {'username': 'etudiant.chim2', 'first_name': 'Celine', 'last_name': 'Njankouo', 'student_id': 'CHIM23001', 'curriculum': 'CHIM-L2'}
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
            
            print(f"\n[SESSIONS] COURS POUR LA SEMAINE DU 05-10/08/2025:")
            week_sessions_db = ScheduleSession.objects.filter(
                specific_date__range=[date(2025, 8, 5), date(2025, 8, 10)]
            ).order_by('specific_date', 'specific_start_time')
            
            current_date = None
            for session in week_sessions_db:
                if current_date != session.specific_date:
                    current_date = session.specific_date
                    print(f"\n   === {session.specific_date.strftime('%A %d/%m/%Y')} ===")
                print(f"   • {session.specific_start_time}-{session.specific_end_time}: {session.course.name} ({session.session_type}) - {session.room.code} - {session.schedule.curriculum.name}")
            
        except Exception as e:
            print(f"\n[ERREUR] ECHEC DU SEEDING: {str(e)}")
            raise


def main():
    """Point d'entrée principal"""
    seeder = OAPETSeeder()
    seeder.run_seed()


if __name__ == '__main__':
    main()