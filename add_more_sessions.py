#!/usr/bin/env python3
"""
Script pour ajouter plus de sessions d'emploi du temps
Remplit chaque jour avec plus de cours pour un planning plus dense
"""

import os
import sys
from datetime import date, time, datetime, timedelta
import random

# Configuration Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oapet_schedule_backend.settings')

import django
django.setup()

from django.utils import timezone
from courses.models import Course, Teacher, Curriculum
from rooms.models import Room
from schedules.models import Schedule, ScheduleSession, TimeSlot

def add_dense_sessions():
    """Ajoute beaucoup plus de sessions pour remplir l'emploi du temps"""
    print("[DENSE] Ajout de sessions supplémentaires...")
    
    # Récupérer les données existantes
    schedules = list(Schedule.objects.all())
    courses = list(Course.objects.all())
    rooms = list(Room.objects.all())
    teachers = list(Teacher.objects.all())
    
    # Heures disponibles (plus dense)
    time_slots = [
        time(8, 0), time(8, 30), time(9, 0), time(9, 30), time(10, 0), time(10, 30),
        time(11, 0), time(11, 30), time(12, 0), time(12, 30), time(13, 0), time(13, 30),
        time(14, 0), time(14, 30), time(15, 0), time(15, 30), time(16, 0), time(16, 30),
        time(17, 0), time(17, 30), time(18, 0), time(18, 30), time(19, 0), time(19, 30),
        time(20, 0), time(20, 30)
    ]
    
    # Types de session variés
    session_types = ['CM', 'TD', 'TP', 'CONF']
    
    # Jours de la semaine (5-10 août 2025)
    dates = [
        date(2025, 8, 5),  # Mardi
        date(2025, 8, 6),  # Mercredi
        date(2025, 8, 7),  # Jeudi
        date(2025, 8, 8),  # Vendredi
        date(2025, 8, 9),  # Samedi
    ]
    
    sessions_added = 0
    
    # Pour chaque jour
    for session_date in dates:
        print(f"  Ajout de sessions pour {session_date.strftime('%A %d/%m/%Y')}...")
        
        # Pour chaque créneau horaire
        for start_time in time_slots:
            # Calculer l'heure de fin (2h après)
            end_time = (datetime.combine(date.today(), start_time) + timedelta(hours=2)).time()
            
            # Essayer d'ajouter une session si pas de conflit
            schedule = random.choice(schedules)
            course = random.choice(courses)
            room = random.choice(rooms)
            teacher = random.choice(teachers)
            session_type = random.choice(session_types)
            
            # Vérifier s'il n'y a pas déjà une session à cette heure dans cette salle
            existing = ScheduleSession.objects.filter(
                specific_date=session_date,
                specific_start_time=start_time,
                room=room
            ).exists()
            
            # Créer des time_slots uniques pour éviter les conflits
            time_slots_db = list(TimeSlot.objects.all())
            time_slot = random.choice(time_slots_db)
            
            # Vérifier la contrainte unique (schedule, time_slot, room)
            unique_exists = ScheduleSession.objects.filter(
                schedule=schedule,
                time_slot=time_slot,
                room=room
            ).exists()
            
            if not existing and not unique_exists:
                try:
                    session = ScheduleSession.objects.create(
                        schedule=schedule,
                        course=course,
                        room=room,
                        teacher=teacher,
                        time_slot=time_slot,
                        specific_date=session_date,
                        specific_start_time=start_time,
                        specific_end_time=end_time,
                        session_type=session_type,
                        expected_students=random.randint(20, 80),
                        difficulty_score=random.uniform(0.3, 0.9),
                        complexity_level=random.choice(['Facile', 'Moyenne', 'Difficile']),
                        scheduling_priority=random.randint(1, 5),
                        is_cancelled=False
                    )
                    sessions_added += 1
                except Exception as e:
                    # Ignorer les erreurs de contrainte et continuer
                    continue
                
                # Limiter pour éviter trop de sessions
                if sessions_added >= 200:
                    break
        
        if sessions_added >= 200:
            break
    
    total_sessions = ScheduleSession.objects.count()
    print(f"[OK] {sessions_added} nouvelles sessions ajoutées")
    print(f"[TOTAL] {total_sessions} sessions au total dans la base")

if __name__ == "__main__":
    add_dense_sessions()