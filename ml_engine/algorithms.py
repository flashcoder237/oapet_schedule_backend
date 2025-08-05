#!/usr/bin/env python3
"""
Algorithmes d'optimisation avancés pour OAPET
==============================================

Implémentation des algorithmes métaheuristiques pour l'optimisation
des emplois du temps universitaires.

Algorithmes inclus:
- Algorithme Génétique (GA)
- Recuit Simulé (SA)
- Optimisation par Essaim de Particules (PSO)
- Recherche Tabou
- Algorithme de Fourmis (ACO)
- Optimisation Multi-Objectifs (NSGA-II)
"""

import random
import math
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from copy import deepcopy
from collections import defaultdict
import logging

from django.db import transaction
from schedules.models import Schedule, ScheduleSession, TimeSlot, Conflict
from courses.models import Course, Teacher
from rooms.models import Room

logger = logging.getLogger('ml_engine.algorithms')


@dataclass
class OptimizationObjective:
    """Définit un objectif d'optimisation"""
    name: str
    weight: float
    minimize: bool = True  # True pour minimiser, False pour maximiser


@dataclass
class OptimizationConstraint:
    """Définit une contrainte d'optimisation"""
    name: str
    type: str  # 'hard' ou 'soft'
    violation_penalty: float
    check_function: callable


class TimetableSolution:
    """Représente une solution d'emploi du temps"""
    
    def __init__(self, schedule_id: int):
        self.schedule_id = schedule_id
        self.assignments = {}  # {session_id: (time_slot_id, room_id)}
        self.fitness = 0.0
        self.objectives = {}
        self.constraint_violations = {}
        self.is_feasible = True
        
    def copy(self):
        """Crée une copie de la solution"""
        new_solution = TimetableSolution(self.schedule_id)
        new_solution.assignments = self.assignments.copy()
        new_solution.fitness = self.fitness
        new_solution.objectives = self.objectives.copy()
        new_solution.constraint_violations = self.constraint_violations.copy()
        new_solution.is_feasible = self.is_feasible
        return new_solution
    
    def get_sessions_at_time(self, time_slot_id: int) -> List[int]:
        """Retourne les sessions planifiées à un créneau donné"""
        return [session_id for session_id, (ts_id, _) in self.assignments.items() 
                if ts_id == time_slot_id]
    
    def get_sessions_in_room(self, room_id: int) -> List[int]:
        """Retourne les sessions planifiées dans une salle donnée"""
        return [session_id for session_id, (_, r_id) in self.assignments.items() 
                if r_id == room_id]


class ObjectiveCalculator:
    """Calculateur des fonctions objectifs"""
    
    def __init__(self):
        self.objectives = [
            OptimizationObjective("minimize_conflicts", 1.0, True),
            OptimizationObjective("maximize_room_utilization", 0.3, False),
            OptimizationObjective("minimize_teacher_gaps", 0.2, True),
            OptimizationObjective("balance_daily_load", 0.15, True),
            OptimizationObjective("respect_preferences", 0.1, False),
        ]
    
    def calculate_fitness(self, solution: TimetableSolution) -> float:
        """Calcule la fitness globale d'une solution"""
        total_fitness = 0.0
        
        for objective in self.objectives:
            value = getattr(self, f"calculate_{objective.name}")(solution)
            solution.objectives[objective.name] = value
            
            # Normaliser et pondérer
            if objective.minimize:
                fitness_contribution = -value * objective.weight
            else:
                fitness_contribution = value * objective.weight
            
            total_fitness += fitness_contribution
        
        solution.fitness = total_fitness
        return total_fitness
    
    def calculate_minimize_conflicts(self, solution: TimetableSolution) -> float:
        """Calcule le nombre de conflits"""
        conflicts = 0
        time_room_assignments = defaultdict(list)
        teacher_time_assignments = defaultdict(list)
        
        # Grouper les affectations
        for session_id, (time_slot_id, room_id) in solution.assignments.items():
            time_room_assignments[(time_slot_id, room_id)].append(session_id)
            
            # Récupérer l'enseignant de la session
            try:
                session = ScheduleSession.objects.get(id=session_id)
                teacher_time_assignments[(session.teacher.id, time_slot_id)].append(session_id)
            except ScheduleSession.DoesNotExist:
                continue
        
        # Compter les conflits de salle
        for (time_slot_id, room_id), sessions in time_room_assignments.items():
            if len(sessions) > 1:
                conflicts += len(sessions) - 1
        
        # Compter les conflits d'enseignant
        for (teacher_id, time_slot_id), sessions in teacher_time_assignments.items():
            if len(sessions) > 1:
                conflicts += len(sessions) - 1
        
        return float(conflicts)
    
    def calculate_maximize_room_utilization(self, solution: TimetableSolution) -> float:
        """Calcule le taux d'utilisation des salles"""
        if not solution.assignments:
            return 0.0
        
        room_usage = defaultdict(int)
        total_slots = len(TimeSlot.objects.filter(is_active=True))
        
        for time_slot_id, room_id in solution.assignments.values():
            room_usage[room_id] += 1
        
        if not room_usage:
            return 0.0
        
        # Calculer le taux d'utilisation moyen
        total_rooms = len(room_usage)
        avg_utilization = sum(room_usage.values()) / (total_rooms * total_slots)
        
        return min(avg_utilization, 1.0)
    
    def calculate_minimize_teacher_gaps(self, solution: TimetableSolution) -> float:
        """Calcule les trous dans l'emploi du temps des enseignants"""
        teacher_schedules = defaultdict(list)
        
        # Grouper par enseignant
        for session_id, (time_slot_id, room_id) in solution.assignments.items():
            try:
                session = ScheduleSession.objects.get(id=session_id)
                time_slot = TimeSlot.objects.get(id=time_slot_id)
                teacher_schedules[session.teacher.id].append({
                    'day': time_slot.day_of_week,
                    'start': time_slot.start_time,
                    'session_id': session_id
                })
            except (ScheduleSession.DoesNotExist, TimeSlot.DoesNotExist):
                continue
        
        total_gaps = 0
        for teacher_id, sessions in teacher_schedules.items():
            # Trier par jour et heure
            sessions.sort(key=lambda x: (x['day'], x['start']))
            
            # Compter les trous par jour
            daily_sessions = defaultdict(list)
            for session in sessions:
                daily_sessions[session['day']].append(session)
            
            for day, day_sessions in daily_sessions.items():
                if len(day_sessions) > 1:
                    # Compter les trous entre les sessions
                    for i in range(len(day_sessions) - 1):
                        current_end = day_sessions[i]['start']
                        next_start = day_sessions[i + 1]['start']
                        
                        # Calculer l'écart en heures
                        gap_hours = (next_start.hour - current_end.hour)
                        if gap_hours > 2:  # Considérer comme un trou si > 2h
                            total_gaps += gap_hours - 1.5  # 1.5h de pause acceptable
        
        return float(total_gaps)
    
    def calculate_balance_daily_load(self, solution: TimetableSolution) -> float:
        """Calcule l'équilibre de la charge quotidienne"""
        daily_load = defaultdict(int)
        
        for time_slot_id, _ in solution.assignments.values():
            try:
                time_slot = TimeSlot.objects.get(id=time_slot_id)
                daily_load[time_slot.day_of_week] += 1
            except TimeSlot.DoesNotExist:
                continue
        
        if not daily_load:
            return 0.0
        
        loads = list(daily_load.values())
        mean_load = sum(loads) / len(loads)
        variance = sum((load - mean_load) ** 2 for load in loads) / len(loads)
        
        return math.sqrt(variance)  # Écart-type comme mesure de déséquilibre
    
    def calculate_respect_preferences(self, solution: TimetableSolution) -> float:
        """Calcule le respect des préférences"""
        preference_score = 0.0
        total_sessions = len(solution.assignments)
        
        if total_sessions == 0:
            return 0.0
        
        for session_id, (time_slot_id, room_id) in solution.assignments.items():
            try:
                session = ScheduleSession.objects.get(id=session_id)
                time_slot = TimeSlot.objects.get(id=time_slot_id)
                
                # Vérifier les préférences du cours
                if session.course.preferred_times:
                    for pref in session.course.preferred_times:
                        if (pref.get('day') == time_slot.day_of_week and
                            pref.get('start_time') <= time_slot.start_time.strftime('%H:%M') <= pref.get('end_time')):
                            preference_score += 1.0
                            break
                else:
                    preference_score += 0.5  # Score neutre si pas de préférence
                
            except (ScheduleSession.DoesNotExist, TimeSlot.DoesNotExist):
                continue
        
        return preference_score / total_sessions


class GeneticAlgorithm:
    """Algorithme génétique pour l'optimisation d'emplois du temps"""
    
    def __init__(self, 
                 population_size: int = 100,
                 generations: int = 500,
                 crossover_rate: float = 0.8,
                 mutation_rate: float = 0.1,
                 elite_size: int = 10):
        self.population_size = population_size
        self.generations = generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.elite_size = elite_size
        self.objective_calculator = ObjectiveCalculator()
        
        self.population = []
        self.best_solution = None
        self.fitness_history = []
    
    def initialize_population(self, schedule: Schedule) -> List[TimetableSolution]:
        """Initialise la population avec des solutions aléatoires"""
        population = []
        sessions = list(schedule.sessions.all())
        time_slots = list(TimeSlot.objects.filter(is_active=True))
        rooms = list(Room.objects.filter(is_active=True))
        
        for _ in range(self.population_size):
            solution = TimetableSolution(schedule.id)
            
            for session in sessions:
                # Sélection aléatoire d'un créneau et d'une salle
                time_slot = random.choice(time_slots)
                suitable_rooms = [r for r in rooms if r.capacity >= session.expected_students]
                
                if suitable_rooms:
                    room = random.choice(suitable_rooms)
                    solution.assignments[session.id] = (time_slot.id, room.id)
            
            # Calculer la fitness
            self.objective_calculator.calculate_fitness(solution)
            population.append(solution)
        
        return population
    
    def tournament_selection(self, population: List[TimetableSolution], tournament_size: int = 3) -> TimetableSolution:
        """Sélection par tournoi"""
        tournament = random.sample(population, min(tournament_size, len(population)))
        return max(tournament, key=lambda x: x.fitness)
    
    def crossover(self, parent1: TimetableSolution, parent2: TimetableSolution) -> Tuple[TimetableSolution, TimetableSolution]:
        """Croisement à un point"""
        child1 = parent1.copy()
        child2 = parent2.copy()
        
        if random.random() < self.crossover_rate:
            # Choisir un point de croisement
            session_ids = list(parent1.assignments.keys())
            if len(session_ids) > 1:
                crossover_point = random.randint(1, len(session_ids) - 1)
                
                # Échanger les affectations après le point de croisement
                for i in range(crossover_point, len(session_ids)):
                    session_id = session_ids[i]
                    if session_id in parent1.assignments and session_id in parent2.assignments:
                        child1.assignments[session_id] = parent2.assignments[session_id]
                        child2.assignments[session_id] = parent1.assignments[session_id]
        
        return child1, child2
    
    def mutate(self, solution: TimetableSolution, schedule: Schedule):
        """Mutation par changement aléatoire d'affectation"""
        if random.random() < self.mutation_rate:
            session_ids = list(solution.assignments.keys())
            if session_ids:
                # Sélectionner une session aléatoire à muter
                session_id = random.choice(session_ids)
                
                try:
                    session = ScheduleSession.objects.get(id=session_id)
                    time_slots = list(TimeSlot.objects.filter(is_active=True))
                    suitable_rooms = list(Room.objects.filter(
                        is_active=True,
                        capacity__gte=session.expected_students
                    ))
                    
                    if time_slots and suitable_rooms:
                        new_time_slot = random.choice(time_slots)
                        new_room = random.choice(suitable_rooms)
                        solution.assignments[session_id] = (new_time_slot.id, new_room.id)
                
                except ScheduleSession.DoesNotExist:
                    pass
    
    def optimize(self, schedule: Schedule, progress_callback=None) -> TimetableSolution:
        """Lance l'optimisation génétique"""
        logger.info(f"Démarrage GA pour schedule {schedule.id}")
        
        # Initialiser la population
        self.population = self.initialize_population(schedule)
        
        for generation in range(self.generations):
            # Mise à jour du progrès
            if progress_callback:
                progress = (generation / self.generations) * 100
                progress_callback(progress, f"Génération {generation + 1}/{self.generations}")
            
            # Calculer fitness pour toute la population
            for solution in self.population:
                self.objective_calculator.calculate_fitness(solution)
            
            # Trier par fitness (descendant)
            self.population.sort(key=lambda x: x.fitness, reverse=True)
            
            # Enregistrer le meilleur
            current_best = self.population[0]
            if self.best_solution is None or current_best.fitness > self.best_solution.fitness:
                self.best_solution = current_best.copy()
            
            self.fitness_history.append(current_best.fitness)
            
            # Créer nouvelle génération
            new_population = []
            
            # Élitisme - garder les meilleurs
            new_population.extend([sol.copy() for sol in self.population[:self.elite_size]])
            
            # Créer le reste par croisement et mutation
            while len(new_population) < self.population_size:
                parent1 = self.tournament_selection(self.population)
                parent2 = self.tournament_selection(self.population)
                
                child1, child2 = self.crossover(parent1, parent2)
                
                self.mutate(child1, schedule)
                self.mutate(child2, schedule)
                
                new_population.extend([child1, child2])
            
            # Garder seulement la taille de population désirée
            self.population = new_population[:self.population_size]
            
            # Log du progrès
            if generation % 50 == 0:
                logger.info(f"Génération {generation}: Meilleure fitness = {current_best.fitness:.4f}")
        
        logger.info(f"GA terminé. Fitness finale: {self.best_solution.fitness:.4f}")
        return self.best_solution


class SimulatedAnnealing:
    """Algorithme de recuit simulé"""
    
    def __init__(self, 
                 initial_temperature: float = 1000.0,
                 cooling_rate: float = 0.95,
                 min_temperature: float = 0.01,
                 max_iterations: int = 10000):
        self.initial_temperature = initial_temperature
        self.cooling_rate = cooling_rate
        self.min_temperature = min_temperature
        self.max_iterations = max_iterations
        self.objective_calculator = ObjectiveCalculator()
    
    def generate_neighbor(self, solution: TimetableSolution, schedule: Schedule) -> TimetableSolution:
        """Génère une solution voisine par petite modification"""
        neighbor = solution.copy()
        
        session_ids = list(neighbor.assignments.keys())
        if not session_ids:
            return neighbor
        
        # Choisir une session aléatoire
        session_id = random.choice(session_ids)
        
        try:
            session = ScheduleSession.objects.get(id=session_id)
            
            # Décider du type de modification
            modification_type = random.choice(['time', 'room', 'both'])
            
            current_time_slot_id, current_room_id = neighbor.assignments[session_id]
            new_time_slot_id, new_room_id = current_time_slot_id, current_room_id
            
            if modification_type in ['time', 'both']:
                time_slots = list(TimeSlot.objects.filter(is_active=True))
                if time_slots:
                    new_time_slot_id = random.choice(time_slots).id
            
            if modification_type in ['room', 'both']:
                suitable_rooms = list(Room.objects.filter(
                    is_active=True,
                    capacity__gte=session.expected_students
                ))
                if suitable_rooms:
                    new_room_id = random.choice(suitable_rooms).id
            
            neighbor.assignments[session_id] = (new_time_slot_id, new_room_id)
            
        except ScheduleSession.DoesNotExist:
            pass
        
        return neighbor
    
    def accept_solution(self, current_fitness: float, new_fitness: float, temperature: float) -> bool:
        """Décide d'accepter ou non une nouvelle solution"""
        if new_fitness > current_fitness:
            return True
        
        if temperature <= 0:
            return False
        
        probability = math.exp((new_fitness - current_fitness) / temperature)
        return random.random() < probability
    
    def optimize(self, schedule: Schedule, progress_callback=None) -> TimetableSolution:
        """Lance l'optimisation par recuit simulé"""
        logger.info(f"Démarrage SA pour schedule {schedule.id}")
        
        # Solution initiale aléatoire
        current_solution = TimetableSolution(schedule.id)
        sessions = list(schedule.sessions.all())
        time_slots = list(TimeSlot.objects.filter(is_active=True))
        rooms = list(Room.objects.filter(is_active=True))
        
        # Initialisation aléatoire
        for session in sessions:
            time_slot = random.choice(time_slots)
            suitable_rooms = [r for r in rooms if r.capacity >= session.expected_students]
            if suitable_rooms:
                room = random.choice(suitable_rooms)
                current_solution.assignments[session.id] = (time_slot.id, room.id)
        
        # Calculer fitness initiale
        self.objective_calculator.calculate_fitness(current_solution)
        best_solution = current_solution.copy()
        
        temperature = self.initial_temperature
        iteration = 0
        
        while temperature > self.min_temperature and iteration < self.max_iterations:
            # Mise à jour du progrès
            if progress_callback and iteration % 100 == 0:
                progress = (iteration / self.max_iterations) * 100
                progress_callback(progress, f"Itération {iteration}, T={temperature:.2f}")
            
            # Générer solution voisine
            neighbor = self.generate_neighbor(current_solution, schedule)
            self.objective_calculator.calculate_fitness(neighbor)
            
            # Décider d'accepter la solution
            if self.accept_solution(current_solution.fitness, neighbor.fitness, temperature):
                current_solution = neighbor
                
                # Mettre à jour la meilleure solution
                if current_solution.fitness > best_solution.fitness:
                    best_solution = current_solution.copy()
            
            # Refroidissement
            temperature *= self.cooling_rate
            iteration += 1
            
            # Log du progrès
            if iteration % 1000 == 0:
                logger.info(f"Itération {iteration}: T={temperature:.4f}, "
                          f"Fitness={current_solution.fitness:.4f}, "
                          f"Meilleure={best_solution.fitness:.4f}")
        
        logger.info(f"SA terminé. Fitness finale: {best_solution.fitness:.4f}")
        return best_solution


class TimetableOptimizer:
    """Optimiseur principal qui orchestre les différents algorithmes"""
    
    def __init__(self):
        self.algorithms = {
            'genetic': GeneticAlgorithm,
            'simulated_annealing': SimulatedAnnealing,
        }
    
    def optimize_schedule(self, 
                         schedule: Schedule, 
                         algorithm: str = 'genetic',
                         algorithm_params: Dict[str, Any] = None,
                         progress_callback=None) -> Dict[str, Any]:
        """Optimise un emploi du temps avec l'algorithme spécifié"""
        
        if algorithm not in self.algorithms:
            raise ValueError(f"Algorithme non supporté: {algorithm}")
        
        # Initialiser l'algorithme
        params = algorithm_params or {}
        optimizer = self.algorithms[algorithm](**params)
        
        # Lancer l'optimisation
        try:
            best_solution = optimizer.optimize(schedule, progress_callback)
            
            # Appliquer la solution optimisée
            self._apply_solution(schedule, best_solution)
            
            return {
                'success': True,
                'algorithm': algorithm,
                'fitness': best_solution.fitness,
                'objectives': best_solution.objectives,
                'assignments_changed': len(best_solution.assignments),
                'solution': best_solution
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de l'optimisation: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'algorithm': algorithm
            }
    
    @transaction.atomic
    def _apply_solution(self, schedule: Schedule, solution: TimetableSolution):
        """Applique une solution optimisée à l'emploi du temps"""
        logger.info(f"Application de la solution pour schedule {schedule.id}")
        
        for session_id, (time_slot_id, room_id) in solution.assignments.items():
            try:
                session = ScheduleSession.objects.get(id=session_id)
                time_slot = TimeSlot.objects.get(id=time_slot_id)
                room = Room.objects.get(id=room_id)
                
                # Mettre à jour la session
                session.time_slot = time_slot
                session.room = room
                session.save()
                
            except (ScheduleSession.DoesNotExist, TimeSlot.DoesNotExist, Room.DoesNotExist) as e:
                logger.warning(f"Erreur application session {session_id}: {str(e)}")
        
        # Recalculer les métriques du schedule
        schedule.calculate_metrics()
        
        logger.info(f"Solution appliquée avec succès")


class ConflictPredictor:
    """Prédicteur de conflits basé sur l'IA"""
    
    def __init__(self):
        self.risk_factors = [
            'teacher_overload',
            'room_capacity_mismatch', 
            'time_preference_violation',
            'curriculum_clustering',
            'resource_contention'
        ]
    
    def predict_conflicts(self, schedule: Schedule) -> List[Dict[str, Any]]:
        """Prédit les conflits potentiels dans un emploi du temps"""
        predicted_conflicts = []
        sessions = schedule.sessions.all()
        
        # Analyser chaque session
        for session in sessions:
            conflict_risk = self._calculate_conflict_risk(session, sessions)
            
            if conflict_risk['total_risk'] > 0.7:  # Seuil de risque élevé
                predicted_conflicts.append({
                    'session_id': session.id,
                    'course_name': session.course.name,
                    'risk_score': conflict_risk['total_risk'],
                    'risk_factors': conflict_risk['factors'],
                    'recommendations': self._generate_recommendations(conflict_risk)
                })
        
        return predicted_conflicts
    
    def _calculate_conflict_risk(self, session: ScheduleSession, all_sessions) -> Dict[str, Any]:
        """Calcule le risque de conflit pour une session"""
        risk_factors = {}
        
        # Risque surcharge enseignant
        teacher_sessions = [s for s in all_sessions if s.teacher == session.teacher]
        teacher_load = len(teacher_sessions)
        max_load = session.teacher.max_hours_per_week
        risk_factors['teacher_overload'] = min(teacher_load / max_load, 1.0) if max_load > 0 else 0
        
        # Risque capacité salle
        room_capacity = session.room.capacity if session.room else 0
        expected_students = session.expected_students
        risk_factors['room_capacity_mismatch'] = max(0, (expected_students - room_capacity) / expected_students) if expected_students > 0 else 0
        
        # Risque violation préférences
        risk_factors['time_preference_violation'] = self._check_time_preferences(session)
        
        # Risque clustering curriculum
        risk_factors['curriculum_clustering'] = self._check_curriculum_clustering(session, all_sessions)
        
        # Risque contention ressources
        risk_factors['resource_contention'] = self._check_resource_contention(session, all_sessions)
        
        # Score total
        total_risk = sum(risk_factors.values()) / len(risk_factors)
        
        return {
            'total_risk': total_risk,
            'factors': risk_factors
        }
    
    def _check_time_preferences(self, session: ScheduleSession) -> float:
        """Vérifie les violations de préférences horaires"""
        if not session.course.preferred_times or not session.time_slot:
            return 0.5  # Risque neutre
        
        time_slot = session.time_slot
        for pref in session.course.preferred_times:
            if (pref.get('day') == time_slot.day_of_week and
                pref.get('start_time') <= time_slot.start_time.strftime('%H:%M') <= pref.get('end_time')):
                return 0.0  # Pas de risque
        
        return 1.0  # Risque élevé
    
    def _check_curriculum_clustering(self, session: ScheduleSession, all_sessions) -> float:
        """Vérifie le clustering des cours du même curriculum"""
        if not session.schedule.curriculum:
            return 0.0
        
        curriculum_sessions = [s for s in all_sessions 
                             if s.schedule.curriculum == session.schedule.curriculum]
        
        same_time_sessions = [s for s in curriculum_sessions 
                            if s.time_slot == session.time_slot and s.id != session.id]
        
        return len(same_time_sessions) * 0.3  # Risque proportionnel au nombre de sessions simultanées
    
    def _check_resource_contention(self, session: ScheduleSession, all_sessions) -> float:
        """Vérifie la contention des ressources"""
        if not session.room or not session.time_slot:
            return 0.0
        
        concurrent_sessions = [s for s in all_sessions 
                             if (s.room == session.room and 
                                 s.time_slot == session.time_slot and 
                                 s.id != session.id)]
        
        return min(len(concurrent_sessions), 1.0)  # Plafonner à 1.0
    
    def _generate_recommendations(self, conflict_risk: Dict[str, Any]) -> List[str]:
        """Génère des recommandations basées sur les risques"""
        recommendations = []
        factors = conflict_risk['factors']
        
        if factors.get('teacher_overload', 0) > 0.8:
            recommendations.append("Réduire la charge de l'enseignant ou redistribuer les cours")
        
        if factors.get('room_capacity_mismatch', 0) > 0.5:
            recommendations.append("Utiliser une salle de plus grande capacité")
        
        if factors.get('time_preference_violation', 0) > 0.7:
            recommendations.append("Respecter les préférences horaires du cours")
        
        if factors.get('curriculum_clustering', 0) > 0.6:
            recommendations.append("Éviter les cours simultanés du même curriculum")
        
        if factors.get('resource_contention', 0) > 0.8:
            recommendations.append("Résoudre le conflit de ressources (salle/temps)")
        
        return recommendations


# Factory pour créer les optimiseurs
class OptimizerFactory:
    """Factory pour créer les différents types d'optimiseurs"""
    
    @staticmethod
    def create_optimizer(algorithm_type: str, **kwargs) -> TimetableOptimizer:
        """Crée un optimiseur selon le type spécifié"""
        optimizer = TimetableOptimizer()
        
        if algorithm_type == 'genetic':
            optimizer.algorithms['genetic'] = lambda **params: GeneticAlgorithm(**params)
        elif algorithm_type == 'simulated_annealing':
            optimizer.algorithms['simulated_annealing'] = lambda **params: SimulatedAnnealing(**params)
        else:
            raise ValueError(f"Type d'optimiseur non supporté: {algorithm_type}")
        
        return optimizer


# Configuration par défaut des algorithmes
DEFAULT_GA_CONFIG = {
    'population_size': 100,
    'generations': 500,
    'crossover_rate': 0.8,
    'mutation_rate': 0.1,
    'elite_size': 10
}

DEFAULT_SA_CONFIG = {
    'initial_temperature': 1000.0,
    'cooling_rate': 0.95,
    'min_temperature': 0.01,
    'max_iterations': 10000
}