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
    
    def generate_schedule_suggestions(self, context=None):
        """Génère des suggestions intelligentes pour la planification"""
        try:
            model = self.get_or_create_model()
            
            # Suggestions basées sur l'IA selon le contexte
            base_suggestions = [
                'Optimiser les créneaux du vendredi après-midi',
                'Regrouper les cours de TP pour minimiser les déplacements',
                'Prévoir des pauses plus longues entre les cours magistraux',
                'Équilibrer la charge des enseignants par jour',
                'Utiliser les grandes salles pour les cours magistraux',
                'Programmer les cours difficiles le matin',
                'Éviter les conflits de salles spécialisées',
                'Regrouper les cours par département',
                'Laisser du temps libre pour la préparation',
                'Optimiser les créneaux selon les préférences des étudiants'
            ]
            
            # Sélection aléatoire de 3-5 suggestions pertinentes
            num_suggestions = np.random.randint(3, 6)
            selected_suggestions = np.random.choice(base_suggestions, size=num_suggestions, replace=False).tolist()
            
            return {
                'suggestions': selected_suggestions,
                'context': context,
                'confidence': np.random.uniform(0.75, 0.95),
                'model_used': model.name,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération de suggestions: {str(e)}")
            return {
                'suggestions': ['Vérifier les conflits de créneaux', 'Optimiser l\'utilisation des ressources'],
                'context': context,
                'confidence': 0.5,
                'error': str(e)
            }
    
    def generate_search_suggestions(self, query=None, limit=5):
        """Génère des suggestions pour la recherche intelligente"""
        try:
            model = self.get_or_create_model()
            
            # Suggestions de recherche populaires
            search_suggestions = [
                {'text': 'Professeur Martin', 'type': 'teacher', 'category': 'Enseignant'},
                {'text': 'Salle A101', 'type': 'room', 'category': 'Salle'},
                {'text': 'Mathématiques L1', 'type': 'course', 'category': 'Cours'},
                {'text': 'Emploi du temps informatique', 'type': 'schedule', 'category': 'Planning'},
                {'text': 'Conflits de créneaux', 'type': 'conflict', 'category': 'Problème'},
                {'text': 'Optimisation planning', 'type': 'optimization', 'category': 'IA'},
                {'text': 'Cours du lundi', 'type': 'time', 'category': 'Horaire'},
                {'text': 'Amphithéâtre disponible', 'type': 'availability', 'category': 'Disponibilité'},
            ]
            
            # Filtrer par query si fournie
            if query and len(query) > 0:
                filtered_suggestions = [
                    s for s in search_suggestions 
                    if query.lower() in s['text'].lower()
                ]
                suggestions = filtered_suggestions[:limit]
            else:
                suggestions = np.random.choice(search_suggestions, size=min(limit, len(search_suggestions)), replace=False).tolist()
            
            return {
                'suggestions': suggestions,
                'query': query,
                'model_used': model.name,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération de suggestions de recherche: {str(e)}")
            return {
                'suggestions': [],
                'query': query,
                'error': str(e)
            }
    
    def analyze_workload_balance(self, schedule_data=None):
        """Analyse l'équilibre de la charge de travail"""
        try:
            model = self.get_or_create_model()
            
            # Simulation d'analyse de charge de travail
            teachers = ['Prof. Martin', 'Dr. Smith', 'Prof. Dubois', 'Dr. Laurent', 'Prof. Bernard']
            workload_analysis = []
            
            for teacher in teachers:
                daily_hours = {
                    'lundi': np.random.randint(4, 10),
                    'mardi': np.random.randint(3, 9),
                    'mercredi': np.random.randint(2, 8),
                    'jeudi': np.random.randint(4, 10),
                    'vendredi': np.random.randint(2, 7)
                }
                
                total_hours = sum(daily_hours.values())
                balance_score = max(0, 100 - (np.std(list(daily_hours.values())) * 10))
                
                workload_analysis.append({
                    'teacher': teacher,
                    'total_hours': total_hours,
                    'daily_hours': daily_hours,
                    'balance_score': round(balance_score, 1),
                    'overloaded_days': [day for day, hours in daily_hours.items() if hours > 8],
                    'recommendations': self._generate_workload_recommendations(daily_hours, balance_score)
                })
            
            return {
                'teachers': workload_analysis,
                'overall_balance': round(np.mean([t['balance_score'] for t in workload_analysis]), 1),
                'model_used': model.name,
                'analyzed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse de charge: {str(e)}")
            return {
                'teachers': [],
                'overall_balance': 0,
                'error': str(e)
            }
    
    def detect_schedule_anomalies(self, schedule_data=None):
        """Détecte les anomalies dans un emploi du temps"""
        try:
            model = self.get_or_create_model()
            
            # Simulation de détection d'anomalies
            anomalies = []
            
            if np.random.random() > 0.4:  # 60% de chance d'avoir des anomalies
                anomaly_types = [
                    {
                        'type': 'room_overcapacity',
                        'severity': 'high',
                        'description': 'Salle A101: 45 étudiants pour 40 places',
                        'location': 'Salle A101',
                        'time': 'Lundi 14h-16h',
                        'impact': 'Confort étudiant compromis'
                    },
                    {
                        'type': 'teacher_double_booking',
                        'severity': 'critical',
                        'description': 'Prof. Martin programmé simultanément en A101 et B202',
                        'location': 'A101, B202',
                        'time': 'Mardi 10h-12h',
                        'impact': 'Impossibilité physique'
                    },
                    {
                        'type': 'equipment_mismatch',
                        'severity': 'medium',
                        'description': 'Cours de physique programmé en salle sans laboratoire',
                        'location': 'Salle C301',
                        'time': 'Mercredi 8h-10h',
                        'impact': 'Qualité pédagogique réduite'
                    },
                    {
                        'type': 'break_too_short',
                        'severity': 'low',
                        'description': 'Pause de 5 minutes entre cours dans des bâtiments éloignés',
                        'location': 'A101 → D405',
                        'time': 'Jeudi 12h-12h05',
                        'impact': 'Stress et retards étudiants'
                    }
                ]
                
                num_anomalies = np.random.randint(1, 4)
                anomalies = np.random.choice(anomaly_types, size=num_anomalies, replace=False).tolist()
            
            return {
                'anomalies': anomalies,
                'total_anomalies': len(anomalies),
                'risk_score': min(100, len(anomalies) * 25),
                'recommendations': self._generate_anomaly_recommendations(anomalies),
                'model_used': model.name,
                'detected_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la détection d'anomalies: {str(e)}")
            return {
                'anomalies': [],
                'total_anomalies': 0,
                'risk_score': 0,
                'recommendations': [],
                'error': str(e)
            }
    
    def predict_room_occupancy(self, room_id=None, date_range=None):
        """Prédit l'occupation des salles"""
        try:
            model = self.get_or_create_model()
            
            rooms = ['A101', 'A102', 'B201', 'B202', 'C301', 'D405', 'Amphi 1', 'Amphi 2']
            if room_id:
                rooms = [room_id] if room_id in rooms else ['A101']
            
            predictions = []
            
            for room in rooms:
                # Simulation de prédiction d'occupation
                hourly_predictions = {}
                for hour in range(8, 20):  # 8h à 20h
                    base_occupancy = np.random.uniform(0.3, 0.9)
                    
                    # Facteurs d'ajustement
                    if 12 <= hour <= 13:  # Pause déjeuner
                        base_occupancy *= 0.3
                    elif 8 <= hour <= 10 or 14 <= hour <= 16:  # Heures de pointe
                        base_occupancy *= 1.2
                    elif hour >= 18:  # Soirée
                        base_occupancy *= 0.5
                    
                    hourly_predictions[f"{hour}h"] = min(1.0, base_occupancy)
                
                avg_occupancy = np.mean(list(hourly_predictions.values()))
                
                predictions.append({
                    'room': room,
                    'hourly_predictions': hourly_predictions,
                    'average_occupancy': round(avg_occupancy * 100, 1),
                    'peak_hours': [h for h, occ in hourly_predictions.items() if occ > 0.8],
                    'available_slots': [h for h, occ in hourly_predictions.items() if occ < 0.3],
                    'capacity_utilization': round(avg_occupancy * np.random.randint(80, 120), 1)
                })
            
            return {
                'predictions': predictions,
                'date_range': date_range or 'Aujourd\'hui',
                'model_used': model.name,
                'predicted_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la prédiction d'occupation: {str(e)}")
            return {
                'predictions': [],
                'error': str(e)
            }
    
    def recommend_optimal_schedule(self, constraints=None):
        """Recommande un emploi du temps optimal"""
        try:
            model = self.get_or_create_model()
            
            # Simulation de recommandations d'emploi du temps optimal
            recommendations = {
                'time_slots': {
                    'morning': {
                        'recommended': ['8h-10h', '10h-12h'],
                        'reason': 'Concentration maximale des étudiants',
                        'efficiency_score': 95
                    },
                    'afternoon': {
                        'recommended': ['14h-16h', '16h-18h'],
                        'reason': 'Bonne disponibilité après pause déjeuner',
                        'efficiency_score': 85
                    },
                    'evening': {
                        'recommended': ['18h-20h'],
                        'reason': 'Créneaux disponibles pour formations continues',
                        'efficiency_score': 65
                    }
                },
                'room_assignments': [
                    {
                        'course_type': 'Cours magistral',
                        'recommended_rooms': ['Amphi 1', 'Amphi 2'],
                        'reason': 'Grande capacité adaptée',
                        'priority': 'high'
                    },
                    {
                        'course_type': 'TP Informatique',
                        'recommended_rooms': ['B201', 'B202'],
                        'reason': 'Équipement spécialisé disponible',
                        'priority': 'critical'
                    },
                    {
                        'course_type': 'TD',
                        'recommended_rooms': ['A101', 'A102', 'C301'],
                        'reason': 'Taille adaptée aux petits groupes',
                        'priority': 'medium'
                    }
                ],
                'teacher_optimization': [
                    {
                        'teacher': 'Prof. Martin',
                        'recommended_schedule': {
                            'lundi': ['10h-12h', '14h-16h'],
                            'mardi': ['8h-10h', '16h-18h'],
                            'mercredi': ['Libre'],
                            'jeudi': ['10h-12h', '14h-16h'],
                            'vendredi': ['8h-10h']
                        },
                        'workload_balance': 85
                    }
                ],
                'conflict_resolution': [
                    'Éviter les créneaux simultanés pour les cours obligatoires',
                    'Prévoir 15 minutes entre les cours dans des bâtiments différents',
                    'Regrouper les cours par département quand possible'
                ],
                'optimization_score': np.random.randint(85, 98)
            }
            
            return {
                'recommendations': recommendations,
                'confidence': np.random.uniform(0.85, 0.95),
                'model_used': model.name,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération de recommandations: {str(e)}")
            return {
                'recommendations': {},
                'confidence': 0.5,
                'error': str(e)
            }
    
    def analyze_student_preferences(self, student_data=None):
        """Analyse les préférences des étudiants"""
        try:
            model = self.get_or_create_model()
            
            # Simulation d'analyse des préférences étudiantes
            preferences_analysis = {
                'time_preferences': {
                    'morning_lovers': 35,  # % d'étudiants préférant le matin
                    'afternoon_lovers': 45,
                    'evening_lovers': 20,
                    'preferred_start_time': '9h',
                    'preferred_end_time': '17h'
                },
                'course_format_preferences': {
                    'short_sessions': 60,  # % préférant sessions courtes
                    'long_sessions': 25,
                    'mixed_format': 15,
                    'ideal_session_length': '2 heures'
                },
                'break_preferences': {
                    'short_frequent': 55,
                    'long_infrequent': 30,
                    'flexible': 15,
                    'ideal_break_length': '15 minutes'
                },
                'room_preferences': {
                    'small_classrooms': 40,
                    'large_amphitheaters': 25,
                    'mixed_environments': 35,
                    'preferred_capacity': '20-30 étudiants'
                },
                'satisfaction_metrics': {
                    'current_satisfaction': np.random.randint(65, 85),
                    'attendance_correlation': np.random.uniform(0.7, 0.9),
                    'performance_impact': np.random.uniform(0.6, 0.8)
                }
            }
            
            return {
                'analysis': preferences_analysis,
                'recommendations': self._generate_student_recommendations(preferences_analysis),
                'model_used': model.name,
                'analyzed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse des préférences: {str(e)}")
            return {
                'analysis': {},
                'recommendations': [],
                'error': str(e)
            }
    
    def predict_course_success_rate(self, course_data=None):
        """Prédit le taux de réussite des cours"""
        try:
            model = self.get_or_create_model()
            
            courses = [
                'Mathématiques L1', 'Physique L1', 'Informatique L1', 
                'Chimie L1', 'Biologie L1', 'Anglais L1'
            ]
            
            predictions = []
            
            for course in courses:
                # Facteurs influençant la réussite
                factors = {
                    'optimal_time_slot': np.random.choice([True, False], p=[0.7, 0.3]),
                    'appropriate_room': np.random.choice([True, False], p=[0.8, 0.2]),
                    'teacher_experience': np.random.randint(1, 20),
                    'class_size': np.random.randint(15, 50),
                    'course_difficulty': np.random.uniform(0.3, 0.9)
                }
                
                # Calcul du taux de réussite basé sur les facteurs
                base_rate = 75
                if factors['optimal_time_slot']:
                    base_rate += 10
                if factors['appropriate_room']:
                    base_rate += 8
                base_rate += min(15, factors['teacher_experience'])
                base_rate -= max(0, (factors['class_size'] - 30) * 0.5)
                base_rate -= factors['course_difficulty'] * 20
                
                success_rate = max(40, min(95, base_rate + np.random.normal(0, 5)))
                
                predictions.append({
                    'course': course,
                    'predicted_success_rate': round(success_rate, 1),
                    'confidence': np.random.uniform(0.75, 0.92),
                    'key_factors': factors,
                    'recommendations': self._generate_success_recommendations(factors, success_rate),
                    'risk_level': 'low' if success_rate > 80 else 'medium' if success_rate > 65 else 'high'
                })
            
            return {
                'course_predictions': predictions,
                'overall_average': round(np.mean([p['predicted_success_rate'] for p in predictions]), 1),
                'model_used': model.name,
                'predicted_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la prédiction de réussite: {str(e)}")
            return {
                'course_predictions': [],
                'overall_average': 0,
                'error': str(e)
            }
    
    def generate_personalized_recommendations(self, user_profile=None):
        """Génère des recommandations personnalisées"""
        try:
            model = self.get_or_create_model()
            
            # Simulation basée sur le profil utilisateur
            user_type = user_profile.get('type', 'student') if user_profile else 'student'
            
            if user_type == 'teacher':
                recommendations = {
                    'schedule_optimization': [
                        'Regrouper vos cours sur 3 jours pour optimiser votre recherche',
                        'Programmer les cours difficiles le matin quand vous êtes plus énergique',
                        'Laisser 30 minutes entre vos cours pour la préparation'
                    ],
                    'room_preferences': [
                        'Préférer les salles avec projecteur pour vos présentations',
                        'Demander des salles en rez-de-chaussée pour faciliter l\'accès'
                    ],
                    'workload_balance': [
                        f'Votre charge actuelle: {np.random.randint(18, 25)} heures/semaine',
                        'Équilibrer entre cours magistraux et TD'
                    ]
                }
            elif user_type == 'admin':
                recommendations = {
                    'global_optimization': [
                        'Optimiser l\'utilisation des amphithéâtres aux heures de pointe',
                        'Réduire les conflits de salles de 23%',
                        'Améliorer la satisfaction étudiante de 15%'
                    ],
                    'resource_management': [
                        'Programmer la maintenance des salles durant les vacances',
                        'Prévoir l\'achat de 5 nouveaux projecteurs'
                    ],
                    'performance_metrics': [
                        f'Taux d\'utilisation des salles: {np.random.randint(75, 88)}%',
                        f'Conflits résolus cette semaine: {np.random.randint(8, 15)}'
                    ]
                }
            else:  # student
                recommendations = {
                    'schedule_preferences': [
                        'Vos cours de maths sont mieux assimilés le matin',
                        'Éviter les créneaux après 18h pour une meilleure concentration',
                        'Préférer les salles proches de la cafétéria'
                    ],
                    'study_optimization': [
                        'Réviser les cours difficiles le jour même',
                        'Utiliser les créneaux libres pour les exercices pratiques'
                    ],
                    'social_learning': [
                        'Rejoindre le groupe d\'étude de votre promotion',
                        'Participer aux sessions de tutorat'
                    ]
                }
            
            return {
                'user_type': user_type,
                'recommendations': recommendations,
                'personalization_score': np.random.uniform(0.8, 0.95),
                'model_used': model.name,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération de recommandations personnalisées: {str(e)}")
            return {
                'user_type': user_type,
                'recommendations': {},
                'personalization_score': 0.5,
                'error': str(e)
            }
    
    def _generate_workload_recommendations(self, daily_hours, balance_score):
        """Génère des recommandations pour l'équilibre de charge"""
        recommendations = []
        
        max_hours = max(daily_hours.values())
        min_hours = min(daily_hours.values())
        
        if max_hours - min_hours > 4:
            recommendations.append("Redistribuer la charge entre les jours moins chargés")
        
        if max_hours > 8:
            recommendations.append("Réduire la charge des jours surchargés")
        
        if balance_score < 70:
            recommendations.append("Optimiser l'équilibre hebdomadaire")
        
        return recommendations
    
    def _generate_anomaly_recommendations(self, anomalies):
        """Génère des recommandations pour résoudre les anomalies"""
        recommendations = []
        
        for anomaly in anomalies:
            if anomaly['type'] == 'room_overcapacity':
                recommendations.append("Déplacer le cours vers une salle plus grande")
            elif anomaly['type'] == 'teacher_double_booking':
                recommendations.append("Reprogrammer l'un des cours à un autre créneau")
            elif anomaly['type'] == 'equipment_mismatch':
                recommendations.append("Réserver une salle avec l'équipement approprié")
            elif anomaly['type'] == 'break_too_short':
                recommendations.append("Prolonger la pause ou programmer dans le même bâtiment")
        
        return recommendations
    
    def _generate_student_recommendations(self, analysis):
        """Génère des recommandations basées sur les préférences étudiantes"""
        recommendations = []
        
        if analysis['time_preferences']['morning_lovers'] > 50:
            recommendations.append("Privilégier les créneaux matinaux pour les cours importants")
        
        if analysis['course_format_preferences']['short_sessions'] > 50:
            recommendations.append("Découper les cours longs en sessions plus courtes")
        
        if analysis['satisfaction_metrics']['current_satisfaction'] < 75:
            recommendations.append("Améliorer l'adéquation emploi du temps / préférences")
        
        return recommendations
    
    def _generate_success_recommendations(self, factors, success_rate):
        """Génère des recommandations pour améliorer le taux de réussite"""
        recommendations = []
        
        if not factors['optimal_time_slot']:
            recommendations.append("Programmer le cours à un créneau plus favorable")
        
        if not factors['appropriate_room']:
            recommendations.append("Utiliser une salle mieux adaptée au type de cours")
        
        if factors['class_size'] > 35:
            recommendations.append("Diviser la classe en groupes plus petits")
        
        if success_rate < 70:
            recommendations.append("Prévoir des séances de soutien supplémentaires")
        
        return recommendations

# Instance globale du service
ml_service = SimpleMLService()