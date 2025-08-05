# ml_engine/models.py
from django.db import models
from django.contrib.auth.models import User
import json


class TimetableDataset(models.Model):
    """Modèle pour stocker les datasets ITC 2007"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    file_path = models.FileField(upload_to='datasets/')
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']


class MLModel(models.Model):
    """Modèle pour stocker les modèles ML entraînés"""
    MODEL_TYPES = [
        ('xgboost', 'XGBoost'),
        ('random_forest', 'Random Forest'),
        ('neural_network', 'Neural Network'),
        ('gradient_boosting', 'Gradient Boosting'),
    ]

    name = models.CharField(max_length=100, unique=True)
    model_type = models.CharField(max_length=20, choices=MODEL_TYPES)
    description = models.TextField(blank=True)
    model_file = models.FileField(upload_to='models/')
    scaler_file = models.FileField(upload_to='models/', blank=True)
    metadata_file = models.FileField(upload_to='models/', blank=True)
    performance_metrics = models.JSONField(default=dict)
    feature_names = models.JSONField(default=list)
    is_active = models.BooleanField(default=False)
    is_trained = models.BooleanField(default=False)  # Nouveau champ
    training_completed_at = models.DateTimeField(null=True, blank=True)  # Nouveau champ
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @classmethod
    def get_or_create_default_model(cls):
        """Crée ou récupère le modèle par défaut"""
        model, created = cls.objects.get_or_create(
            name='default_schedule_model',
            defaults={
                'model_type': 'random_forest',
                'description': 'Modèle par défaut pour la prédiction des emplois du temps',
                'is_active': True
            }
        )
        return model, created

    def __str__(self):
        return f"{self.name} ({self.model_type})"

    class Meta:
        ordering = ['-created_at']


class PredictionRequest(models.Model):
    """Modèle pour stocker les requêtes de prédiction"""
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En cours'),
        ('completed', 'Terminé'),
        ('failed', 'Échoué'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    model = models.ForeignKey(MLModel, on_delete=models.CASCADE)
    input_data = models.JSONField()
    output_data = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    processing_time = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Prédiction {self.id} - {self.status}"

    class Meta:
        ordering = ['-created_at']


class ModelTrainingTask(models.Model):
    """Modèle pour suivre les tâches d'entraînement"""
    STATUS_CHOICES = [
        ('queued', 'En file d\'attente'),
        ('running', 'En cours'),
        ('completed', 'Terminé'),
        ('failed', 'Échoué'),
    ]

    name = models.CharField(max_length=100)
    dataset = models.ForeignKey(TimetableDataset, on_delete=models.CASCADE)
    model_types = models.JSONField(default=list)  # Types de modèles à entraîner
    parameters = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    progress = models.FloatField(default=0.0)  # Pourcentage de progression
    logs = models.TextField(blank=True)
    results = models.JSONField(default=dict)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Entraînement {self.name} - {self.status}"

    class Meta:
        ordering = ['-created_at']


class FeatureImportance(models.Model):
    """Modèle pour stocker l'importance des features"""
    model = models.ForeignKey(MLModel, on_delete=models.CASCADE)
    feature_name = models.CharField(max_length=100)
    importance_score = models.FloatField()
    rank = models.IntegerField()

    def __str__(self):
        return f"{self.feature_name} - {self.importance_score:.4f}"

    class Meta:
        ordering = ['rank']
        unique_together = ['model', 'feature_name']


class PredictionHistory(models.Model):
    """Modèle pour l'historique des prédictions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course_name = models.CharField(max_length=200)
    predicted_difficulty = models.FloatField()
    complexity_level = models.CharField(max_length=20)
    priority = models.IntegerField()
    actual_difficulty = models.FloatField(null=True, blank=True)  # Pour feedback
    feedback_provided = models.BooleanField(default=False)
    prediction_data = models.JSONField()  # Données complètes de la prédiction
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.course_name} - {self.complexity_level}"

    class Meta:
        ordering = ['-created_at']


class ModelPerformanceMetric(models.Model):
    """Modèle pour suivre les métriques de performance dans le temps"""
    model = models.ForeignKey(MLModel, on_delete=models.CASCADE)
    metric_name = models.CharField(max_length=50)  # 'mse', 'mae', 'r2', etc.
    metric_value = models.FloatField()
    dataset_name = models.CharField(max_length=100)
    recorded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.model.name} - {self.metric_name}: {self.metric_value}"

    class Meta:
        ordering = ['-recorded_at']
