# rooms/models.py
from django.db import models


class Building(models.Model):
    """Modèle pour les bâtiments"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    address = models.TextField(blank=True)
    description = models.TextField(blank=True)
    total_floors = models.IntegerField(default=1)
    has_elevator = models.BooleanField(default=False)
    has_parking = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        ordering = ['code']


class RoomType(models.Model):
    """Modèle pour les types de salles"""
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    default_capacity = models.IntegerField(default=30)
    requires_special_equipment = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Room(models.Model):
    """Modèle pour les salles"""
    FLOOR_CHOICES = [
        ('RDC', 'Rez-de-chaussée'),
        ('1', '1er étage'),
        ('2', '2ème étage'),
        ('3', '3ème étage'),
        ('4', '4ème étage'),
        ('5', '5ème étage'),
    ]

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='rooms')
    room_type = models.ForeignKey(RoomType, on_delete=models.CASCADE, related_name='rooms')
    floor = models.CharField(max_length=5, choices=FLOOR_CHOICES, default='RDC')
    capacity = models.IntegerField()
    area = models.FloatField(blank=True, null=True)  # Surface en m²
    description = models.TextField(blank=True)
    
    # Équipements disponibles
    has_projector = models.BooleanField(default=False)
    has_computer = models.BooleanField(default=False)
    has_whiteboard = models.BooleanField(default=True)
    has_blackboard = models.BooleanField(default=False)
    has_air_conditioning = models.BooleanField(default=False)
    has_internet = models.BooleanField(default=True)
    has_audio_system = models.BooleanField(default=False)
    
    # Spécifications pour laboratoires
    is_laboratory = models.BooleanField(default=False)
    laboratory_type = models.CharField(max_length=50, blank=True)  # Informatique, Chimie, etc.
    has_special_equipment = models.BooleanField(default=False)
    equipment_list = models.JSONField(default=list)  # Liste des équipements spéciaux
    
    # Accessibilité
    is_accessible = models.BooleanField(default=True)  # Accessible PMR
    has_emergency_exit = models.BooleanField(default=True)
    
    # Disponibilité
    is_bookable = models.BooleanField(default=True)
    priority_level = models.IntegerField(default=1)  # 1=haute, 2=moyenne, 3=basse
    maintenance_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        ordering = ['building__code', 'code']


class RoomEquipment(models.Model):
    """Modèle pour les équipements additionnels des salles"""
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='additional_equipment')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    quantity = models.IntegerField(default=1)
    is_working = models.BooleanField(default=True)
    last_maintenance = models.DateField(blank=True, null=True)
    next_maintenance = models.DateField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.room.code} - {self.name}"

    class Meta:
        ordering = ['room__code', 'name']


class RoomAvailability(models.Model):
    """Modèle pour la disponibilité des salles"""
    DAYS_OF_WEEK = [
        ('monday', 'Lundi'),
        ('tuesday', 'Mardi'),
        ('wednesday', 'Mercredi'),
        ('thursday', 'Jeudi'),
        ('friday', 'Vendredi'),
        ('saturday', 'Samedi'),
        ('sunday', 'Dimanche'),
    ]
    
    PERIOD_CHOICES = [
        ('08:00-09:30', '08:00-09:30'),
        ('09:45-11:15', '09:45-11:15'),
        ('11:30-13:00', '11:30-13:00'),
        ('14:00-15:30', '14:00-15:30'),
        ('15:45-17:15', '15:45-17:15'),
        ('17:30-19:00', '17:30-19:00'),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='availability')
    day_of_week = models.CharField(max_length=10, choices=DAYS_OF_WEEK)
    period = models.CharField(max_length=15, choices=PERIOD_CHOICES)
    is_available = models.BooleanField(default=True)
    reason = models.CharField(max_length=200, blank=True)  # Raison d'indisponibilité
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    
    def __str__(self):
        status = "Disponible" if self.is_available else "Indisponible"
        return f"{self.room.code} - {self.get_day_of_week_display()} {self.period} - {status}"

    class Meta:
        unique_together = ['room', 'day_of_week', 'period']
        ordering = ['room__code', 'day_of_week', 'period']


class RoomBooking(models.Model):
    """Modèle pour les réservations de salles (non cours)"""
    BOOKING_TYPE_CHOICES = [
        ('meeting', 'Réunion'),
        ('conference', 'Conférence'),
        ('event', 'Événement'),
        ('maintenance', 'Maintenance'),
        ('other', 'Autre'),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings')
    booking_type = models.CharField(max_length=20, choices=BOOKING_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    organizer_name = models.CharField(max_length=100)
    organizer_email = models.EmailField()
    expected_attendees = models.IntegerField(default=1)
    special_requirements = models.TextField(blank=True)
    is_recurring = models.BooleanField(default=False)
    recurrence_pattern = models.JSONField(default=dict, blank=True)
    is_approved = models.BooleanField(default=False)
    approved_by = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.room.code} - {self.title} ({self.date})"

    class Meta:
        ordering = ['-date', '-start_time']


class MaintenanceRecord(models.Model):
    """Modèle pour l'historique de maintenance des salles"""
    MAINTENANCE_TYPE_CHOICES = [
        ('preventive', 'Préventive'),
        ('corrective', 'Corrective'),
        ('emergency', 'Urgence'),
        ('upgrade', 'Amélioration'),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='maintenance_records')
    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    date_scheduled = models.DateField()
    date_completed = models.DateField(blank=True, null=True)
    technician_name = models.CharField(max_length=100)
    cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    is_completed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.room.code} - {self.title} ({self.date_scheduled})"

    class Meta:
        ordering = ['-date_scheduled']
