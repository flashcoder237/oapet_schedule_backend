# ml_engine/services.py
import pandas as pd
import numpy as np
import os
import json
import joblib
import requests
import networkx as nx
from collections import defaultdict
from itertools import combinations
from typing import Dict, List, Any, Optional
from django.conf import settings
from django.core.files.base import ContentFile
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import xgboost as xgb
import logging

from .models import TimetableDataset, MLModel, PredictionRequest, ModelTrainingTask, FeatureImportance, PredictionHistory

logger = logging.getLogger('ml_engine')


class TimetableDataProcessor:
    """Service pour traiter les données ITC 2007"""
    
    def __init__(self):
        self.base_url = "https://raw.githubusercontent.com/Docheinstein/itc2007-cct/master/datasets/"
        self.datasets_dir = settings.ML_DATASETS_DIR
        
    def download_datasets(self) -> List[str]:
        """Télécharge les datasets ITC 2007"""
        os.makedirs(self.datasets_dir, exist_ok=True)
        instances = [f"comp{i:02d}.ctt" for i in range(1, 22)]
        successful_downloads = []
        
        logger.info("Téléchargement des datasets ITC 2007...")
        for instance in instances:
            try:
                url = self.base_url + instance
                response = requests.get(url, timeout=15)
                if response.status_code == 200:
                    file_path = os.path.join(self.datasets_dir, instance)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    successful_downloads.append(file_path)
                    logger.info(f"✓ {instance}")
                    
                    # Créer l'entrée dans la base de données
                    dataset, created = TimetableDataset.objects.get_or_create(
                        name=instance.replace('.ctt', ''),
                        defaults={
                            'description': f'Dataset ITC 2007 - {instance}',
                            'metadata': {'source': 'ITC 2007', 'url': url}
                        }
                    )
                    dataset.file_path.save(instance, ContentFile(response.text))
                    
            except Exception as e:
                logger.error(f"✗ Erreur {instance}: {str(e)}")
        
        logger.info(f"Téléchargement terminé: {len(successful_downloads)} fichiers")
        return successful_downloads
    
    def parse_instance(self, file_path: str) -> Dict[str, Any]:
        """Parse une instance ITC"""
        data = {
            'metadata': {},
            'courses': [],
            'rooms': [],
            'curricula': [],
            'unavailability': [],
            'room_constraints': []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            lines = content.split('\n')
            sections = content.split('\n\n')
            
            # Parse métadonnées
            for line in lines:
                if ':' in line and not any(line.startswith(prefix) for prefix in 
                    ['COURSES:', 'ROOMS:', 'CURRICULA:', 'UNAVAILABILITY_', 'ROOM_']):
                    key, value = line.split(':', 1)
                    try:
                        data['metadata'][key.strip().lower()] = int(value.strip())
                    except ValueError:
                        data['metadata'][key.strip().lower()] = value.strip()
            
            # Parse sections
            for section in sections:
                section_lines = [line.strip() for line in section.split('\n') if line.strip()]
                if not section_lines:
                    continue
                
                header = section_lines[0]
                data_lines = section_lines[1:]
                
                if header == 'COURSES:':
                    for line in data_lines:
                        parts = line.split()
                        if len(parts) >= 5:
                            data['courses'].append({
                                'id': parts[0],
                                'teacher': parts[1],
                                'lectures': int(parts[2]),
                                'min_days': int(parts[3]),
                                'students': int(parts[4])
                            })
                
                elif header == 'ROOMS:':
                    for line in data_lines:
                        parts = line.split()
                        if len(parts) >= 2:
                            data['rooms'].append({
                                'id': parts[0],
                                'capacity': int(parts[1])
                            })
                
                elif header == 'CURRICULA:':
                    for line in data_lines:
                        parts = line.split()
                        if len(parts) >= 3:
                            data['curricula'].append({
                                'id': parts[0],
                                'num_courses': int(parts[1]),
                                'courses': parts[2:]
                            })
                
                elif header == 'UNAVAILABILITY_CONSTRAINTS:':
                    for line in data_lines:
                        parts = line.split()
                        if len(parts) >= 3:
                            data['unavailability'].append({
                                'course': parts[0],
                                'day': int(parts[1]),
                                'period': int(parts[2])
                            })
                
                elif header == 'ROOM_CONSTRAINTS:':
                    for line in data_lines:
                        parts = line.split()
                        if len(parts) >= 2:
                            data['room_constraints'].append({
                                'course': parts[0],
                                'room': parts[1]
                            })
        
        except Exception as e:
            logger.error(f"Erreur parsing {file_path}: {str(e)}")
        
        return data


class FeatureExtractor:
    """Service pour extraire les features des données ITC"""
    
    def create_conflict_graph(self, instance_data: Dict[str, Any]) -> nx.Graph:
        """Crée un graphe de conflits entre cours"""
        G = nx.Graph()
        
        for course in instance_data['courses']:
            G.add_node(course['id'], **course)
        
        for curriculum in instance_data['curricula']:
            course_pairs = combinations(curriculum['courses'], 2)
            for c1, c2 in course_pairs:
                if G.has_node(c1) and G.has_node(c2):
                    G.add_edge(c1, c2, conflict_type='curriculum')
        
        return G
    
    def extract_features(self, files: List[str]) -> pd.DataFrame:
        """Extrait les features de tous les fichiers"""
        all_features = []
        processor = TimetableDataProcessor()
        
        for file_path in files:
            instance_name = os.path.basename(file_path).replace('.ctt', '')
            logger.info(f"Traitement {instance_name}...")
            
            data = processor.parse_instance(file_path)
            if not data['courses']:
                continue
            
            conflict_graph = self.create_conflict_graph(data)
            
            # Statistiques globales
            total_lectures = sum(course['lectures'] for course in data['courses'])
            total_periods = data['metadata'].get('days', 5) * data['metadata'].get('periods_per_day', 6)
            avg_room_capacity = np.mean([room['capacity'] for room in data['rooms']])
            
            # Features par cours
            for course in data['courses']:
                course_id = course['id']
                
                features = {
                    'instance': instance_name,
                    'course_id': course_id,
                    'lectures': course['lectures'],
                    'min_days': course['min_days'],
                    'students': course['students'],
                    'teacher': course['teacher'],
                    'total_courses': len(data['courses']),
                    'total_rooms': len(data['rooms']),
                    'total_days': data['metadata'].get('days', 5),
                    'periods_per_day': data['metadata'].get('periods_per_day', 6),
                    'total_curricula': len(data['curricula']),
                    'total_lectures': total_lectures,
                    'avg_room_capacity': avg_room_capacity,
                }
                
                # Features calculées
                features.update({
                    'lecture_density': course['lectures'] / total_periods,
                    'student_lecture_ratio': course['students'] / max(course['lectures'], 1),
                    'course_room_ratio': len(data['courses']) / len(data['rooms']),
                    'utilization_pressure': total_lectures / total_periods,
                    'min_days_constraint_tightness': course['lectures'] / max(course['min_days'], 1),
                })
                
                # Features de réseau
                if conflict_graph.has_node(course_id):
                    neighbors = list(conflict_graph.neighbors(course_id))
                    features.update({
                        'conflict_degree': len(neighbors),
                        'conflict_density': len(neighbors) / max(len(data['courses']) - 1, 1),
                        'clustering_coefficient': nx.clustering(conflict_graph, course_id),
                    })
                    
                    try:
                        centrality = nx.betweenness_centrality(conflict_graph)
                        features['betweenness_centrality'] = centrality.get(course_id, 0)
                    except:
                        features['betweenness_centrality'] = 0
                else:
                    features.update({
                        'conflict_degree': 0,
                        'conflict_density': 0,
                        'clustering_coefficient': 0,
                        'betweenness_centrality': 0,
                    })
                
                # Contraintes
                unavail_constraints = [u for u in data['unavailability'] if u['course'] == course_id]
                features['unavailability_count'] = len(unavail_constraints)
                features['unavailability_ratio'] = len(unavail_constraints) / total_periods
                
                room_constraints = [r for r in data['room_constraints'] if r['course'] == course_id]
                features['room_constraint_count'] = len(room_constraints)
                
                # Score de difficulté composite
                difficulty_components = {
                    'conflict_weight': features['conflict_degree'] * 0.25,
                    'constraint_weight': features['unavailability_count'] * 0.20,
                    'density_weight': features['lecture_density'] * 0.15,
                    'student_weight': min(features['students'] / 1000, 1) * 0.15,
                    'room_pressure_weight': features['course_room_ratio'] * 0.10,
                    'utilization_weight': features['utilization_pressure'] * 0.10,
                    'min_days_weight': max(0, course['lectures'] - course['min_days']) * 0.05
                }
                
                features['difficulty_score'] = sum(difficulty_components.values())
                all_features.append(features)
        
        return pd.DataFrame(all_features)


class TimetableMLService:
    """Service principal pour le modèle ML de planification"""
    
    def __init__(self):
        self.models = {}
        self.best_model = None
        self.scaler = StandardScaler()
        self.label_encoders = {}
        self.feature_names = []
        self.results = {}
        
    def prepare_data(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
        """Prépare les données pour l'entraînement"""
        # Features prédictives
        self.feature_names = [
            'lectures', 'min_days', 'students', 'total_courses', 'total_rooms',
            'total_days', 'periods_per_day', 'lecture_density', 'student_lecture_ratio',
            'course_room_ratio', 'utilization_pressure', 'min_days_constraint_tightness',
            'conflict_degree', 'conflict_density', 'clustering_coefficient',
            'betweenness_centrality', 'unavailability_count', 'unavailability_ratio',
            'room_constraint_count'
        ]
        
        # Encodage des variables catégorielles
        self.label_encoders['teacher'] = LabelEncoder()
        self.label_encoders['instance'] = LabelEncoder()
        
        df['teacher_encoded'] = self.label_encoders['teacher'].fit_transform(df['teacher'])
        df['instance_encoded'] = self.label_encoders['instance'].fit_transform(df['instance'])
        
        # Features finales
        X_features = self.feature_names + ['teacher_encoded', 'instance_encoded']
        X = df[X_features].fillna(0)
        y = df['difficulty_score']
        
        return X, y
    
    def create_models(self) -> Dict[str, Any]:
        """Crée les modèles à tester"""
        self.models = {
            'XGBoost': xgb.XGBRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.1,
                random_state=42
            ),
            'Random Forest': RandomForestRegressor(
                n_estimators=150,
                max_depth=12,
                random_state=42
            ),
            'Neural Network': MLPRegressor(
                hidden_layer_sizes=(100, 50),
                max_iter=1000,
                random_state=42
            ),
            'Gradient Boosting': GradientBoostingRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.1,
                random_state=42
            )
        }
        return self.models
    
    def train_models(self, X: pd.DataFrame, y: pd.Series, training_task: Optional[ModelTrainingTask] = None) -> tuple[str, Dict[str, Any]]:
        """Entraîne et évalue tous les modèles"""
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Normalisation pour les modèles qui en ont besoin
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        logger.info("Entraînement des modèles...")
        total_models = len(self.models)
        
        for idx, (name, model) in enumerate(self.models.items()):
            logger.info(f"  {name}...")
            
            # Mise à jour du progrès
            if training_task:
                progress = (idx / total_models) * 100
                training_task.progress = progress
                training_task.logs += f"Entraînement {name}...\n"
                training_task.save()
            
            # Choix des données selon le modèle
            if name == 'Neural Network':
                model.fit(X_train_scaled, y_train)
                y_pred = model.predict(X_test_scaled)
                cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=5, scoring='r2')
            else:
                model.fit(X_train, y_train)
                y_pred = model.predict(X_test)
                cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='r2')
            
            # Métriques
            mse = mean_squared_error(y_test, y_pred)
            mae = mean_absolute_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            
            self.results[name] = {
                'model': model,
                'mse': mse,
                'mae': mae,
                'r2': r2,
                'cv_mean': cv_scores.mean(),
                'cv_std': cv_scores.std()
            }
        
        # Sélection du meilleur modèle
        best_name = max(self.results.keys(), key=lambda k: self.results[k]['r2'])
        self.best_model = self.results[best_name]['model']
        
        # Mise à jour finale du progrès
        if training_task:
            training_task.progress = 100.0
            training_task.results = {name: {k: v for k, v in results.items() if k != 'model'} 
                                   for name, results in self.results.items()}
            training_task.logs += f"Meilleur modèle: {best_name}\n"
            training_task.save()
        
        return best_name, self.results
    
    def save_model(self, model_name: str) -> MLModel:
        """Sauvegarde le modèle dans Django"""
        os.makedirs(settings.ML_MODELS_DIR, exist_ok=True)
        
        # Sauvegarde des fichiers
        model_filename = f'{model_name}_model.pkl'
        scaler_filename = f'{model_name}_scaler.pkl'
        
        model_path = os.path.join(settings.ML_MODELS_DIR, model_filename)
        scaler_path = os.path.join(settings.ML_MODELS_DIR, scaler_filename)
        
        joblib.dump(self.best_model, model_path)
        joblib.dump(self.scaler, scaler_path)
        
        # Sauvegarde des encodeurs
        for name, encoder in self.label_encoders.items():
            encoder_filename = f'{model_name}_{name}_encoder.pkl'
            encoder_path = os.path.join(settings.ML_MODELS_DIR, encoder_filename)
            joblib.dump(encoder, encoder_path)
        
        # Métadonnées
        metadata = {
            'feature_names': self.feature_names + ['teacher_encoded', 'instance_encoded'],
            'model_type': type(self.best_model).__name__,
            'performance': {name: {k: v for k, v in results.items() if k != 'model'} 
                          for name, results in self.results.items()}
        }
        
        # Créer l'entrée Django
        ml_model = MLModel.objects.create(
            name=model_name,
            model_type=self._get_model_type_key(type(self.best_model).__name__),
            description=f'Modèle ML pour prédiction de difficulté de planification',
            performance_metrics=metadata['performance'],
            feature_names=metadata['feature_names'],
            is_active=True
        )
        
        # Sauvegarder les fichiers dans Django
        with open(model_path, 'rb') as f:
            ml_model.model_file.save(model_filename, ContentFile(f.read()))
        
        with open(scaler_path, 'rb') as f:
            ml_model.scaler_file.save(scaler_filename, ContentFile(f.read()))
        
        # Métadonnées JSON
        metadata_content = json.dumps(metadata, indent=2)
        ml_model.metadata_file.save(f'{model_name}_metadata.json', ContentFile(metadata_content))
        
        logger.info(f"Modèle sauvegardé: {ml_model.name}")
        return ml_model
    
    def _get_model_type_key(self, class_name: str) -> str:
        """Convertit le nom de classe en clé de type de modèle"""
        mapping = {
            'XGBRegressor': 'xgboost',
            'RandomForestRegressor': 'random_forest',
            'MLPRegressor': 'neural_network',
            'GradientBoostingRegressor': 'gradient_boosting'
        }
        return mapping.get(class_name, 'unknown')


class TimetablePredictor:
    """Service pour utiliser le modèle entraîné"""
    
    def __init__(self, ml_model: MLModel):
        self.ml_model = ml_model
        self.model = self._load_model()
        self.scaler = self._load_scaler()
        self.label_encoders = self._load_encoders()
        self.feature_names = ml_model.feature_names
    
    def _load_model(self):
        """Charge le modèle depuis le fichier"""
        return joblib.load(self.ml_model.model_file.path)
    
    def _load_scaler(self):
        """Charge le scaler depuis le fichier"""
        if self.ml_model.scaler_file:
            return joblib.load(self.ml_model.scaler_file.path)
        return None
    
    def _load_encoders(self) -> Dict[str, Any]:
        """Charge les encodeurs depuis les métadonnées"""
        encoders = {}
        if self.ml_model.metadata_file:
            # Ici on devrait charger les encodeurs depuis les fichiers séparés
            # Pour simplifier, on crée des encodeurs vides qui seront mis à jour
            encoders['teacher'] = LabelEncoder()
            encoders['instance'] = LabelEncoder()
        return encoders
    
    def predict_difficulty(self, course_data: Dict[str, Any], user=None) -> Dict[str, Any]:
        """Prédit la difficulté de planification d'un cours"""
        # Préparer les features
        features = {}
        for feature in self.feature_names:
            if feature.endswith('_encoded'):
                # Gestion des variables encodées
                original_feature = feature.replace('_encoded', '')
                if original_feature in course_data:
                    try:
                        if original_feature in self.label_encoders:
                            encoded_value = self.label_encoders[original_feature].transform([course_data[original_feature]])[0]
                            features[feature] = encoded_value
                        else:
                            features[feature] = 0
                    except (ValueError, KeyError):
                        features[feature] = 0  # Valeur inconnue
                else:
                    features[feature] = 0
            else:
                features[feature] = course_data.get(feature, 0)
        
        # Prédiction
        feature_vector = np.array([features[f] for f in self.feature_names]).reshape(1, -1)
        
        if self.scaler and self.ml_model.model_type == 'neural_network':
            feature_vector = self.scaler.transform(feature_vector)
        
        difficulty = self.model.predict(feature_vector)[0]
        
        # Classification
        if difficulty < 0.3:
            level = "Faible"
            priority = 3
        elif difficulty < 0.7:
            level = "Moyenne"
            priority = 2
        else:
            level = "Élevée"
            priority = 1
        
        result = {
            'difficulty_score': float(difficulty),
            'complexity_level': level,
            'priority': priority,
            'recommendations': self._get_recommendations(level, course_data)
        }
        
        # Sauvegarder dans l'historique
        if user:
            PredictionHistory.objects.create(
                user=user,
                course_name=course_data.get('course_name', 'Cours inconnu'),
                predicted_difficulty=difficulty,
                complexity_level=level,
                priority=priority,
                prediction_data=result
            )
        
        return result
    
    def _get_recommendations(self, level: str, course_data: Dict[str, Any]) -> List[str]:
        """Génère des recommandations basées sur la complexité"""
        recommendations = []
        
        if level == "Élevée":
            recommendations.extend([
                "Planifier en priorité absolue",
                "Allouer les meilleurs créneaux",
                "Prévoir des alternatives",
                "Assigner une salle adaptée"
            ])
        elif level == "Moyenne":
            recommendations.extend([
                "Planifier après les cours prioritaires",
                "Vérifier les contraintes",
                "Optimiser l'utilisation des ressources"
            ])
        else:
            recommendations.extend([
                "Flexible pour combler les créneaux",
                "Peut être reprogrammé si nécessaire"
            ])
        
        # Recommandations spécifiques
        if course_data.get('students', 0) > 100:
            recommendations.append("Nécessite une grande salle")
        
        if course_data.get('lectures', 0) > 3:
            recommendations.append("Étaler sur plusieurs jours")
        
        return recommendations


class MLTrainingService:
    """Service pour gérer l'entraînement des modèles ML"""
    
    @staticmethod
    def start_training(dataset: TimetableDataset, model_types: List[str], parameters: Dict[str, Any], user) -> ModelTrainingTask:
        """Démarre une tâche d'entraînement"""
        training_task = ModelTrainingTask.objects.create(
            name=f"Training_{dataset.name}_{user.username}",
            dataset=dataset,
            model_types=model_types,
            parameters=parameters,
            created_by=user,
            status='queued'
        )
        
        # Ici on pourrait lancer la tâche en arrière-plan avec Celery
        # Pour l'instant, on exécute directement
        try:
            training_task.status = 'running'
            training_task.save()
            
            # Traitement des données
            processor = TimetableDataProcessor()
            extractor = FeatureExtractor()
            ml_service = TimetableMLService()
            
            # Télécharger si nécessaire
            if not os.path.exists(dataset.file_path.path):
                files = processor.download_datasets()
            else:
                files = [dataset.file_path.path]
            
            # Extraction des features
            df = extractor.extract_features(files)
            
            if df.empty:
                training_task.status = 'failed'
                training_task.logs += "Aucune donnée extraite\n"
                training_task.save()
                return training_task
            
            # Entraînement
            ml_service.create_models()
            X, y = ml_service.prepare_data(df)
            best_name, results = ml_service.train_models(X, y, training_task)
            
            # Sauvegarde du modèle
            ml_model = ml_service.save_model(f"{dataset.name}_{best_name.replace(' ', '_')}")
            
            training_task.status = 'completed'
            training_task.results['best_model'] = best_name
            training_task.results['model_id'] = ml_model.id
            training_task.save()
            
        except Exception as e:
            training_task.status = 'failed'
            training_task.logs += f"Erreur: {str(e)}\n"
            training_task.save()
            logger.error(f"Erreur entraînement: {str(e)}")
        
        return training_task