# ml_engine/serializers.py
from rest_framework import serializers
from .models import (
    TimetableDataset, MLModel, PredictionRequest, ModelTrainingTask,
    FeatureImportance, PredictionHistory, ModelPerformanceMetric
)


class TimetableDatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimetableDataset
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class MLModelSerializer(serializers.ModelSerializer):
    performance_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = MLModel
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
    
    def get_performance_summary(self, obj):
        """Retourne un résumé des performances du modèle"""
        if not obj.performance_metrics:
            return None
        
        # Calculer le score moyen
        scores = []
        for model_name, metrics in obj.performance_metrics.items():
            if isinstance(metrics, dict) and 'r2' in metrics:
                scores.append(metrics['r2'])
        
        return {
            'average_r2': sum(scores) / len(scores) if scores else 0,
            'model_count': len(scores),
            'best_score': max(scores) if scores else 0
        }


class PredictionRequestSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    model_name = serializers.CharField(source='model.name', read_only=True)
    
    class Meta:
        model = PredictionRequest
        fields = '__all__'
        read_only_fields = ('created_at', 'completed_at', 'processing_time')


class ModelTrainingTaskSerializer(serializers.ModelSerializer):
    dataset_name = serializers.CharField(source='dataset.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = ModelTrainingTask
        fields = '__all__'
        read_only_fields = ('created_at', 'started_at', 'completed_at')
    
    def get_duration(self, obj):
        """Calcule la durée d'entraînement"""
        if obj.started_at and obj.completed_at:
            duration = obj.completed_at - obj.started_at
            return duration.total_seconds()
        return None


class FeatureImportanceSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source='model.name', read_only=True)
    
    class Meta:
        model = FeatureImportance
        fields = '__all__'


class PredictionHistorySerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    accuracy = serializers.SerializerMethodField()
    
    class Meta:
        model = PredictionHistory
        fields = '__all__'
        read_only_fields = ('created_at',)
    
    def get_accuracy(self, obj):
        """Calcule la précision si une valeur réelle est fournie"""
        if obj.actual_difficulty and obj.predicted_difficulty:
            error = abs(obj.actual_difficulty - obj.predicted_difficulty)
            return max(0, 1 - error)
        return None


class ModelPerformanceMetricSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source='model.name', read_only=True)
    
    class Meta:
        model = ModelPerformanceMetric
        fields = '__all__'
        read_only_fields = ('recorded_at',)


class CoursePredictionSerializer(serializers.Serializer):
    """Serializer pour les requêtes de prédiction de difficulté de cours"""
    course_name = serializers.CharField(max_length=200)
    lectures = serializers.IntegerField(min_value=1)
    min_days = serializers.IntegerField(min_value=1)
    students = serializers.IntegerField(min_value=1)
    teacher = serializers.CharField(max_length=100)
    instance = serializers.CharField(max_length=50, default='custom')
    total_courses = serializers.IntegerField(min_value=1, default=30)
    total_rooms = serializers.IntegerField(min_value=1, default=10)
    total_days = serializers.IntegerField(min_value=1, default=5)
    periods_per_day = serializers.IntegerField(min_value=1, default=6)
    lecture_density = serializers.FloatField(min_value=0, max_value=1, default=0.1)
    student_lecture_ratio = serializers.FloatField(min_value=0, default=40)
    course_room_ratio = serializers.FloatField(min_value=0, default=3)
    utilization_pressure = serializers.FloatField(min_value=0, max_value=1, default=0.7)
    min_days_constraint_tightness = serializers.FloatField(min_value=0, default=1.5)
    conflict_degree = serializers.IntegerField(min_value=0, default=4)
    conflict_density = serializers.FloatField(min_value=0, max_value=1, default=0.15)
    clustering_coefficient = serializers.FloatField(min_value=0, max_value=1, default=0.3)
    betweenness_centrality = serializers.FloatField(min_value=0, max_value=1, default=0.1)
    unavailability_count = serializers.IntegerField(min_value=0, default=2)
    unavailability_ratio = serializers.FloatField(min_value=0, max_value=1, default=0.067)
    room_constraint_count = serializers.IntegerField(min_value=0, default=1)


class PredictionResponseSerializer(serializers.Serializer):
    """Serializer pour les réponses de prédiction"""
    difficulty_score = serializers.FloatField()
    complexity_level = serializers.CharField()
    priority = serializers.IntegerField()
    recommendations = serializers.ListField(child=serializers.CharField())
    processing_time = serializers.FloatField(required=False)
    model_used = serializers.CharField(required=False)