# ml_engine/simple_ml_service.py
import os
import pickle
import numpy as np
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from .models import MLModel
import logging

logger = logging.getLogger(__name__)

class SimpleMLService:
    """Service ML simplifié pour la gestion des emplois du temps"""
    
    def __init__(self):
        self.model_dir = os.path.join(settings.MEDIA_ROOT, 'ml_models')
        os.makedirs(self.model_dir, exist_ok=True)
        
    def is_model_trained(self):
        """Vérifie si un modèle est déjà entraîné"""
        try:
            model = MLModel.objects.filter(
                name='default_schedule_model',
                is_trained=True
            ).first()
            return model is not None
        except:
            return False
    
    def get_or_create_model(self):
        """Récupère ou crée le modèle par défaut"""
        model, created = MLModel.get_or_create_default_model()
        
        # Si le modèle n'est pas encore entraîné, l'entraîner
        if not model.is_trained:
            self.train_simple_model(model)
            
        return model
    
    def train_simple_model(self, model):
        """Entraîne un modèle simple (simulation)"""
        try:
            logger.info("Début de l'entraînement du modèle ML...")
            
            # Simulation d'un entraînement simple
            # Dans un vrai projet, ici vous auriez votre algorithme ML
            fake_model_data = {
                'model_type': 'random_forest',
                'features': ['course_duration', 'room_capacity', 'teacher_availability'],
                'trained_at': datetime.now().isoformat(),
                'performance': {
                    'accuracy': 0.85,
                    'precision': 0.82,
                    'recall': 0.88
                }
            }
            
            # Sauvegarder les données du modèle
            model_path = os.path.join(self.model_dir, f'model_{model.id}.pkl')
            with open(model_path, 'wb') as f:
                pickle.dump(fake_model_data, f)
            
            # Mettre à jour le modèle en base
            model.is_trained = True
            model.training_completed_at = timezone.now()
            model.performance_metrics = fake_model_data['performance']
            model.feature_names = fake_model_data['features']
            model.save()
            
            logger.info("Entraînement du modèle ML terminé avec succès")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'entraînement du modèle: {str(e)}")
            return False
    
    def predict_schedule_difficulty(self, course_data):
        """Prédit la difficulté de planification d'un cours"""
        try:
            model = self.get_or_create_model()
            
            if not model.is_trained:
                logger.warning("Modèle non entraîné, utilisation de valeurs par défaut")
                return {
                    'difficulty_score': 0.5,
                    'complexity_level': 'Moyenne',
                    'priority': 2,
                    'confidence': 0.7
                }
            
            # Simulation de prédiction
            # Dans un vrai projet, ici vous chargeriez le modèle et feriez la prédiction
            difficulty_score = np.random.uniform(0.3, 0.9)
            
            if difficulty_score < 0.4:
                complexity_level = 'Facile'
                priority = 1
            elif difficulty_score < 0.7:
                complexity_level = 'Moyenne'
                priority = 2
            else:
                complexity_level = 'Difficile'
                priority = 3
            
            return {
                'difficulty_score': float(difficulty_score),
                'complexity_level': complexity_level,
                'priority': priority,
                'confidence': 0.85,
                'model_used': model.name
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la prédiction: {str(e)}")
            return {
                'difficulty_score': 0.5,
                'complexity_level': 'Moyenne',
                'priority': 2,
                'confidence': 0.5,
                'error': str(e)
            }
    
    def optimize_schedule(self, schedule_data):
        """Optimise un emploi du temps"""
        try:
            model = self.get_or_create_model()
            
            # Simulation d'optimisation
            return {
                'optimized_schedule': schedule_data,  # Dans un vrai projet, ici vous optimiseriez
                'conflicts_resolved': np.random.randint(0, 5),
                'optimization_score': np.random.uniform(0.7, 0.95),
                'suggestions': [
                    'Regrouper les cours par département',
                    'Optimiser l\'utilisation des salles',
                    'Équilibrer la charge des enseignants'
                ],
                'model_used': model.name
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de l'optimisation: {str(e)}")
            return {
                'error': str(e),
                'optimized_schedule': schedule_data,
                'conflicts_resolved': 0,
                'optimization_score': 0.0,
                'suggestions': []
            }

# Instance globale du service
ml_service = SimpleMLService()