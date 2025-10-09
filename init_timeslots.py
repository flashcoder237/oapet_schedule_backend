#!/usr/bin/env python
"""Script pour créer les TimeSlots de base"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oapet_schedule_backend.settings')
django.setup()

from schedules.models import TimeSlot
from datetime import time

def create_timeslots():
    """Créer les créneaux horaires standard"""

    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']

    slots = [
        ('08:00', '10:00', 'Créneau 1'),
        ('10:00', '12:00', 'Créneau 2'),
        ('14:00', '16:00', 'Créneau 3'),
        ('16:00', '18:00', 'Créneau 4'),
    ]

    created_count = 0

    for day in days:
        for start_str, end_str, name in slots:
            start_time = time(*map(int, start_str.split(':')))
            end_time = time(*map(int, end_str.split(':')))

            slot, created = TimeSlot.objects.get_or_create(
                day_of_week=day,
                start_time=start_time,
                end_time=end_time,
                defaults={
                    'name': name,
                    'is_active': True
                }
            )

            if created:
                created_count += 1
                print(f"✓ Créé: {slot}")
            else:
                print(f"  Existe déjà: {slot}")

    print(f"\n✅ {created_count} créneaux créés")
    print(f"📊 Total: {TimeSlot.objects.count()} créneaux dans la base")

if __name__ == '__main__':
    create_timeslots()
