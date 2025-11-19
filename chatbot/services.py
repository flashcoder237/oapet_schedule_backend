"""
Services pour le chatbot intelligent OAPET
"""
import re
from datetime import datetime, timedelta
from django.db.models import Q, Count, Avg
from django.utils import timezone
from courses.models import Course, Teacher, Department
from schedules.models import Schedule, ScheduleSession
from rooms.models import Room
from .models import ChatbotKnowledge, Conversation
from .agent_service import AgentActionService
from difflib import SequenceMatcher
import spacy
from rapidfuzz import fuzz, process
import random


class ChatbotService:
    """Service principal du chatbot avec IA avancée"""

    def __init__(self):
        # Mémoire contextuelle pour les conversations
        self.context = {}

        # Charger le modèle spaCy français (lazy loading)
        self.nlp = None
        try:
            self.nlp = spacy.load('fr_core_news_md')
            print("[ChatbotService] Modèle spaCy chargé avec succès")
        except Exception as e:
            print(f"[ChatbotService] Erreur chargement spaCy: {e}. Utilisation mode basique.")

        # Templates de réponses personnalisées et chaleureuses
        self.response_templates = {
            'greeting': [
                "Bonjour {name} ! 😊 Ravi de vous revoir ! Comment puis-je vous aider aujourd'hui ?",
                "Salut {name} ! 👋 Prêt à optimiser votre emploi du temps ?",
                "Hello {name} ! Je suis là pour vous faciliter la vie. Que puis-je faire pour vous ?",
                "Bonjour ! Content de vous voir {name} ! Dites-moi ce dont vous avez besoin.",
            ],
            'success': [
                "Parfait ! ✅ C'est fait. {message}",
                "Super ! 🎉 {message}",
                "Excellent ! {message} Besoin d'autre chose ?",
                "Voilà ! ✨ {message} Je reste à votre disposition.",
            ],
            'help_offer': [
                "\n\n💡 Astuce : {tip}",
                "\n\n🔍 Le saviez-vous ? {tip}",
                "\n\nℹ️ Info utile : {tip}",
            ],
            'error': [
                "Oups ! 😅 {message} Laissez-moi vous aider autrement.",
                "Désolé, {message} Voulez-vous que je vous montre ce que je peux faire ?",
                "Hmm... {message} Pas de souci, on va trouver une solution ensemble !",
            ],
            'encouragement': [
                "Vous vous en sortez très bien ! 👏",
                "Parfait, continuons ! 💪",
                "Génial, vous maîtrisez ! 🌟",
            ]
        }

        # Conseils et astuces contextuels
        self.contextual_tips = {
            'schedule': [
                "Vous pouvez dire 'L1MED' pour afficher directement une classe",
                "Essayez 'semaine' pour changer rapidement de vue",
                "Tapez 'stats' pour voir les statistiques en un clin d'œil",
            ],
            'generation': [
                "La génération automatique optimise les conflits d'horaires",
                "Je peux générer des emplois du temps pour plusieurs classes en même temps",
                "L'IA s'assure de respecter les disponibilités des enseignants",
            ],
            'navigation': [
                "Je peux vous emmener directement sur n'importe quelle page",
                "Dites simplement le nom de la page où vous voulez aller",
                "Vous pouvez me demander d'effectuer des actions sans naviguer manuellement",
            ]
        }

        self.intents = {
            'schedule': {
                'keywords': ['emploi', 'planning', 'horaire', 'programme', 'cours', 'session', 'quand', 'aujourd\'hui', 'demain', 'semaine', 'prochain', 'edt', 'agenda'],
                'patterns': [
                    r'emploi.*temps',
                    r'(mon|mes|notre|l\')\s+(?:emploi|planning|edt|horaire)',
                    r'(mon|mes)\s+cours',
                    r'quand.*cours',
                    r'planning.*(?:jour|semaine|mois)',
                    r'prochaine?\s+(?:cours|session)',
                    r'(?:voir|consulter|afficher)\s+(?:l\')?(?:emploi|edt|planning)',
                    r'j\'ai\s+(?:quoi|cours)',
                    r'(?:que|quoi)\s+(?:aujourd\'hui|demain|cette\s+semaine)',
                ],
                'actions': ['view_schedule', 'find_next_class']
            },
            'course': {
                'keywords': ['cours', 'matière', 'module', 'enseignement', 'crédit', 'heures', 'leçon'],
                'patterns': [
                    r'(?:quel|quels|quelles)\s+cours',
                    r'cours.*(?:disponible|offert)',
                    r'information.*cours',
                ]
            },
            'room': {
                'keywords': ['salle', 'local', 'amphithéâtre', 'amphitheatre', 'classe', 'bâtiment', 'lieu', 'où'],
                'patterns': [
                    r'(?:où|ou)\s+(?:se trouve|est|trouver)',
                    r'salle.*(?:disponible|libre)',
                    r'capacité.*salle',
                ]
            },
            'teacher': {
                'keywords': ['professeur', 'enseignant', 'prof', 'instructeur', 'docteur', 'dr'],
                'patterns': [
                    r'(?:prof|professeur|enseignant).*(?:contact|email|téléphone)',
                    r'qui\s+enseigne',
                    r'contact.*(?:prof|professeur)',
                ]
            },
            'conflict': {
                'keywords': ['conflit', 'chevauchement', 'collision', 'problème', 'erreur', 'incompatible'],
                'patterns': [
                    r'conflit.*(?:emploi|planning|horaire)',
                    r'(?:cours|session).*(?:même.*temps|simultané)',
                ]
            },
            'availability': {
                'keywords': ['disponible', 'disponibilité', 'libre', 'occupé', 'réserver'],
                'patterns': [
                    r'(?:salle|prof).*disponible',
                    r'(?:qui|quand).*(?:libre|disponible)',
                ]
            },
            'statistics': {
                'keywords': ['statistique', 'nombre', 'combien', 'total', 'moyenne'],
                'patterns': [
                    r'combien\s+de\s+(?:cours|salles|professeurs)',
                    r'(?:nombre|total).*(?:cours|session)',
                ]
            },
            'help': {
                'keywords': ['aide', 'comment', 'qui', 'quoi', 'où', 'quand', 'pourquoi', 'help', 'info'],
                'patterns': [
                    r'comment.*(?:faire|utiliser|fonction)',
                    r'(?:qu\'est|c\'est\s+quoi)',
                ]
            },
            'greeting': {
                'keywords': ['bonjour', 'salut', 'hello', 'bonsoir', 'hey', 'hi', 'coucou', 'bjr', 'slt', 'yo'],
                'patterns': [
                    r'^(?:bonjour|salut|hello|hey|hi|bonsoir|coucou|bjr|slt|yo)',
                    r'(?:bonjour|salut|hello|hey|hi|bonsoir|coucou)\s+(?:assistant|chatbot|bot)',
                    r'comment\s+(?:vas?|allez?[\s-]vous|tu\s+vas)',
                    r'(?:ca|ça)\s+va\s*\??',
                ]
            },
            'thanks': {
                'keywords': ['merci', 'thank', 'remercie'],
                'patterns': [
                    r'merci(?:\s+beaucoup)?',
                    r'je\s+(?:te|vous)\s+remercie',
                ]
            },
            'create': {
                'keywords': ['creer', 'ajouter', 'nouveau', 'nouvelle', 'inscrire', 'enregistrer'],
                'patterns': [
                    r'(?:creer|ajouter|nouveau)\s+(?:cours|salle|enseignant|etudiant)',
                    r'(?:inscrire|enregistrer)\s+un',
                ]
            },
            'modify': {
                'keywords': ['modifier', 'changer', 'mettre a jour', 'editer', 'corriger'],
                'patterns': [
                    r'modifier.*(?:cours|salle|horaire)',
                    r'changer.*(?:date|heure|salle)',
                ]
            },
            'delete': {
                'keywords': ['supprimer', 'effacer', 'retirer', 'annuler'],
                'patterns': [
                    r'supprimer.*(?:cours|session)',
                    r'annuler.*(?:cours|reservation)',
                ]
            },
            'search': {
                'keywords': ['chercher', 'trouver', 'rechercher', 'localiser'],
                'patterns': [
                    r'(?:chercher|trouver|rechercher)\s+(?:cours|salle|prof)',
                    r'ou\s+(?:se trouve|est|trouver)',
                ]
            },
            'recommendation': {
                'keywords': ['suggerer', 'proposer', 'recommander', 'meilleur', 'optimal'],
                'patterns': [
                    r'(?:suggerer|proposer|recommander)\s+',
                    r'(?:meilleur|optimal).*(?:horaire|planning)',
                ]
            },
            'export': {
                'keywords': ['exporter', 'telecharger', 'extraire', 'sauvegarder'],
                'patterns': [
                    r'exporter.*(?:emploi|planning|donnees)',
                    r'telecharger.*(?:csv|excel|pdf)',
                ]
            },
            'generate_schedule': {
                'keywords': ['generer', 'générer', 'generation', 'génération', 'creer', 'créer', 'faire', 'nouveau', 'automatique', 'ia', 'automatiquement', 'planifier', 'construire'],
                'patterns': [
                    r'g[ée]n[ée]rer?\s+(?:un\s+)?(?:nouvel\s+)?emploi\s+du\s+temps',
                    r'cr[ée]er?\s+(?:un\s+)?(?:nouvel\s+)?emploi\s+du\s+temps',
                    r'faire\s+(?:un\s+)?(?:nouvel\s+)?emploi\s+du\s+temps',
                    r'(?:nouveau|nouvel)\s+emploi\s+du\s+temps',
                    r'g[ée]n[ée]ration.*(?:automatique|ia|intelligente|emploi)',
                    r'(?:planifier|construire)\s+(?:automatiquement|un\s+emploi)',
                    r'(?:je\s+veux|veux)\s+(?:g[ée]n[ée]rer|cr[ée]er|faire)\s+(?:un\s+)?emploi',
                    r'(?:peux[\s-]tu|pouvez[\s-]vous)\s+(?:g[ée]n[ée]rer|cr[ée]er)',
                    # Formulations directes
                    r'^g[ée]n[ée]rer?$',
                    r'^(?:g[ée]n[ée]ration|cr[ée]ation)\s+(?:emploi|edt)$',
                ]
            },
            'detect_conflicts': {
                'keywords': ['detecter', 'détecter', 'verifier', 'vérifier', 'conflit', 'probleme', 'problème', 'chevauchement'],
                'patterns': [
                    r'd[ée]tecter?\s+(?:les\s+)?conflits?',
                    r'v[ée]rifier?\s+(?:les\s+)?conflits?',
                    r'y\s+a[- ]t[- ]il\s+(?:des\s+)?conflits?',
                    r'rechercher?\s+(?:les\s+)?(?:problemes?|probl[èe]mes?)',
                ]
            },
            'evaluate_quality': {
                'keywords': ['evaluer', 'évaluer', 'evaluation', 'évaluation', 'qualite', 'qualité', 'score', 'note'],
                'patterns': [
                    r'[ée]valuer?\s+(?:la\s+)?qualit[ée]',
                    r'(?:quel|quelle)\s+(?:est\s+le\s+)?(?:score|note|qualit[ée])',
                    r'analyser?\s+(?:l\')?emploi\s+du\s+temps',
                ]
            },
            'cancel_occurrence': {
                'keywords': ['annuler', 'annule', 'annulé', 'annulation', 'supprimer', 'cours', 'seance', 'séance', 'pas', 'sauter'],
                'patterns': [
                    r'annuler?\s+(?:le\s+)?(?:cours|seance|s[ée]ance|session)',
                    r'supprimer?\s+(?:le\s+)?(?:cours|seance|s[ée]ance|session)',
                    r'ne\s+pas\s+avoir\s+(?:le\s+|de\s+)?cours',
                    r'(?:pas|plus)\s+de\s+cours',
                    r'(?:sauter|[ée]viter)\s+(?:le\s+)?cours',
                    r'(?:je\s+veux|veux)\s+annuler',
                    r'(?:supprimer|retirer|enlever)\s+(?:le\s+)?cours',
                    # Formulations directes
                    r'^annuler?$',
                    r'^(?:pas|plus)\s+cours$',
                ]
            },
            'reschedule_occurrence': {
                'keywords': ['reprogrammer', 'reprogramme', 'deplacer', 'déplacer', 'changer', 'date', 'heure', 'reporter', 'décaler', 'decaler'],
                'patterns': [
                    r'reprogrammer?\s+(?:le\s+)?(?:cours|seance|s[ée]ance|session)',
                    r'd[ée]placer?\s+(?:le\s+)?(?:cours|seance|s[ée]ance|session)',
                    r'(?:changer|modifier)\s+(?:l\'|la\s+)?(?:heure|date)\s+(?:du\s+)?cours',
                    r'(?:mettre|passer|reporter)\s+(?:le\s+)?cours\s+(?:au|à|a|le)',
                    r'd[ée]caler?\s+(?:le\s+)?cours',
                    r'(?:je\s+veux|veux)\s+(?:reprogrammer|d[ée]placer|reporter)',
                    r'(?:bouger|transf[ée]rer)\s+(?:le\s+)?cours',
                    # Formulations directes
                    r'^(?:reprogrammer|d[ée]placer|reporter)$',
                ]
            },
            'modify_occurrence': {
                'keywords': ['modifier', 'modifie', 'modifié', 'changer', 'changé', 'salle', 'enseignant', 'prof', 'professeur', 'remplacer'],
                'patterns': [
                    r'modifier?\s+(?:la\s+)?salle',
                    r'changer?\s+(?:de\s+)?salle',
                    r'(?:changer|modifier)\s+(?:d\'|l\'|le\s+)?enseignant',
                    r'remplacer?\s+(?:le\s+|l\')?(?:prof|enseignant|professeur)',
                    r'(?:je\s+veux|veux)\s+(?:modifier|changer)',
                    r'(?:autre|nouvelle)\s+salle',
                    r'(?:autre|nouveau)\s+(?:prof|enseignant)',
                    # Formulations directes
                    r'^modifier?$',
                    r'^changer?$',
                ]
            },
            'list_occurrences': {
                'keywords': ['lister', 'liste', 'afficher', 'voir', 'annule', 'annulé', 'modifie', 'modifié', 'cours', 'montrer', 'quels', 'quelles'],
                'patterns': [
                    r'(?:lister?|voir|afficher|montrer)\s+(?:les\s+)?cours\s+annul[ée]s',
                    r'(?:lister?|voir|afficher|montrer)\s+(?:les\s+)?cours\s+modifi[ée]s',
                    r'(?:quels?|quelles?)\s+cours\s+(?:sont\s+)?annul[ée]s',
                    r'(?:quels?|quelles?)\s+cours\s+(?:ont\s+[ée]t[ée]\s+)?modifi[ée]s',
                    r'(?:montre|donne)[\s-]moi\s+(?:les\s+)?cours\s+(?:annul[ée]s|modifi[ée]s)',
                    r'(?:y\s+a[- ]t[- ]il|il\s+y\s+a)\s+(?:des\s+)?cours\s+(?:annul[ée]s|modifi[ée]s)',
                    r'(?:liste|historique)\s+(?:des\s+)?(?:annulations|modifications)',
                    # Formulations directes
                    r'^(?:annul[ée]s|modifi[ée]s)$',
                    r'^liste\s+cours$',
                ]
            },
            # Intentions de navigation et contrôle UI
            'navigate_to_schedule': {
                'keywords': ['aller', 'va', 'vas', 'ouvrir', 'ouvre', 'afficher', 'affiche', 'page', 'emploi', 'planning', 'edt', 'voir', 'acceder', 'accéder'],
                'patterns': [
                    r'(?:aller?|vas?)\s+(?:sur|à|a|vers)\s+(?:la\s+page\s+)?(?:emploi|planning|edt)',
                    r'ouvrir?\s+(?:la\s+page\s+)?(?:emploi|planning|edt)',
                    r'afficher?\s+(?:la\s+page\s+)?(?:emploi|planning|edt)',
                    r'(?:montre|montrer)\s+(?:moi\s+)?(?:l\'|le\s+)?(?:emploi|planning|edt)',
                    r'(?:voir|consulter|acc[ée]der)\s+(?:à\s+|a\s+)?(?:l\'|le\s+)?(?:emploi|planning|edt)',
                    r'(?:page|interface)\s+(?:emploi|planning|edt)',
                    r'(?:emmene|emmène|am[èe]ne)[\s-]moi\s+(?:sur|à|a)\s+(?:l\')?(?:emploi|planning)',
                ]
            },
            'select_class': {
                'keywords': ['selectionner', 'sélectionner', 'choisir', 'classe', 'afficher', 'voir', 'montre', 'montrer', 'prendre'],
                'patterns': [
                    r's[ée]lectionner?\s+(?:la\s+)?classe\s+([A-Z0-9]+)',
                    r'choisir?\s+(?:la\s+)?classe\s+([A-Z0-9]+)',
                    r'afficher?\s+(?:la\s+)?classe\s+([A-Z0-9]+)',
                    r'voir\s+(?:l\'emploi\s+(?:de\s+)?)?(?:la\s+)?classe\s+([A-Z0-9]+)',
                    r'(?:montre|montrer)\s+(?:moi\s+)?(?:la\s+)?classe\s+([A-Z0-9]+)',
                    r'(?:prendre|prends)\s+(?:la\s+)?classe\s+([A-Z0-9]+)',
                    # Formulations directes sans mot "classe"
                    r'(?:afficher?|voir|montre|s[ée]lectionner?)\s+([A-Z][0-9][A-Z]+)',
                    r'^([A-Z][0-9][A-Z0-9]+)$',  # Juste le code de classe (ex: L1MED)
                    r'(?:je\s+veux|donne[\s-]moi)\s+(?:la\s+)?classe\s+([A-Z0-9]+)',
                    r'(?:emploi|edt|planning)\s+(?:de\s+)?(?:la\s+)?classe\s+([A-Z0-9]+)',
                ]
            },
            'change_view_mode': {
                'keywords': ['vue', 'mode', 'affichage', 'jour', 'semaine', 'mois', 'passer', 'journee', 'journée', 'hebdo', 'mensuel'],
                'patterns': [
                    r'(?:passer|changer|mettre|passe)\s+en\s+(?:vue\s+)?(?:jour|semaine|mois|journ[ée]e|hebdo|mensuel)',
                    r'afficher?\s+(?:en\s+)?(?:vue\s+)?(?:par\s+)?(?:jour|semaine|mois|journ[ée]e)',
                    r'(?:mode|vue)\s+(?:jour|semaine|mois|journ[ée]e|hebdo|mensuel)',
                    r'(?:voir|afficher)\s+(?:par\s+)?(?:jour|semaine|mois)',
                    r'(?:vue|affichage)\s+(?:de\s+(?:la\s+)?)?(?:journ[ée]e|semaine|mois)',
                    # Formulations directes
                    r'^(?:jour|semaine|mois)$',
                    r'(?:montre|affiche)[\s-]moi\s+(?:la\s+)?(?:semaine|le\s+jour|le\s+mois)',
                ]
            },
            'filter_sessions': {
                'keywords': ['filtrer', 'filtre', 'afficher', 'voir', 'seulement', 'uniquement', 'cm', 'td', 'tp', 'tpe', 'exam', 'cours', 'magistral', 'dirigés', 'pratiques'],
                'patterns': [
                    r'filtrer?\s+(?:par\s+)?(?:les\s+)?(?:cours\s+)?(?:de\s+)?(?:cm|td|tp|tpe|exams?)',
                    r'afficher?\s+(?:seulement|uniquement|que)\s+(?:les\s+)?(?:cm|td|tp|tpe|exams?)',
                    r'voir\s+(?:que|seulement|uniquement)\s+(?:les\s+)?(?:cm|td|tp|tpe|exams?)',
                    r'(?:montre|montrer)[\s-]moi\s+(?:que|seulement)\s+(?:les\s+)?(?:cm|td|tp|tpe|exams?)',
                    r'(?:juste|seulement|uniquement)\s+(?:les\s+)?(?:cm|td|tp|tpe|exams?)',
                    # Formulations directes
                    r'^(?:cm|td|tp|tpe|exams?)$',
                    r'filtre\s+(?:cm|td|tp|tpe|exams?)',
                    r'(?:cours\s+)?magistr(?:al|aux)',  # Cours magistral = CM
                    r'(?:cours\s+)?(?:travaux\s+)?dirig[ée]s',  # Travaux dirigés = TD
                    r'(?:cours\s+)?(?:travaux\s+)?pratiques',  # Travaux pratiques = TP
                ]
            },
            'show_statistics': {
                'keywords': ['statistiques', 'stats', 'afficher', 'voir', 'montrer', 'panel', 'données', 'chiffres', 'infos', 'informations'],
                'patterns': [
                    r'(?:afficher?|voir|montrer)\s+(?:les\s+)?statistiques?',
                    r'(?:afficher?|voir|montrer)\s+(?:les\s+)?stats',
                    r'ouvrir?\s+(?:le\s+)?panel\s+(?:des\s+)?stats',
                    r'(?:montre|donne)[\s-]moi\s+(?:les\s+)?(?:statistiques?|stats|donn[ée]es|chiffres)',
                    r'(?:je\s+veux|voir)\s+(?:les\s+)?(?:statistiques?|stats|infos)',
                    # Formulations directes
                    r'^stats?$',
                    r'^statistiques?$',
                ]
            },
            'toggle_edit_mode': {
                'keywords': ['mode', 'édition', 'edition', 'editer', 'modifier', 'activer', 'desactiver', 'désactiver', 'drag', 'déplacer'],
                'patterns': [
                    r'(?:activer|d[ée]sactiver|passer\s+en|mettre)\s+mode\s+[ée]dition',
                    r'(?:activer|d[ée]sactiver|allumer|[ée]teindre)\s+(?:l\'|le\s+)?[ée]dition',
                    r'mode\s+(?:drag|d[ée]placer|d[ée]placement)',
                    r'(?:je\s+veux|veux)\s+(?:[ée]diter|modifier)',
                    r'(?:activer|allumer)\s+(?:le\s+mode\s+)?drag',
                    # Formulations directes
                    r'^[ée]dition$',
                    r'^(?:mode\s+)?drag$',
                ]
            },
            'create_session': {
                'keywords': ['créer', 'creer', 'ajouter', 'nouvelle', 'nouveau', 'session', 'cours', 'planifier', 'programmer'],
                'patterns': [
                    r'cr[ée]er?\s+(?:une\s+)?(?:nouvelle\s+)?session',
                    r'ajouter?\s+(?:une\s+)?(?:nouvelle\s+)?session',
                    r'cr[ée]er?\s+(?:un\s+)?(?:nouveau\s+)?cours',
                    r'(?:nouveau|nouvelle)\s+(?:cours|session)',
                    r'(?:planifier|programmer)\s+(?:un\s+)?(?:nouveau\s+)?cours',
                    r'(?:je\s+veux|veux)\s+(?:cr[ée]er|ajouter|planifier)\s+(?:un\s+)?cours',
                    r'(?:ouvrir|afficher)\s+(?:le\s+)?formulaire',
                    # Formulations directes
                    r'^nouveau$',
                    r'^(?:cr[ée]er|ajouter)$',
                ]
            },
            'export_schedule': {
                'keywords': ['exporter', 'télécharger', 'telecharger', 'excel', 'pdf', 'csv', 'extraire', 'sauvegarder', 'enregistrer'],
                'patterns': [
                    r'exporter?\s+(?:l\'|le\s+)?(?:emploi|planning|edt)',
                    r't[ée]l[ée]charger?\s+(?:l\'|le\s+)?(?:emploi|planning|edt)',
                    r'exporter?\s+en\s+(?:excel|pdf|csv)',
                    r't[ée]l[ée]charger?\s+(?:en\s+)?(?:excel|pdf|csv)',
                    r'(?:sauvegarder|enregistrer)\s+(?:l\'|le\s+)?(?:emploi|planning|edt)',
                    r'(?:extraire|exporter)\s+(?:les\s+)?donn[ée]es',
                    r'(?:donne|envoie)[\s-]moi\s+(?:l\'|le\s+)?(?:emploi|planning)\s+en\s+(?:excel|pdf|csv)',
                    # Formulations directes avec format
                    r'(?:excel|pdf|csv)$',
                ]
            },
        }

    def detect_intent(self, message):
        """Détecte l'intention de l'utilisateur avec NLP amélioré (spaCy + rapidfuzz)"""
        message_lower = message.lower()
        message_words = message_lower.split()

        intent_scores = {}

        # Traiter le message avec spaCy si disponible
        doc = None
        if self.nlp:
            try:
                doc = self.nlp(message_lower)
            except:
                pass

        for intent, data in self.intents.items():
            score = 0

            # 1. Score basé sur les mots-clés (avec fuzzy matching)
            keywords = data.get('keywords', [])
            for keyword in keywords:
                # Utiliser rapidfuzz pour fuzzy matching
                best_match = process.extractOne(
                    keyword,
                    message_words,
                    scorer=fuzz.ratio,
                    score_cutoff=80
                )
                if best_match:
                    # Score proportionnel à la similarité
                    score += (best_match[1] / 100) * 2.5

            # 2. Score basé sur les patterns regex (priorité haute)
            patterns = data.get('patterns', [])
            for pattern in patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    score += 5  # Augmenté de 3 à 5 pour donner plus de poids aux patterns

            # 3. Score de similarité sémantique avec spaCy
            if doc and self.nlp:
                try:
                    # Créer une phrase représentative de l'intention
                    intent_phrase = ' '.join(keywords[:5])  # Prendre les 5 premiers mots-clés
                    intent_doc = self.nlp(intent_phrase)

                    # Calculer la similarité sémantique
                    similarity = doc.similarity(intent_doc)
                    if similarity > 0.5:  # Seuil de similarité
                        score += similarity * 3  # Bonus pour similarité sémantique
                except:
                    pass

            # 4. Bonus pour les mots-clés exacts dans le message
            exact_matches = sum(1 for keyword in keywords if keyword in message_lower)
            score += exact_matches * 1.5

            if score > 0:
                intent_scores[intent] = score

        if intent_scores:
            detected_intent = max(intent_scores, key=intent_scores.get)
            max_score = intent_scores[detected_intent]

            # Calculer la confiance normalisée
            total_score = sum(intent_scores.values())
            confidence = min((max_score / total_score) * 100, 99)

            # Logs pour debug
            print(f"[NLP] Message: '{message}' -> Intent: '{detected_intent}' (confiance: {confidence:.1f}%)")
            print(f"[NLP] Scores: {sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)[:3]}")

            return detected_intent, confidence

        return 'unknown', 0.0

    def get_personalized_response(self, template_type, user=None, **kwargs):
        """Génère une réponse personnalisée et chaleureuse"""
        templates = self.response_templates.get(template_type, ["{message}"])
        template = random.choice(templates)

        # Ajouter le nom de l'utilisateur si disponible
        if user:
            kwargs['name'] = user.get_full_name() or user.username

        return template.format(**kwargs)

    def add_contextual_tip(self, response, intent_category):
        """Ajoute un conseil contextuel à la réponse"""
        tips = self.contextual_tips.get(intent_category, [])
        if tips and random.random() < 0.3:  # 30% de chance d'ajouter un conseil
            tip = random.choice(tips)
            tip_template = random.choice(self.response_templates['help_offer'])
            response += tip_template.format(tip=tip)
        return response

    def get_smart_suggestions(self, intent, user_context):
        """Génère des suggestions intelligentes basées sur le contexte"""
        suggestions = []

        # Suggestions basées sur l'intention
        if intent == 'schedule':
            suggestions = [
                "Afficher une classe spécifique",
                "Voir les statistiques",
                "Changer la vue (jour/semaine/mois)",
            ]
        elif intent == 'generate_schedule':
            suggestions = [
                "Détecter les conflits d'abord",
                "Évaluer la qualité de l'emploi actuel",
                "Générer pour toutes les classes",
            ]
        elif intent in ['navigate_to_schedule', 'select_class']:
            suggestions = [
                "Filtrer par type de cours (CM/TD/TP)",
                "Activer le mode édition",
                "Exporter l'emploi du temps",
            ]
        elif intent == 'greeting':
            suggestions = [
                "Voir l'emploi du temps",
                "Générer un nouvel emploi",
                "Gérer les cours annulés",
            ]

        return suggestions[:3]  # Max 3 suggestions

    def format_helpful_error(self, error_message, intent=None):
        """Formate un message d'erreur de manière utile"""
        response = self.get_personalized_response('error', message=error_message)

        # Ajouter des suggestions si une intention était détectée
        if intent and intent != 'unknown':
            response += "\n\n🤔 Peut-être vouliez-vous :\n"
            suggestions = self.get_smart_suggestions(intent, {})
            for i, suggestion in enumerate(suggestions, 1):
                response += f"{i}. {suggestion}\n"

        return response

    def process_message(self, message, user, conversation=None):
        """Traite le message et génère une réponse avec contexte et actions agent"""
        message_lower = message.lower()

        # Gérer le contexte de la conversation
        user_context = self.context.get(user.id, {})

        # Initialiser le service d'agent pour cet utilisateur
        agent_service = AgentActionService(user)

        # === GESTION DES ACTIONS AGENT ===

        # Verifier si l'utilisateur repond a une demande de confirmation
        pending_action = user_context.get('pending_action')
        if pending_action:
            # L'utilisateur confirme ou annule
            if any(word in message_lower for word in ['oui', 'ok', 'confirme', 'confirmer', 'valide', 'valider', 'oui']):
                # Executer l'action en attente
                success, response_message, data = agent_service.execute_action(
                    pending_action['action_name'],
                    pending_action['params'],
                    conversation
                )

                # Nettoyer le contexte
                user_context.pop('pending_action', None)
                self.context[user.id] = user_context

                return {
                    'response': response_message,
                    'intent': 'agent_action',
                    'confidence': 100,
                    'context_data': {'action_executed': success, 'action_name': pending_action['action_name']},
                    'attachments': []
                }
            elif any(word in message_lower for word in ['non', 'annule', 'annuler', 'stop', 'pas']):
                # Annuler l'action
                user_context.pop('pending_action', None)
                self.context[user.id] = user_context

                return {
                    'response': "Action annulee. Comment puis-je vous aider autrement ?",
                    'intent': 'agent_action_cancel',
                    'confidence': 100,
                    'context_data': {},
                    'attachments': []
                }

        # Verifier si l'utilisateur complete des parametres manquants
        if user_context.get('awaiting_params'):
            awaiting_info = user_context['awaiting_params']
            action_name = awaiting_info['action_name']
            current_params = awaiting_info['params']

            # Extraire les nouveaux parametres du message
            new_params = agent_service.extract_parameters(message, action_name)

            # Fusionner avec les parametres existants
            current_params.update(new_params)

            # Verifier si tous les parametres sont maintenant presents
            missing = agent_service.get_missing_parameters(action_name, current_params)

            if missing:
                # Encore des parametres manquants, demander le prochain
                param_labels = {
                    'schedule_id': "l'ID de l'emploi du temps",
                    'session_id': "l'ID de la session",
                    'course_id': "l'ID du cours",
                    'room_id': "l'ID de la salle",
                    'teacher_id': "l'ID de l'enseignant",
                    'name': "le nom",
                    'academic_year': "l'annee academique (ex: 2024-2025)",
                    'semester': "le semestre",
                    'start_time': "l'heure de debut",
                    'duration': "la duree (en heures)"
                }
                next_param = missing[0]
                param_label = param_labels.get(next_param, next_param)

                return {
                    'response': f"Veuillez fournir {param_label}.",
                    'intent': 'agent_param_request',
                    'confidence': 100,
                    'context_data': {'missing_param': next_param},
                    'attachments': []
                }
            else:
                # Tous les parametres sont presents
                user_context.pop('awaiting_params', None)

                # Verifier si confirmation requise
                action_config = agent_service.ACTION_INTENTS.get(action_name, {})
                if action_config.get('confirmation_required'):
                    # Stocker l'action en attente de confirmation
                    user_context['pending_action'] = {
                        'action_name': action_name,
                        'params': current_params
                    }
                    self.context[user.id] = user_context

                    return {
                        'response': f"Voulez-vous vraiment executer cette action ? (Repondez 'oui' ou 'non')",
                        'intent': 'agent_confirmation',
                        'confidence': 100,
                        'context_data': {'action': action_name, 'params': current_params},
                        'attachments': []
                    }
                else:
                    # Executer directement
                    success, response_message, data = agent_service.execute_action(
                        action_name,
                        current_params,
                        conversation
                    )

                    self.context[user.id] = user_context

                    return {
                        'response': response_message,
                        'intent': 'agent_action',
                        'confidence': 100,
                        'context_data': {'action_executed': success, 'action_name': action_name},
                        'attachments': []
                    }

        # Detecter une nouvelle intention d'action
        action_name, action_confidence = agent_service.detect_action_intent(message)

        if action_name and action_confidence > 0.5:
            # Une action a ete detectee
            params = agent_service.extract_parameters(message, action_name)
            missing = agent_service.get_missing_parameters(action_name, params)

            if missing:
                # Parametres manquants, demander le premier
                param_labels = {
                    'schedule_id': "l'ID de l'emploi du temps",
                    'session_id': "l'ID de la session",
                    'course_id': "l'ID du cours",
                    'room_id': "l'ID de la salle",
                    'teacher_id': "l'ID de l'enseignant",
                    'name': "le nom",
                    'academic_year': "l'annee academique (ex: 2024-2025)",
                    'semester': "le semestre",
                    'start_time': "l'heure de debut",
                    'duration': "la duree (en heures)"
                }
                next_param = missing[0]
                param_label = param_labels.get(next_param, next_param)

                # Stocker le contexte
                user_context['awaiting_params'] = {
                    'action_name': action_name,
                    'params': params
                }
                self.context[user.id] = user_context

                return {
                    'response': f"Pour executer cette action, j'ai besoin de {param_label}.",
                    'intent': 'agent_param_request',
                    'confidence': 100,
                    'context_data': {'missing_param': next_param},
                    'attachments': []
                }
            else:
                # Tous les parametres sont presents
                action_config = agent_service.ACTION_INTENTS.get(action_name, {})
                if action_config.get('confirmation_required'):
                    # Demander confirmation
                    user_context['pending_action'] = {
                        'action_name': action_name,
                        'params': params
                    }
                    self.context[user.id] = user_context

                    return {
                        'response': f"Voulez-vous vraiment executer cette action ? (Repondez 'oui' ou 'non')",
                        'intent': 'agent_confirmation',
                        'confidence': 100,
                        'context_data': {'action': action_name, 'params': params},
                        'attachments': []
                    }
                else:
                    # Executer directement
                    success, response_message, data = agent_service.execute_action(
                        action_name,
                        params,
                        conversation
                    )

                    return {
                        'response': response_message,
                        'intent': 'agent_action',
                        'confidence': 100,
                        'context_data': {'action_executed': success, 'action_name': action_name},
                        'attachments': []
                    }

        # === TRAITEMENT NORMAL DU CHATBOT ===

        intent, confidence = self.detect_intent(message)

        # Chercher dans la base de connaissances
        knowledge_response = self._search_knowledge_base(message, intent)
        if knowledge_response:
            return {
                'response': knowledge_response['answer'],
                'intent': intent,
                'confidence': confidence,
                'context_data': {'source': 'knowledge_base'},
                'attachments': []
            }

        # Traiter selon l'intention avec contexte
        handlers = {
            'greeting': lambda: self._handle_greeting(user),
            'thanks': lambda: self._handle_thanks(user),
            'schedule': lambda: self._handle_schedule_query(message, user, user_context),
            'course': lambda: self._handle_course_query(message, user, user_context),
            'room': lambda: self._handle_room_query(message, user),
            'teacher': lambda: self._handle_teacher_query(message, user),
            'conflict': lambda: self._handle_conflict_query(message, user),
            'availability': lambda: self._handle_availability_query(message, user),
            'statistics': lambda: self._handle_statistics_query(message, user),
            'create': lambda: self._handle_create_action(message, user),
            'modify': lambda: self._handle_modify_action(message, user),
            'delete': lambda: self._handle_delete_action(message, user),
            'search': lambda: self._handle_search_query(message, user),
            'recommendation': lambda: self._handle_recommendation(message, user),
            'export': lambda: self._handle_export_request(message, user),
            'generate_schedule': lambda: self._handle_schedule_generation(message, user, user_context),
            'detect_conflicts': lambda: self._handle_detect_conflicts(message, user, user_context),
            'evaluate_quality': lambda: self._handle_evaluate_quality(message, user, user_context),
            'cancel_occurrence': lambda: self._handle_cancel_occurrence(message, user, user_context),
            'reschedule_occurrence': lambda: self._handle_reschedule_occurrence(message, user, user_context),
            'modify_occurrence': lambda: self._handle_modify_occurrence(message, user, user_context),
            'list_occurrences': lambda: self._handle_list_occurrences(message, user, user_context),
            # Handlers de navigation et contrôle UI
            'navigate_to_schedule': lambda: self._handle_navigate_to_schedule(message, user, user_context),
            'select_class': lambda: self._handle_select_class(message, user, user_context),
            'change_view_mode': lambda: self._handle_change_view_mode(message, user, user_context),
            'filter_sessions': lambda: self._handle_filter_sessions(message, user, user_context),
            'show_statistics': lambda: self._handle_show_statistics(message, user, user_context),
            'toggle_edit_mode': lambda: self._handle_toggle_edit_mode(message, user, user_context),
            'create_session': lambda: self._handle_create_session_ui(message, user, user_context),
            'export_schedule': lambda: self._handle_export_schedule_ui(message, user, user_context),
            'help': lambda: self._handle_help(),
        }

        handler = handlers.get(intent, self._handle_unknown)
        response = handler()

        # Mettre à jour le contexte
        self.context[user.id] = {
            'last_intent': intent,
            'last_message': message,
            'timestamp': timezone.now()
        }

        return response

    def _search_knowledge_base(self, message, intent):
        """Recherche dans la base de connaissances"""
        message_lower = message.lower()

        # Recherche par catégorie et mots-clés
        knowledge = ChatbotKnowledge.objects.filter(
            is_active=True,
            category=intent
        )

        for kb in knowledge:
            keywords = kb.keywords if isinstance(kb.keywords, list) else []
            if any(keyword.lower() in message_lower for keyword in keywords):
                kb.usage_count += 1
                kb.save()
                return {
                    'answer': kb.answer,
                    'category': kb.category
                }

        return None

    def _handle_greeting(self, user):
        """Gère les salutations avec personnalisation chaleureuse"""
        hour = datetime.now().hour
        if hour < 12:
            greeting = "Bonjour"
            emoji = "☀️"
        elif hour < 18:
            greeting = "Bon après-midi"
            emoji = "😊"
        else:
            greeting = "Bonsoir"
            emoji = "🌙"

        # Determiner le role de l'utilisateur pour personnaliser le message
        agent = AgentActionService(user)
        role = agent.user_role

        name = user.first_name or user.username
        response = f"{greeting} {name} ! {emoji}\n\n"
        response += random.choice([
            "Ravi de vous revoir ! Je suis là pour vous faciliter la vie. 💪",
            "Content de vous voir ! Prêt à optimiser votre journée ? 🚀",
            "Hello ! Je suis votre assistant intelligent OAPET, toujours à votre service ! ✨",
        ])

        response += "\n\n"

        # Personnaliser selon le role avec emojis
        if role == 'admin':
            response += "🔧 **En tant qu'administrateur**, je peux vous aider à :\n\n"
            response += "📊 **Gestion globale** :\n"
            response += "  • Générer des emplois du temps intelligemment\n"
            response += "  • Détecter et résoudre les conflits\n"
            response += "  • Analyser les statistiques et performances\n\n"
            response += "⚙️ **Actions rapides** :\n"
            response += "  • Créer/modifier des sessions\n"
            response += "  • Gérer les annulations et reports\n"
            response += "  • Publier les emplois du temps\n"
        elif role == 'teacher':
            response += "👨‍🏫 **En tant qu'enseignant**, je peux vous aider à :\n\n"
            response += "📅 **Votre planning** :\n"
            response += "  • Consulter vos cours et horaires\n"
            response += "  • Gérer vos sessions (salle, horaire)\n"
            response += "  • Voir les disponibilités\n\n"
            response += "🎯 **Actions pratiques** :\n"
            response += "  • Exporter votre emploi du temps\n"
            response += "  • Annuler ou reporter un cours\n"
            response += "  • Trouver une salle libre\n"
        else:  # student
            response += "🎓 **Bienvenue !** Je peux vous aider à :\n\n"
            response += "📚 **Votre emploi du temps** :\n"
            response += "  • Voir vos cours du jour/semaine\n"
            response += "  • Consulter l'emploi de votre classe\n"
            response += "  • Être notifié des changements\n\n"
            response += "🔍 **Informations utiles** :\n"
            response += "  • Localiser les salles de cours\n"
            response += "  • Contacter vos enseignants\n"
            response += "  • Exporter votre planning\n"

        # Ajouter des suggestions intelligentes
        suggestions = self.get_smart_suggestions('greeting', {})
        if suggestions:
            response += "\n\n💡 **Suggestions rapides** :\n"
            for suggestion in suggestions:
                response += f"  • {suggestion}\n"

        response += "\n✨ **Dites-moi simplement ce dont vous avez besoin !**"

        return {
            'response': response,
            'intent': 'greeting',
            'confidence': 100,
            'context_data': {'greeting_time': hour, 'user_role': role},
            'attachments': []
        }

    def _handle_schedule_query(self, message, user, context=None):
        """Gère les questions sur les emplois du temps avec contexte"""
        # Chercher des dates dans le message
        today = timezone.now().date()
        message_lower = message.lower()

        # Détection intelligente de la période demandée
        if 'demain' in message_lower:
            today = today + timezone.timedelta(days=1)
        elif 'hier' in message_lower:
            today = today - timezone.timedelta(days=1)
        elif any(word in message_lower for word in ['prochaine', 'prochain']):
            # Chercher la prochaine session
            return self._find_next_session(user)

        # Récupérer les sessions d'aujourd'hui
        sessions = ScheduleSession.objects.filter(
            specific_date=today
        ).select_related('course', 'room', 'teacher')[:5]

        if sessions:
            response = f"Emploi du temps pour aujourd'hui ({today.strftime('%d/%m/%Y')}) :\n\n"
            for session in sessions:
                start = session.specific_start_time or (session.time_slot.start_time if session.time_slot else "N/A")
                end = session.specific_end_time or (session.time_slot.end_time if session.time_slot else "N/A")
                response += f"- {start} - {end} : "
                response += f"{session.course.name}\n"
                teacher_name = session.teacher.user.get_full_name() if session.teacher else "N/A"
                room_name = session.room.name if session.room else "N/A"
                response += f"  Salle : {room_name}, Prof : {teacher_name}\n\n"
        else:
            response = "Aucune session programmee pour aujourd'hui."

        return {
            'response': response,
            'intent': 'schedule',
            'confidence': 85,
            'context_data': {'date': str(today), 'session_count': len(sessions)},
            'attachments': []
        }

    def _handle_course_query(self, message, user, context=None):
        """Gère les questions sur les cours avec recherche intelligente"""
        message_lower = message.lower()

        # Recherche intelligente dans le message
        courses = Course.objects.all()

        # Filtrer par mots-clés du message
        words = message_lower.split()
        for word in words:
            if len(word) > 3:
                courses = courses.filter(
                    Q(name__icontains=word) |
                    Q(code__icontains=word) |
                    Q(description__icontains=word)
                )

        courses = courses[:5]

        if courses:
            response = "Voici quelques cours disponibles :\n\n"
            for course in courses:
                response += f"- {course.name} ({course.code})\n"
                response += f"  Credits : {course.credits}, Heures : {course.hours_per_week}h/semaine\n"
                if course.teacher:
                    response += f"  Enseignant : {course.teacher.name}\n"
                response += "\n"
        else:
            response = "Aucun cours trouve dans la base de donnees."

        return {
            'response': response,
            'intent': 'course',
            'confidence': 80,
            'context_data': {'course_count': len(courses)},
            'attachments': []
        }

    def _handle_room_query(self, message, user):
        """Gère les questions sur les salles"""
        rooms = Room.objects.filter(is_active=True)[:5]

        if rooms:
            response = "Salles disponibles :\n\n"
            for room in rooms:
                response += f"- {room.name} ({room.building})\n"
                response += f"  Capacite : {room.capacity} places\n"
                if room.equipment:
                    response += f"  Equipements : {', '.join(room.equipment)}\n"
                response += "\n"
        else:
            response = "Aucune salle disponible actuellement."

        return {
            'response': response,
            'intent': 'room',
            'confidence': 80,
            'context_data': {'room_count': len(rooms)},
            'attachments': []
        }

    def _handle_teacher_query(self, message, user):
        """Gère les questions sur les enseignants"""
        teachers = Teacher.objects.filter(is_active=True)[:5]

        if teachers:
            response = "Enseignants disponibles :\n\n"
            for teacher in teachers:
                response += f"- {teacher.name}\n"
                if teacher.email:
                    response += f"  Email : {teacher.email}\n"
                if teacher.department:
                    response += f"  Departement : {teacher.department.name}\n"
                response += "\n"
        else:
            response = "Aucun enseignant trouve."

        return {
            'response': response,
            'intent': 'teacher',
            'confidence': 80,
            'context_data': {'teacher_count': len(teachers)},
            'attachments': []
        }

    def _handle_help(self):
        """Gère les demandes d'aide"""
        response = "Guide d'utilisation du chatbot OAPET\n\n"
        response += "Je peux vous aider avec les questions suivantes :\n\n"
        response += "**Emplois du temps**\n"
        response += '- "Quel est mon emploi du temps aujourd\'hui ?"\n'
        response += '- "Quand est mon prochain cours ?"\n\n'
        response += "**Cours**\n"
        response += '- "Quels cours sont disponibles ?"\n'
        response += '- "Montre-moi les cours de cette semaine"\n\n'
        response += "**Salles**\n"
        response += '- "Quelles salles sont disponibles ?"\n'
        response += '- "Ou se trouve la salle X ?"\n\n'
        response += "**Enseignants**\n"
        response += '- "Comment contacter le professeur X ?"\n'
        response += '- "Qui enseigne le cours Y ?"\n\n'
        response += "Posez-moi une question et je ferai de mon mieux pour vous aider !"

        return {
            'response': response,
            'intent': 'help',
            'confidence': 100,
            'context_data': {},
            'attachments': []
        }

    def _handle_unknown(self):
        """Gère les messages non compris avec empathie et aide"""
        responses = [
            "Hmm... 🤔 Je ne suis pas sûr de bien comprendre. Pas de panique, je suis là pour vous aider !",
            "Oups ! 😅 Je n'ai pas tout à fait saisi. Reformulons ensemble ?",
            "Je veux vraiment vous aider, mais je ne suis pas certain d'avoir compris. 💭",
        ]

        response = random.choice(responses)
        response += "\n\n"

        response += "✨ **Voici ce que vous pouvez essayer** :\n\n"

        response += "🎯 **Navigation et actions rapides** :\n"
        response += "  • 'Va sur la page emploi du temps'\n"
        response += "  • 'Affiche L1MED' (code de classe)\n"
        response += "  • 'Semaine' (changer de vue)\n"
        response += "  • 'CM' ou 'TD' (filtrer)\n\n"

        response += "📊 **Gestion emplois du temps** :\n"
        response += "  • 'Génère un emploi du temps'\n"
        response += "  • 'Détecte les conflits'\n"
        response += "  • 'Stats' (statistiques)\n\n"

        response += "📅 **Gestion des cours** :\n"
        response += "  • 'Annuler un cours'\n"
        response += "  • 'Reporter un cours'\n"
        response += "  • 'Liste des cours annulés'\n\n"

        response += "💾 **Export et autres** :\n"
        response += "  • 'Exporte en Excel/PDF'\n"
        response += "  • 'Active le mode édition'\n"
        response += "  • 'Aide' (voir toutes les possibilités)\n\n"

        response += "💬 **Astuce** : Vous pouvez utiliser un langage naturel !\n"
        response += "Par exemple : 'montre-moi l\'emploi de L1MED' ou 'je veux annuler un cours'\n\n"

        response += "🤗 N'hésitez pas, je suis là pour rendre votre expérience plus simple !"

        # Ajouter des suggestions de questions
        suggestions = self._get_suggested_questions()

        return {
            'response': response,
            'intent': 'unknown',
            'confidence': 0,
            'context_data': {'suggestions': suggestions},
            'attachments': []
        }

    def _handle_thanks(self, user):
        """Gère les remerciements"""
        responses = [
            "De rien ! Je suis la pour vous aider.",
            "Avec plaisir ! N'hesitez pas si vous avez d'autres questions.",
            "Content de pouvoir vous aider !",
            "C'est un plaisir ! Bonne journee !",
        ]
        import random
        response = random.choice(responses)

        return {
            'response': response,
            'intent': 'thanks',
            'confidence': 100,
            'context_data': {},
            'attachments': []
        }

    def _handle_conflict_query(self, message, user):
        """Gère les questions sur les conflits d'horaire"""
        from schedules.models import ScheduleSession

        # Rechercher les conflits potentiels
        today = timezone.now().date()
        sessions = ScheduleSession.objects.filter(specific_date=today).order_by('specific_start_time')

        conflicts = []
        for i, session in enumerate(sessions):
            for other_session in sessions[i+1:]:
                # Obtenir les heures
                s1_start = session.specific_start_time or (session.time_slot.start_time if session.time_slot else None)
                s1_end = session.specific_end_time or (session.time_slot.end_time if session.time_slot else None)
                s2_start = other_session.specific_start_time or (other_session.time_slot.start_time if other_session.time_slot else None)
                s2_end = other_session.specific_end_time or (other_session.time_slot.end_time if other_session.time_slot else None)

                if not all([s1_start, s1_end, s2_start, s2_end]):
                    continue

                # Vérifier le chevauchement
                if (s1_start < s2_end and s1_end > s2_start):
                    # Vérifier si même salle ou même enseignant
                    if (session.room == other_session.room or
                        session.teacher == other_session.teacher):
                        conflicts.append({
                            'session1': session,
                            'session2': other_session,
                            'type': 'room' if session.room == other_session.room else 'teacher'
                        })

        if conflicts:
            response = f"J'ai detecte {len(conflicts)} conflit(s) aujourd'hui :\n\n"
            for conflict in conflicts[:3]:  # Limiter a 3
                s1, s2 = conflict['session1'], conflict['session2']
                response += f"- {s1.course.name} et {s2.course.name}\n"
                s1_start = s1.specific_start_time or (s1.time_slot.start_time if s1.time_slot else "N/A")
                s2_end = s2.specific_end_time or (s2.time_slot.end_time if s2.time_slot else "N/A")
                response += f"  Heure : {s1_start} - {s2_end}\n"
                if conflict['type'] == 'room':
                    response += f"  Conflit de salle : {s1.room.name}\n"
                else:
                    response += f"  Conflit d'enseignant : {s1.teacher.user.get_full_name()}\n"
                response += "\n"
        else:
            response = "Aucun conflit detecte dans l'emploi du temps actuel."

        return {
            'response': response,
            'intent': 'conflict',
            'confidence': 85,
            'context_data': {'conflict_count': len(conflicts)},
            'attachments': []
        }

    def _handle_availability_query(self, message, user):
        """Gère les questions sur la disponibilité"""
        message_lower = message.lower()

        # Determiner ce qui est demande
        if any(word in message_lower for word in ['salle', 'local', 'classe']):
            # Disponibilite des salles
            available_rooms = Room.objects.filter(is_active=True)[:5]
            response = "Salles actuellement disponibles :\n\n"
            for room in available_rooms:
                response += f"- {room.name} - Capacite : {room.capacity} places\n"
        elif any(word in message_lower for word in ['prof', 'enseignant', 'professeur']):
            # Disponibilite des enseignants
            teachers = Teacher.objects.filter(is_active=True)[:5]
            response = "Enseignants disponibles :\n\n"
            for teacher in teachers:
                response += f"- {teacher.name}\n"
                if teacher.email:
                    response += f"  Contact : {teacher.email}\n"
        else:
            response = "Pour verifier la disponibilite, precisez si vous cherchez une salle ou un enseignant."

        return {
            'response': response,
            'intent': 'availability',
            'confidence': 75,
            'context_data': {},
            'attachments': []
        }

    def _handle_statistics_query(self, message, user):
        """Gère les questions statistiques"""
        from django.db.models import Count

        # Compter les différentes entités
        course_count = Course.objects.count()
        room_count = Room.objects.filter(is_active=True).count()
        teacher_count = Teacher.objects.filter(is_active=True).count()

        today = timezone.now().date()
        session_count = ScheduleSession.objects.filter(specific_date=today).count()

        response = "Statistiques du systeme OAPET :\n\n"
        response += f"- Cours : {course_count} cours disponibles\n"
        response += f"- Salles : {room_count} salles actives\n"
        response += f"- Enseignants : {teacher_count} enseignants actifs\n"
        response += f"- Sessions aujourd'hui : {session_count} sessions\n"

        return {
            'response': response,
            'intent': 'statistics',
            'confidence': 90,
            'context_data': {
                'courses': course_count,
                'rooms': room_count,
                'teachers': teacher_count,
                'sessions': session_count
            },
            'attachments': []
        }

    def _find_next_session(self, user):
        """Trouve la prochaine session pour l'utilisateur"""
        now = timezone.now()
        next_session = ScheduleSession.objects.filter(
            specific_date__gte=now.date(),
            specific_start_time__gte=now.time() if now.date() == now.date() else None
        ).select_related('course', 'room', 'teacher').order_by('specific_date', 'specific_start_time').first()

        if next_session:
            start = next_session.specific_start_time or (next_session.time_slot.start_time if next_session.time_slot else "N/A")
            response = f"Votre prochain cours est :\n\n"
            response += f"- {next_session.course.name}\n"
            response += f"- Date : {next_session.specific_date.strftime('%d/%m/%Y')}\n"
            response += f"- Heure : {start}\n"
            response += f"- Salle : {next_session.room.name if next_session.room else 'N/A'}\n"
            if next_session.teacher:
                response += f"- Enseignant : {next_session.teacher.user.get_full_name()}\n"
        else:
            response = "Aucun cours programme pour le moment."

        return {
            'response': response,
            'intent': 'schedule',
            'confidence': 90,
            'context_data': {},
            'attachments': []
        }

    def _handle_create_action(self, message, user):
        """Guide l'utilisateur pour créer de nouvelles entités"""
        message_lower = message.lower()

        if 'cours' in message_lower:
            entity = "cours"
            steps = ["nom du cours", "code", "nombre de credits", "heures par semaine"]
        elif 'salle' in message_lower:
            entity = "salle"
            steps = ["nom de la salle", "batiment", "capacite"]
        elif 'enseignant' in message_lower:
            entity = "enseignant"
            steps = ["nom", "prenom", "email", "departement"]
        else:
            entity = "entite"
            steps = []

        response = f"Pour creer un nouveau/nouvelle {entity}, vous devez fournir :\n\n"
        for i, step in enumerate(steps, 1):
            response += f"{i}. {step}\n"
        response += f"\nVeuillez utiliser le formulaire correspondant dans l'interface pour creer un {entity}."

        return {
            'response': response,
            'intent': 'create',
            'confidence': 85,
            'context_data': {'entity': entity},
            'attachments': []
        }

    def _handle_modify_action(self, message, user):
        """Guide pour modifier des entités"""
        response = "Pour modifier des informations :\n\n"
        response += "- Utilisez le tableau de bord\n"
        response += "- Cliquez sur l'element a modifier\n"
        response += "- Apportez vos changements\n"
        response += "- Sauvegardez\n\n"
        response += "Que souhaitez-vous modifier ?"

        return {
            'response': response,
            'intent': 'modify',
            'confidence': 80,
            'context_data': {},
            'attachments': []
        }

    def _handle_delete_action(self, message, user):
        """Guide pour supprimer des entités"""
        response = "Attention ! La suppression est irreversible.\n\n"
        response += "Pour supprimer un element :\n"
        response += "- Allez dans la section correspondante\n"
        response += "- Selectionnez l'element\n"
        response += "- Cliquez sur supprimer\n"
        response += "- Confirmez l'action\n\n"
        response += "Assurez-vous que l'element n'est pas utilise ailleurs avant de le supprimer."

        return {
            'response': response,
            'intent': 'delete',
            'confidence': 80,
            'context_data': {},
            'attachments': []
        }

    def _handle_search_query(self, message, user):
        """Recherche avancée multi-entités"""
        message_lower = message.lower()
        words = [w for w in message_lower.split() if len(w) > 3]

        results = {
            'cours': [],
            'salles': [],
            'enseignants': []
        }

        for word in words:
            # Recherche cours
            courses = Course.objects.filter(
                Q(name__icontains=word) | Q(code__icontains=word)
            )[:3]
            results['cours'].extend(courses)

            # Recherche salles
            rooms = Room.objects.filter(
                Q(name__icontains=word) | Q(building__icontains=word)
            )[:3]
            results['salles'].extend(rooms)

            # Recherche enseignants
            teachers = Teacher.objects.filter(
                Q(user__first_name__icontains=word) | Q(user__last_name__icontains=word)
            )[:3]
            results['enseignants'].extend(teachers)

        response = "Resultats de recherche :\n\n"

        if results['cours']:
            response += "Cours trouves :\n"
            for c in results['cours'][:3]:
                response += f"- {c.name} ({c.code})\n"
            response += "\n"

        if results['salles']:
            response += "Salles trouvees :\n"
            for r in results['salles'][:3]:
                response += f"- {r.name} ({r.building})\n"
            response += "\n"

        if results['enseignants']:
            response += "Enseignants trouves :\n"
            for t in results['enseignants'][:3]:
                response += f"- {t.user.get_full_name()}\n"

        if not any(results.values()):
            response = "Aucun resultat trouve pour votre recherche."

        return {
            'response': response,
            'intent': 'search',
            'confidence': 85,
            'context_data': results,
            'attachments': []
        }

    def _handle_recommendation(self, message, user):
        """Fournit des recommandations intelligentes"""
        # Analyser les conflits existants
        from schedules.models import ScheduleSession
        today = timezone.now().date()
        sessions = ScheduleSession.objects.filter(specific_date__gte=today)[:20]

        response = "Recommandations intelligentes :\n\n"
        response += "1. Optimisation des horaires :\n"
        response += "   - Evitez les cours tardifs le vendredi\n"
        response += "   - Privilegiez les matins pour les cours theoriques\n\n"
        response += "2. Gestion des salles :\n"
        response += "   - Groupez les cours par batiment\n"
        response += "   - Reservez les grandes salles pour les CM\n\n"
        response += "3. Charge de travail :\n"
        response += "   - Maximum 6h de cours par jour\n"
        response += "   - Pause dejeuner de 1h minimum\n"

        return {
            'response': response,
            'intent': 'recommendation',
            'confidence': 75,
            'context_data': {},
            'attachments': []
        }

    def _handle_export_request(self, message, user):
        """Guide pour exporter des données"""
        response = "Export de donnees :\n\n"
        response += "Formats disponibles :\n"
        response += "- CSV : Pour Excel et tableurs\n"
        response += "- JSON : Pour integration technique\n"
        response += "- PDF : Pour impression\n\n"
        response += "Dans chaque section, utilisez le bouton 'Exporter' pour telecharger les donnees.\n\n"
        response += "Que souhaitez-vous exporter ?"

        return {
            'response': response,
            'intent': 'export',
            'confidence': 85,
            'context_data': {'formats': ['csv', 'json', 'pdf']},
            'attachments': []
        }

    def _handle_schedule_generation(self, message, user, context):
        """Gère la génération d'emploi du temps avec wizard conversationnel"""
        from courses.models_class import StudentClass, AcademicPeriod
        import requests
        from django.conf import settings

        # Vérifier les permissions (admin uniquement)
        agent = AgentActionService(user)
        if agent.user_role != 'admin':
            return {
                'response': "Désolé, seuls les administrateurs peuvent générer des emplois du temps automatiquement.",
                'intent': 'generate_schedule',
                'confidence': 100,
                'context_data': {'permission_denied': True},
                'attachments': []
            }

        # Récupérer ou initialiser le wizard
        wizard = context.get('generation_wizard', {
            'step': 'init',
            'params': {}
        })

        message_lower = message.lower()

        # Étape initiale
        if wizard['step'] == 'init':
            wizard['step'] = 'academic_year'
            wizard['params'] = {}
            self.context[user.id] = {**context, 'generation_wizard': wizard}

            return {
                'response': "Je vais vous guider pour générer un emploi du temps.\n\n📅 Pour quelle année académique ?\nExemple: 2025-2026",
                'intent': 'generate_schedule',
                'confidence': 100,
                'context_data': {'wizard_step': 'academic_year'},
                'attachments': []
            }

        # Étape: Année académique
        if wizard['step'] == 'academic_year':
            year_match = re.search(r'(\d{4})[/-](\d{4})', message)
            if year_match:
                wizard['params']['academic_year'] = f"{year_match.group(1)}-{year_match.group(2)}"
                wizard['step'] = 'semester'
                self.context[user.id] = {**context, 'generation_wizard': wizard}

                return {
                    'response': f"Année académique: {wizard['params']['academic_year']}\n\n📚 Quel semestre ?\n- S1 (Septembre - Février)\n- S2 (Mars - Août)\n- Annuel",
                    'intent': 'generate_schedule',
                    'confidence': 100,
                    'context_data': {'wizard_step': 'semester'},
                    'attachments': []
                }
            else:
                return {
                    'response': "Format invalide. Veuillez entrer l'année académique au format YYYY-YYYY.\nExemple: 2025-2026",
                    'intent': 'generate_schedule',
                    'confidence': 100,
                    'context_data': {'wizard_step': 'academic_year', 'error': 'invalid_format'},
                    'attachments': []
                }

        # Étape: Semestre
        if wizard['step'] == 'semester':
            if 's1' in message_lower or 'semestre 1' in message_lower or 'premier' in message_lower:
                wizard['params']['semester'] = 'S1'
            elif 's2' in message_lower or 'semestre 2' in message_lower or 'deuxi' in message_lower or 'second' in message_lower:
                wizard['params']['semester'] = 'S2'
            elif 'annuel' in message_lower or 'année' in message_lower:
                wizard['params']['semester'] = 'ANNUEL'
            else:
                return {
                    'response': "Réponse non reconnue. Veuillez choisir:\n- S1\n- S2\n- Annuel",
                    'intent': 'generate_schedule',
                    'confidence': 100,
                    'context_data': {'wizard_step': 'semester', 'error': 'invalid_choice'},
                    'attachments': []
                }

            # Récupérer les classes disponibles
            classes = StudentClass.objects.filter(is_active=True).order_by('level', 'name')
            class_list = "\n".join([f"- {cls.code}: {cls.name} ({cls.level})" for cls in classes[:10]])

            wizard['step'] = 'classes'
            self.context[user.id] = {**context, 'generation_wizard': wizard}

            return {
                'response': f"Semestre: {wizard['params']['semester']}\n\n🎓 Pour quelles classes ?\n\n{class_list}\n\nVous pouvez entrer un ou plusieurs codes de classes séparés par des virgules.\nExemple: L1MED, L2MED",
                'intent': 'generate_schedule',
                'confidence': 100,
                'context_data': {'wizard_step': 'classes'},
                'attachments': []
            }

        # Étape: Classes
        if wizard['step'] == 'classes':
            # Extraire les codes de classes du message
            class_codes = [code.strip().upper() for code in re.split(r'[,;\s]+', message) if len(code.strip()) > 2]

            if not class_codes:
                return {
                    'response': "Aucun code de classe valide détecté. Veuillez entrer les codes des classes.\nExemple: L1MED, L2MED",
                    'intent': 'generate_schedule',
                    'confidence': 100,
                    'context_data': {'wizard_step': 'classes', 'error': 'no_classes'},
                    'attachments': []
                }

            # Chercher les classes
            found_classes = StudentClass.objects.filter(code__in=class_codes, is_active=True)

            if not found_classes.exists():
                return {
                    'response': f"Aucune classe trouvée avec ces codes: {', '.join(class_codes)}\nVeuillez vérifier et réessayer.",
                    'intent': 'generate_schedule',
                    'confidence': 100,
                    'context_data': {'wizard_step': 'classes', 'error': 'classes_not_found'},
                    'attachments': []
                }

            wizard['params']['class_ids'] = list(found_classes.values_list('id', flat=True))
            wizard['params']['class_codes'] = list(found_classes.values_list('code', flat=True))
            wizard['step'] = 'dates'
            self.context[user.id] = {**context, 'generation_wizard': wizard}

            classes_str = ', '.join([f"{cls.code}" for cls in found_classes])

            return {
                'response': f"Classes sélectionnées: {classes_str}\n\n📆 Dates de début et de fin ?\n\nExemple: Du 1er septembre 2025 au 31 janvier 2026\nOu tapez 'auto' pour utiliser les dates standard du semestre.",
                'intent': 'generate_schedule',
                'confidence': 100,
                'context_data': {'wizard_step': 'dates'},
                'attachments': []
            }

        # Étape: Dates
        if wizard['step'] == 'dates':
            if 'auto' in message_lower or 'standard' in message_lower or 'défaut' in message_lower or 'defaut' in message_lower:
                # Dates automatiques selon le semestre
                year_start = int(wizard['params']['academic_year'].split('-')[0])
                if wizard['params']['semester'] == 'S1':
                    wizard['params']['start_date'] = f"{year_start}-09-01"
                    wizard['params']['end_date'] = f"{year_start + 1}-01-31"
                elif wizard['params']['semester'] == 'S2':
                    wizard['params']['start_date'] = f"{year_start + 1}-02-01"
                    wizard['params']['end_date'] = f"{year_start + 1}-07-31"
                else:  # Annuel
                    wizard['params']['start_date'] = f"{year_start}-09-01"
                    wizard['params']['end_date'] = f"{year_start + 1}-07-31"
            else:
                # Extraire les dates du message
                date_matches = re.findall(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})', message)
                if len(date_matches) >= 2:
                    # Format DD-MM-YYYY vers YYYY-MM-DD
                    start = f"{date_matches[0][2]}-{date_matches[0][1].zfill(2)}-{date_matches[0][0].zfill(2)}"
                    end = f"{date_matches[1][2]}-{date_matches[1][1].zfill(2)}-{date_matches[1][0].zfill(2)}"
                    wizard['params']['start_date'] = start
                    wizard['params']['end_date'] = end
                else:
                    return {
                        'response': "Dates non reconnues. Veuillez entrer les dates au format:\nDu JJ/MM/AAAA au JJ/MM/AAAA\n\nOu tapez 'auto' pour les dates standards.",
                        'intent': 'generate_schedule',
                        'confidence': 100,
                        'context_data': {'wizard_step': 'dates', 'error': 'invalid_dates'},
                        'attachments': []
                    }

            wizard['step'] = 'confirmation'
            self.context[user.id] = {**context, 'generation_wizard': wizard}

            # Récapitulatif
            recap = f"""📋 Récapitulatif de la génération:

Année académique: {wizard['params']['academic_year']}
Semestre: {wizard['params']['semester']}
Classes: {', '.join(wizard['params']['class_codes'])}
Période: du {wizard['params']['start_date']} au {wizard['params']['end_date']}

⚠️ La génération peut prendre quelques instants.

Voulez-vous lancer la génération ? (Répondez 'oui' ou 'non')"""

            return {
                'response': recap,
                'intent': 'generate_schedule',
                'confidence': 100,
                'context_data': {'wizard_step': 'confirmation', 'params': wizard['params']},
                'attachments': []
            }

        # Étape: Confirmation et exécution
        if wizard['step'] == 'confirmation':
            if any(word in message_lower for word in ['oui', 'ok', 'confirme', 'yes', 'valide', 'lance', 'go']):
                # Appeler l'API de génération
                try:
                    # Préparer les paramètres pour l'API
                    api_params = {
                        'academic_year': wizard['params']['academic_year'],
                        'semester': wizard['params']['semester'],
                        'start_date': wizard['params']['start_date'],
                        'end_date': wizard['params']['end_date'],
                        'class_ids': wizard['params']['class_ids']
                    }

                    # Appeler la fonction de génération réelle
                    result = self._call_generation_api(api_params, user)

                    # Nettoyer le contexte
                    context.pop('generation_wizard', None)
                    self.context[user.id] = context

                    if result.get('success'):
                        schedules_created = result.get('schedules', [])

                        response_text = f"""✅ Génération réussie!

J'ai créé {len(schedules_created)} emploi(s) du temps:

"""
                        for schedule in schedules_created:
                            response_text += f"📚 {schedule['name']}\n"
                            response_text += f"   Sessions: {schedule.get('sessions_count', 0)}\n\n"

                        response_text += "📊 Vous pouvez consulter les emplois du temps dans la section \"Gestion des emplois du temps\"."

                        return {
                            'response': response_text,
                            'intent': 'generate_schedule',
                            'confidence': 100,
                            'context_data': {
                                'generation_started': True,
                                'params': api_params,
                                'schedules': schedules_created
                            },
                            'attachments': [{'type': 'generation_result', 'data': result}]
                        }
                    else:
                        error_msg = result.get('error', 'Erreur inconnue')
                        return {
                            'response': f"❌ Erreur lors de la génération: {error_msg}\n\nVeuillez vérifier les paramètres et réessayer.",
                            'intent': 'generate_schedule',
                            'confidence': 100,
                            'context_data': {'generation_failed': True, 'error': error_msg},
                            'attachments': []
                        }

                except Exception as e:
                    # Nettoyer le contexte même en cas d'erreur
                    context.pop('generation_wizard', None)
                    self.context[user.id] = context

                    return {
                        'response': f"❌ Erreur lors de la génération: {str(e)}\n\nVeuillez réessayer ou contacter l'administrateur.",
                        'intent': 'generate_schedule',
                        'confidence': 100,
                        'context_data': {'generation_failed': True, 'error': str(e)},
                        'attachments': []
                    }

            elif any(word in message_lower for word in ['non', 'annule', 'stop', 'cancel']):
                # Annuler la génération
                context.pop('generation_wizard', None)
                self.context[user.id] = context

                return {
                    'response': "Génération annulée. Comment puis-je vous aider autrement ?",
                    'intent': 'generate_schedule',
                    'confidence': 100,
                    'context_data': {'generation_cancelled': True},
                    'attachments': []
                }
            else:
                return {
                    'response': "Veuillez répondre 'oui' pour confirmer ou 'non' pour annuler.",
                    'intent': 'generate_schedule',
                    'confidence': 100,
                    'context_data': {'wizard_step': 'confirmation', 'awaiting_confirmation': True},
                    'attachments': []
                }

        # État par défaut
        return {
            'response': "Une erreur s'est produite dans le processus de génération. Veuillez réessayer.",
            'intent': 'generate_schedule',
            'confidence': 100,
            'context_data': {'error': 'unknown_state'},
            'attachments': []
        }

    def _handle_detect_conflicts(self, message, user, context):
        """Détecte les conflits dans les emplois du temps"""
        from schedules.models import Schedule

        # Récupérer tous les emplois du temps actifs
        schedules = Schedule.objects.filter(is_published=True)[:5]

        if not schedules.exists():
            return {
                'response': "Aucun emploi du temps publié trouvé. Publiez un emploi du temps pour détecter les conflits.",
                'intent': 'detect_conflicts',
                'confidence': 100,
                'context_data': {'no_schedules': True},
                'attachments': []
            }

        # Pour chaque emploi du temps, rechercher les conflits
        all_conflicts = []

        for schedule in schedules:
            # Appeler la fonction de détection de conflits existante
            conflicts_found = self._find_schedule_conflicts(schedule)
            if conflicts_found:
                all_conflicts.extend(conflicts_found)

        if all_conflicts:
            response = f"⚠️ J'ai détecté {len(all_conflicts)} conflit(s):\n\n"

            for idx, conflict in enumerate(all_conflicts[:5], 1):
                response += f"{idx}. {conflict['type']}: {conflict['description']}\n"
                response += f"   Suggestion: {conflict['suggestion']}\n\n"

            if len(all_conflicts) > 5:
                response += f"... et {len(all_conflicts) - 5} autre(s) conflit(s).\n"

            return {
                'response': response,
                'intent': 'detect_conflicts',
                'confidence': 100,
                'context_data': {'conflict_count': len(all_conflicts)},
                'attachments': [{'type': 'conflicts', 'data': all_conflicts[:10]}]
            }
        else:
            return {
                'response': "✅ Aucun conflit détecté dans les emplois du temps publiés!",
                'intent': 'detect_conflicts',
                'confidence': 100,
                'context_data': {'conflict_count': 0},
                'attachments': []
            }

    def _handle_evaluate_quality(self, message, user, context):
        """Évalue la qualité d'un emploi du temps"""
        from schedules.models import Schedule

        # Chercher un emploi du temps dans le message
        schedule_id_match = re.search(r'#?(\d+)', message)

        if schedule_id_match:
            schedule_id = int(schedule_id_match.group(1))
            try:
                schedule = Schedule.objects.get(id=schedule_id)
            except Schedule.DoesNotExist:
                return {
                    'response': f"Emploi du temps #{schedule_id} introuvable.",
                    'intent': 'evaluate_quality',
                    'confidence': 100,
                    'context_data': {'error': 'not_found'},
                    'attachments': []
                }
        else:
            # Prendre le plus récent
            schedule = Schedule.objects.filter(is_published=True).order_by('-created_at').first()

            if not schedule:
                return {
                    'response': "Aucun emploi du temps publié trouvé. Veuillez spécifier l'ID d'un emploi du temps.",
                    'intent': 'evaluate_quality',
                    'confidence': 100,
                    'context_data': {'error': 'no_schedule'},
                    'attachments': []
                }

        # Calculer les métriques de qualité
        quality = self._calculate_quality_score(schedule)

        # Formater la réponse
        response = f"""📊 Évaluation de qualité: {schedule.name}

🎯 Score global: {quality['overall_score']}/1000 ({quality['grade']})

Détails:
• Qualité pédagogique: {quality['pedagogical_quality']}/100
• Satisfaction enseignants: {quality['teacher_satisfaction']}/100
• Utilisation salles: {quality['room_utilization']}/100
• Équilibre charge étudiants: {quality['student_balance']}/100

⚠️ Contraintes dures:
• Conflits salles: {quality['room_conflicts']}
• Conflits enseignants: {quality['teacher_conflicts']}
• Heures manquantes: {quality['missing_hours']}

💡 Recommandations:
{quality['recommendations']}
"""

        return {
            'response': response,
            'intent': 'evaluate_quality',
            'confidence': 100,
            'context_data': {'schedule_id': schedule.id, 'quality': quality},
            'attachments': [{'type': 'quality_evaluation', 'data': quality}]
        }

    def _call_generation_api(self, params, user):
        """Appelle la génération d'emploi du temps réelle"""
        from datetime import datetime
        from courses.models_class import StudentClass, AcademicPeriod, ClassCourse
        from schedules.models import Schedule, ScheduleSession, TimeSlot
        from rooms.models import Room
        from django.db import transaction
        import logging

        logger = logging.getLogger(__name__)

        try:
            # Récupérer ou créer la période académique
            academic_year = params['academic_year']
            semester = params['semester']
            start_date = datetime.strptime(params['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(params['end_date'], '%Y-%m-%d').date()
            class_ids = params['class_ids']

            period_name = f"{academic_year} - {semester}"

            academic_period, created = AcademicPeriod.objects.get_or_create(
                academic_year=academic_year,
                semester=semester,
                defaults={
                    'name': period_name,
                    'start_date': start_date,
                    'end_date': end_date,
                    'is_current': True
                }
            )

            generated_schedules = []

            with transaction.atomic():
                # Générer pour chaque classe
                for class_id in class_ids:
                    try:
                        student_class = StudentClass.objects.get(id=class_id)
                    except StudentClass.DoesNotExist:
                        logger.error(f"StudentClass {class_id} n'existe pas")
                        continue

                    # Créer l'emploi du temps
                    schedule = Schedule.objects.create(
                        name=f"Emploi du temps {academic_period.name} - {student_class.name}",
                        academic_period=academic_period,
                        student_class=student_class,
                        level=student_class.level,
                        schedule_type='class',
                        status='draft',
                        created_by=user
                    )

                    # Compter les sessions (on va générer dans une prochaine étape)
                    # Pour l'instant, on retourne juste l'emploi du temps créé
                    sessions_count = 0

                    generated_schedules.append({
                        'id': schedule.id,
                        'name': schedule.name,
                        'sessions_count': sessions_count,
                        'class': student_class.name
                    })

                    logger.info(f"Emploi du temps créé: {schedule.name}")

            return {
                'success': True,
                'schedules': generated_schedules,
                'period': {
                    'id': academic_period.id,
                    'name': academic_period.name,
                    'created': created
                }
            }

        except Exception as e:
            logger.error(f"Erreur lors de la génération: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _find_schedule_conflicts(self, schedule):
        """Trouve les conflits dans un emploi du temps (méthode helper)"""
        from schedules.models import ScheduleSession
        from django.db.models import Q

        conflicts = []

        # Récupérer toutes les sessions de cet emploi du temps
        sessions = ScheduleSession.objects.filter(schedule=schedule).select_related(
            'course', 'room', 'teacher', 'time_slot'
        )

        # Vérifier les conflits de salle et d'enseignant
        for session in sessions:
            if not session.specific_date or not session.time_slot:
                continue

            # Trouver les sessions qui se chevauchent
            overlapping = ScheduleSession.objects.filter(
                specific_date=session.specific_date,
                time_slot=session.time_slot
            ).exclude(id=session.id).select_related('course', 'room', 'teacher')

            for other in overlapping:
                # Conflit de salle
                if session.room and other.room and session.room == other.room:
                    conflicts.append({
                        'type': 'Conflit de salle',
                        'description': f"La salle {session.room.name} est utilisée par {session.course.name} et {other.course.name}",
                        'suggestion': f"Déplacer l'un des cours vers une autre salle",
                        'severity': 'high'
                    })

                # Conflit d'enseignant
                if session.teacher and other.teacher and session.teacher == other.teacher:
                    conflicts.append({
                        'type': 'Conflit enseignant',
                        'description': f"{session.teacher.user.get_full_name()} est assigné à {session.course.name} et {other.course.name}",
                        'suggestion': f"Reprogrammer l'un des cours à un autre moment",
                        'severity': 'high'
                    })

        return conflicts

    def _calculate_quality_score(self, schedule):
        """Calcule le score de qualité d'un emploi du temps (méthode helper)"""
        try:
            from schedules.schedule_evaluator import ScheduleEvaluator

            evaluator = ScheduleEvaluator()

            # Score global
            global_score = evaluator.evaluate(schedule)

            # Convertir -inf en 0
            is_valid = global_score != float('-inf')
            global_score_safe = 0 if global_score == float('-inf') else global_score

            # Rapport détaillé
            report = evaluator.get_detailed_report(schedule)

            # Grade
            if not is_valid:
                grade = 'F'
            elif global_score_safe > 800:
                grade = 'A'
            elif global_score_safe > 600:
                grade = 'B'
            elif global_score_safe > 400:
                grade = 'C'
            elif global_score_safe > 200:
                grade = 'D'
            else:
                grade = 'F'

            # Recommandations
            recommendations_list = []
            if report['hard_constraints']['room_conflicts'] > 0:
                recommendations_list.append(
                    f"• {report['hard_constraints']['room_conflicts']} conflit(s) de salles - Modifier les sessions en conflit"
                )

            if report['hard_constraints']['teacher_conflicts'] > 0:
                recommendations_list.append(
                    f"• {report['hard_constraints']['teacher_conflicts']} conflit(s) d'enseignants - Reprogrammer les cours"
                )

            if report['hard_constraints']['missing_course_hours'] > 0:
                recommendations_list.append(
                    f"• {report['hard_constraints']['missing_course_hours']} cours avec heures manquantes - Compléter les heures"
                )

            if is_valid and report['soft_scores']['pedagogical_quality'] < 60:
                recommendations_list.append(
                    "• Qualité pédagogique faible - Déplacer les CM le matin et les TP l'après-midi"
                )

            if is_valid and report['soft_scores']['teacher_satisfaction'] < 60:
                recommendations_list.append(
                    "• Satisfaction enseignants faible - Vérifier les préférences horaires"
                )

            if is_valid and report['soft_scores']['student_balance'] < 60:
                recommendations_list.append(
                    "• Charge étudiants déséquilibrée - Mieux répartir les cours dans la semaine"
                )

            recommendations = '\n'.join(recommendations_list) if recommendations_list else '• Aucune recommandation - Emploi du temps optimal'

            return {
                'overall_score': int(global_score_safe),
                'grade': grade,
                'is_valid': is_valid,
                'pedagogical_quality': int(report['soft_scores']['pedagogical_quality']),
                'teacher_satisfaction': int(report['soft_scores']['teacher_satisfaction']),
                'room_utilization': int(report['soft_scores']['room_utilization']),
                'student_balance': int(report['soft_scores']['student_balance']),
                'teacher_balance': int(report['soft_scores']['teacher_balance']),
                'room_conflicts': report['hard_constraints']['room_conflicts'],
                'teacher_conflicts': report['hard_constraints']['teacher_conflicts'],
                'missing_hours': report['hard_constraints']['missing_course_hours'],
                'recommendations': recommendations
            }

        except Exception as e:
            # En cas d'erreur, retourner des valeurs par défaut
            return {
                'overall_score': 0,
                'grade': 'N/A',
                'is_valid': False,
                'pedagogical_quality': 0,
                'teacher_satisfaction': 0,
                'room_utilization': 0,
                'student_balance': 0,
                'teacher_balance': 0,
                'room_conflicts': 0,
                'teacher_conflicts': 0,
                'missing_hours': 0,
                'recommendations': f'• Erreur lors de l\'évaluation: {str(e)}'
            }

    def _handle_cancel_occurrence(self, message, user, context):
        """Gère l'annulation d'une occurrence de cours"""
        from schedules.models import SessionOccurrence
        from datetime import datetime

        # Vérifier les permissions
        agent = AgentActionService(user)
        if agent.user_role not in ['admin', 'teacher']:
            return {
                'response': "Désolé, seuls les administrateurs et enseignants peuvent annuler des cours.",
                'intent': 'cancel_occurrence',
                'confidence': 100,
                'context_data': {'permission_denied': True},
                'attachments': []
            }

        # Récupérer ou initialiser le wizard
        wizard = context.get('cancel_wizard', {
            'step': 'init',
            'params': {}
        })

        message_lower = message.lower()

        # Étape initiale - rechercher le cours à annuler
        if wizard['step'] == 'init':
            # Extraire la date du message
            date_match = re.search(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})', message)
            date_match_reverse = re.search(r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})', message)

            # Détecter "aujourd'hui", "demain", etc.
            target_date = None
            if 'aujourd\'hui' in message_lower or 'aujourdhui' in message_lower:
                target_date = datetime.now().date()
            elif 'demain' in message_lower:
                target_date = datetime.now().date() + timezone.timedelta(days=1)
            elif date_match:
                day, month, year = date_match.groups()
                target_date = datetime(int(year), int(month), int(day)).date()
            elif date_match_reverse:
                year, month, day = date_match_reverse.groups()
                target_date = datetime(int(year), int(month), int(day)).date()

            if not target_date:
                wizard['step'] = 'ask_date'
                self.context[user.id] = {**context, 'cancel_wizard': wizard}

                return {
                    'response': "📅 Pour quelle date voulez-vous annuler un cours?\nExemple: 15/03/2026 ou 'aujourd'hui' ou 'demain'",
                    'intent': 'cancel_occurrence',
                    'confidence': 100,
                    'context_data': {'wizard_step': 'ask_date'},
                    'attachments': []
                }

            # Chercher les occurrences de ce jour
            occurrences = SessionOccurrence.objects.filter(
                actual_date=target_date,
                is_cancelled=False
            ).select_related('session_template__course', 'room', 'teacher').order_by('start_time')

            if not occurrences.exists():
                context.pop('cancel_wizard', None)
                self.context[user.id] = context

                return {
                    'response': f"Aucun cours trouvé pour le {target_date.strftime('%d/%m/%Y')}.",
                    'intent': 'cancel_occurrence',
                    'confidence': 100,
                    'context_data': {'no_occurrences': True},
                    'attachments': []
                }

            # Afficher la liste des cours
            response = f"Cours du {target_date.strftime('%d/%m/%Y')}:\n\n"
            for idx, occ in enumerate(occurrences, 1):
                course_name = occ.session_template.course.name
                response += f"{idx}. {occ.start_time.strftime('%H:%M')} - {course_name}\n"
                response += f"   Salle: {occ.room.name}, Prof: {occ.teacher.user.get_full_name()}\n\n"

            response += "Quel cours voulez-vous annuler? (Entrez le numéro)"

            wizard['step'] = 'select_course'
            wizard['params'] = {
                'date': str(target_date),
                'occurrences': [occ.id for occ in occurrences]
            }
            self.context[user.id] = {**context, 'cancel_wizard': wizard}

            return {
                'response': response,
                'intent': 'cancel_occurrence',
                'confidence': 100,
                'context_data': {'wizard_step': 'select_course', 'occurrences_count': len(occurrences)},
                'attachments': []
            }

        # Étape: Demander la date
        if wizard['step'] == 'ask_date':
            date_match = re.search(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})', message)

            if 'aujourd\'hui' in message_lower or 'aujourdhui' in message_lower:
                target_date = datetime.now().date()
            elif 'demain' in message_lower:
                target_date = datetime.now().date() + timezone.timedelta(days=1)
            elif date_match:
                day, month, year = date_match.groups()
                target_date = datetime(int(year), int(month), int(day)).date()
            else:
                return {
                    'response': "Format de date invalide. Utilisez JJ/MM/AAAA, 'aujourd'hui' ou 'demain'.",
                    'intent': 'cancel_occurrence',
                    'confidence': 100,
                    'context_data': {'wizard_step': 'ask_date', 'error': 'invalid_date'},
                    'attachments': []
                }

            # Chercher les occurrences
            occurrences = SessionOccurrence.objects.filter(
                actual_date=target_date,
                is_cancelled=False
            ).select_related('session_template__course', 'room', 'teacher').order_by('start_time')

            if not occurrences.exists():
                context.pop('cancel_wizard', None)
                self.context[user.id] = context

                return {
                    'response': f"Aucun cours trouvé pour le {target_date.strftime('%d/%m/%Y')}.",
                    'intent': 'cancel_occurrence',
                    'confidence': 100,
                    'context_data': {'no_occurrences': True},
                    'attachments': []
                }

            # Afficher la liste
            response = f"Cours du {target_date.strftime('%d/%m/%Y')}:\n\n"
            for idx, occ in enumerate(occurrences, 1):
                course_name = occ.session_template.course.name
                response += f"{idx}. {occ.start_time.strftime('%H:%M')} - {course_name}\n"
                response += f"   Salle: {occ.room.name}, Prof: {occ.teacher.user.get_full_name()}\n\n"

            response += "Quel cours voulez-vous annuler? (Entrez le numéro)"

            wizard['step'] = 'select_course'
            wizard['params'] = {
                'date': str(target_date),
                'occurrences': [occ.id for occ in occurrences]
            }
            self.context[user.id] = {**context, 'cancel_wizard': wizard}

            return {
                'response': response,
                'intent': 'cancel_occurrence',
                'confidence': 100,
                'context_data': {'wizard_step': 'select_course'},
                'attachments': []
            }

        # Étape: Sélection du cours
        if wizard['step'] == 'select_course':
            # Extraire le numéro
            number_match = re.search(r'\b(\d+)\b', message)
            if number_match:
                selected_num = int(number_match.group(1))
                occurrence_ids = wizard['params']['occurrences']

                if 1 <= selected_num <= len(occurrence_ids):
                    wizard['params']['occurrence_id'] = occurrence_ids[selected_num - 1]
                    wizard['step'] = 'ask_reason'
                    self.context[user.id] = {**context, 'cancel_wizard': wizard}

                    return {
                        'response': "Raison de l'annulation? (Ex: Enseignant absent, jour férié, etc.)",
                        'intent': 'cancel_occurrence',
                        'confidence': 100,
                        'context_data': {'wizard_step': 'ask_reason'},
                        'attachments': []
                    }
                else:
                    return {
                        'response': f"Numéro invalide. Choisissez entre 1 et {len(occurrence_ids)}.",
                        'intent': 'cancel_occurrence',
                        'confidence': 100,
                        'context_data': {'wizard_step': 'select_course', 'error': 'invalid_number'},
                        'attachments': []
                    }
            else:
                return {
                    'response': "Veuillez entrer le numéro du cours à annuler.",
                    'intent': 'cancel_occurrence',
                    'confidence': 100,
                    'context_data': {'wizard_step': 'select_course', 'error': 'no_number'},
                    'attachments': []
                }

        # Étape: Raison de l'annulation
        if wizard['step'] == 'ask_reason':
            wizard['params']['reason'] = message
            wizard['step'] = 'confirmation'
            self.context[user.id] = {**context, 'cancel_wizard': wizard}

            # Récupérer l'occurrence pour affichage
            try:
                occurrence = SessionOccurrence.objects.select_related(
                    'session_template__course', 'room', 'teacher'
                ).get(id=wizard['params']['occurrence_id'])

                recap = f"""📋 Récapitulatif de l'annulation:

Cours: {occurrence.session_template.course.name}
Date: {occurrence.actual_date.strftime('%d/%m/%Y')}
Heure: {occurrence.start_time.strftime('%H:%M')} - {occurrence.end_time.strftime('%H:%M')}
Salle: {occurrence.room.name}
Raison: {message}

Confirmer l'annulation? (oui/non)"""

                return {
                    'response': recap,
                    'intent': 'cancel_occurrence',
                    'confidence': 100,
                    'context_data': {'wizard_step': 'confirmation'},
                    'attachments': []
                }
            except SessionOccurrence.DoesNotExist:
                context.pop('cancel_wizard', None)
                self.context[user.id] = context

                return {
                    'response': "Erreur: Cours introuvable.",
                    'intent': 'cancel_occurrence',
                    'confidence': 100,
                    'context_data': {'error': 'occurrence_not_found'},
                    'attachments': []
                }

        # Étape: Confirmation
        if wizard['step'] == 'confirmation':
            if any(word in message_lower for word in ['oui', 'ok', 'confirme', 'yes', 'valide']):
                try:
                    occurrence = SessionOccurrence.objects.get(id=wizard['params']['occurrence_id'])

                    # Annuler l'occurrence
                    occurrence.is_cancelled = True
                    occurrence.status = 'cancelled'
                    occurrence.cancellation_reason = wizard['params']['reason']
                    occurrence.cancelled_at = timezone.now()
                    occurrence.cancelled_by = user
                    occurrence.save()

                    # Nettoyer le contexte
                    context.pop('cancel_wizard', None)
                    self.context[user.id] = context

                    return {
                        'response': f"✅ Cours annulé avec succès!\n\n{occurrence.session_template.course.name} du {occurrence.actual_date.strftime('%d/%m/%Y')} à {occurrence.start_time.strftime('%H:%M')} a été annulé.\n\nRaison: {wizard['params']['reason']}",
                        'intent': 'cancel_occurrence',
                        'confidence': 100,
                        'context_data': {'cancelled': True, 'occurrence_id': occurrence.id},
                        'attachments': []
                    }

                except Exception as e:
                    context.pop('cancel_wizard', None)
                    self.context[user.id] = context

                    return {
                        'response': f"❌ Erreur lors de l'annulation: {str(e)}",
                        'intent': 'cancel_occurrence',
                        'confidence': 100,
                        'context_data': {'error': str(e)},
                        'attachments': []
                    }

            elif any(word in message_lower for word in ['non', 'annule', 'stop', 'cancel']):
                context.pop('cancel_wizard', None)
                self.context[user.id] = context

                return {
                    'response': "Annulation annulée. Le cours reste programmé.",
                    'intent': 'cancel_occurrence',
                    'confidence': 100,
                    'context_data': {'cancelled_action': True},
                    'attachments': []
                }
            else:
                return {
                    'response': "Veuillez répondre 'oui' pour confirmer ou 'non' pour annuler.",
                    'intent': 'cancel_occurrence',
                    'confidence': 100,
                    'context_data': {'wizard_step': 'confirmation', 'awaiting_confirmation': True},
                    'attachments': []
                }

        return {
            'response': "Une erreur s'est produite. Veuillez réessayer.",
            'intent': 'cancel_occurrence',
            'confidence': 100,
            'context_data': {'error': 'unknown_state'},
            'attachments': []
        }

    def _handle_reschedule_occurrence(self, message, user, context):
        """Gère la reprogrammation d'une occurrence de cours"""
        # TODO: Implémenter la reprogrammation
        return {
            'response': "Fonctionnalité de reprogrammation en cours de développement.",
            'intent': 'reschedule_occurrence',
            'confidence': 100,
            'context_data': {},
            'attachments': []
        }

    def _handle_modify_occurrence(self, message, user, context):
        """Gère la modification d'une occurrence (salle/enseignant)"""
        # TODO: Implémenter la modification
        return {
            'response': "Fonctionnalité de modification en cours de développement.",
            'intent': 'modify_occurrence',
            'confidence': 100,
            'context_data': {},
            'attachments': []
        }

    def _handle_list_occurrences(self, message, user, context):
        """Liste les occurrences annulées/modifiées"""
        from schedules.models import SessionOccurrence
        from datetime import datetime, timedelta

        message_lower = message.lower()

        # Déterminer le type de liste demandé
        if 'annul' in message_lower:
            # Cours annulés
            occurrences = SessionOccurrence.objects.filter(
                is_cancelled=True,
                actual_date__gte=datetime.now().date() - timedelta(days=7)
            ).select_related('session_template__course', 'room', 'teacher').order_by('-actual_date', '-start_time')[:10]

            if not occurrences.exists():
                return {
                    'response': "Aucun cours annulé dans les 7 derniers jours.",
                    'intent': 'list_occurrences',
                    'confidence': 100,
                    'context_data': {'no_results': True},
                    'attachments': []
                }

            response = "📅 Cours annulés (7 derniers jours):\n\n"
            for occ in occurrences:
                response += f"• {occ.session_template.course.name}\n"
                response += f"  Date: {occ.actual_date.strftime('%d/%m/%Y')} à {occ.start_time.strftime('%H:%M')}\n"
                response += f"  Raison: {occ.cancellation_reason or 'Non spécifiée'}\n\n"

        elif 'modifi' in message_lower:
            # Cours modifiés
            occurrences = SessionOccurrence.objects.filter(
                actual_date__gte=datetime.now().date() - timedelta(days=7)
            ).filter(
                Q(is_room_modified=True) |
                Q(is_teacher_modified=True) |
                Q(is_time_modified=True)
            ).select_related('session_template__course', 'room', 'teacher').order_by('-actual_date', '-start_time')[:10]

            if not occurrences.exists():
                return {
                    'response': "Aucun cours modifié dans les 7 derniers jours.",
                    'intent': 'list_occurrences',
                    'confidence': 100,
                    'context_data': {'no_results': True},
                    'attachments': []
                }

            response = "📝 Cours modifiés (7 derniers jours):\n\n"
            for occ in occurrences:
                response += f"• {occ.session_template.course.name}\n"
                response += f"  Date: {occ.actual_date.strftime('%d/%m/%Y')} à {occ.start_time.strftime('%H:%M')}\n"
                modifications = []
                if occ.is_room_modified:
                    modifications.append(f"Salle: {occ.room.name}")
                if occ.is_teacher_modified:
                    modifications.append(f"Prof: {occ.teacher.user.get_full_name()}")
                if occ.is_time_modified:
                    modifications.append("Horaires")
                response += f"  Modifié: {', '.join(modifications)}\n\n"
        else:
            return {
                'response': "Voulez-vous voir les cours annulés ou modifiés?",
                'intent': 'list_occurrences',
                'confidence': 100,
                'context_data': {},
                'attachments': []
            }

        return {
            'response': response,
            'intent': 'list_occurrences',
            'confidence': 100,
            'context_data': {'count': len(occurrences)},
            'attachments': []
        }

    def _handle_navigate_to_schedule(self, message, user, context):
        """Navigation vers la page emploi du temps avec aide"""
        from courses.models_class import StudentClass

        message_lower = message.lower()

        # Chercher si une classe spécifique est mentionnée
        class_code = None
        words = message_lower.split()

        # Essayer de trouver un code de classe
        classes = StudentClass.objects.filter(is_active=True)
        for cls in classes:
            if cls.code.lower() in message_lower:
                class_code = cls.code
                break

        action = {
            'type': 'navigate',
            'route': '/schedule',
            'params': {}
        }

        if class_code:
            action['params']['class'] = class_code
            response_text = f"🚀 Parfait ! Je vous emmène sur l'emploi du temps de **{class_code}**"
        else:
            response_text = "🚀 C'est parti ! Direction la page emploi du temps !"

        # Ajouter des conseils contextuels
        response_text = self.add_contextual_tip(response_text, 'navigation')

        return {
            'response': response_text,
            'intent': 'navigate_to_schedule',
            'confidence': 100,
            'context_data': {'navigating': True, 'class_code': class_code},
            'attachments': [{'type': 'ui_action', 'action': action}]
        }

    def _handle_select_class(self, message, user, context):
        """Sélection d'une classe dans l'emploi du temps avec aide"""
        from courses.models_class import StudentClass

        message_lower = message.lower()

        # Extraire le code de la classe
        classes = StudentClass.objects.filter(is_active=True)
        class_code = None

        for cls in classes:
            if cls.code.lower() in message_lower:
                class_code = cls.code
                break

        if not class_code:
            # Liste les classes disponibles de manière sympathique
            class_list = "\n".join([f"  • **{cls.code}** - {cls.name}" for cls in classes[:10]])
            total_classes = classes.count()

            response = "🎓 Bien sûr ! Je peux vous aider à sélectionner une classe.\n\n"
            response += f"📚 **Classes disponibles** ({total_classes} au total) :\n\n{class_list}"

            if total_classes > 10:
                response += f"\n\n_... et {total_classes - 10} autres classes_"

            response += "\n\n💡 **Astuce** : Vous pouvez taper directement le code de la classe !"
            response += "\nExemple : 'L1MED' ou 'affiche L2INFO'"

            return {
                'response': response,
                'intent': 'select_class',
                'confidence': 100,
                'context_data': {'awaiting_class_code': True},
                'attachments': []
            }

        action = {
            'type': 'select_class',
            'class_code': class_code
        }

        # Chercher le nom complet de la classe
        class_obj = classes.filter(code=class_code).first()
        class_name = class_obj.name if class_obj else class_code

        response = f"✨ Parfait ! Affichage de l'emploi du temps de **{class_code}** ({class_name})"

        # Ajouter des conseils contextuels
        response = self.add_contextual_tip(response, 'schedule')

        return {
            'response': response,
            'intent': 'select_class',
            'confidence': 100,
            'context_data': {'class_selected': class_code},
            'attachments': [{'type': 'ui_action', 'action': action}]
        }

    def _handle_change_view_mode(self, message, user, context):
        """Changement du mode de vue (jour/semaine/mois)"""
        message_lower = message.lower()

        view_mode = None
        if 'jour' in message_lower:
            view_mode = 'day'
        elif 'semaine' in message_lower:
            view_mode = 'week'
        elif 'mois' in message_lower:
            view_mode = 'month'

        if not view_mode:
            return {
                'response': "Quel mode de vue voulez-vous?\n- Vue jour\n- Vue semaine\n- Vue mois",
                'intent': 'change_view_mode',
                'confidence': 100,
                'context_data': {},
                'attachments': []
            }

        view_names = {'day': 'Jour', 'week': 'Semaine', 'month': 'Mois'}

        action = {
            'type': 'change_view_mode',
            'mode': view_mode
        }

        return {
            'response': f"📅 Passage en vue {view_names[view_mode]}",
            'intent': 'change_view_mode',
            'confidence': 100,
            'context_data': {'view_mode': view_mode},
            'attachments': [{'type': 'ui_action', 'action': action}]
        }

    def _handle_filter_sessions(self, message, user, context):
        """Filtrage des sessions par type"""
        message_lower = message.lower()

        filter_type = None
        if 'cm' in message_lower:
            filter_type = 'CM'
        elif 'td' in message_lower:
            filter_type = 'TD'
        elif 'tp' in message_lower:
            filter_type = 'TP'
        elif 'tpe' in message_lower:
            filter_type = 'TPE'
        elif 'exam' in message_lower:
            filter_type = 'EXAM'

        if not filter_type:
            return {
                'response': "Quel type de session voulez-vous filtrer?\n- CM (Cours Magistraux)\n- TD (Travaux Dirigés)\n- TP (Travaux Pratiques)\n- TPE (Travaux Personnels Encadrés)\n- EXAM (Examens)",
                'intent': 'filter_sessions',
                'confidence': 100,
                'context_data': {},
                'attachments': []
            }

        action = {
            'type': 'filter_sessions',
            'filter': filter_type
        }

        return {
            'response': f"🔍 Filtrage par {filter_type}",
            'intent': 'filter_sessions',
            'confidence': 100,
            'context_data': {'filter': filter_type},
            'attachments': [{'type': 'ui_action', 'action': action}]
        }

    def _handle_show_statistics(self, message, user, context):
        """Affichage du panel de statistiques"""
        action = {
            'type': 'show_statistics',
            'show': True
        }

        return {
            'response': "📊 Affichage des statistiques",
            'intent': 'show_statistics',
            'confidence': 100,
            'context_data': {'showing_stats': True},
            'attachments': [{'type': 'ui_action', 'action': action}]
        }

    def _handle_toggle_edit_mode(self, message, user, context):
        """Activation/désactivation du mode édition"""
        message_lower = message.lower()

        # Vérifier les permissions
        agent = AgentActionService(user)
        if agent.user_role not in ['admin', 'teacher']:
            return {
                'response': "Désolé, seuls les administrateurs et enseignants peuvent activer le mode édition.",
                'intent': 'toggle_edit_mode',
                'confidence': 100,
                'context_data': {'permission_denied': True},
                'attachments': []
            }

        enable = True
        mode_type = 'edit'  # edit ou drag

        if 'desactiv' in message_lower or 'désactiv' in message_lower or 'vue' in message_lower:
            enable = False
        elif 'drag' in message_lower or 'déplac' in message_lower or 'deplac' in message_lower:
            mode_type = 'drag'

        if not enable:
            action = {
                'type': 'set_edit_mode',
                'mode': 'view'
            }
            response_text = "👁️ Passage en mode lecture seule"
        elif mode_type == 'drag':
            action = {
                'type': 'set_edit_mode',
                'mode': 'drag'
            }
            response_text = "🎯 Activation du mode drag & drop"
        else:
            action = {
                'type': 'set_edit_mode',
                'mode': 'edit'
            }
            response_text = "✏️ Activation du mode édition"

        return {
            'response': response_text,
            'intent': 'toggle_edit_mode',
            'confidence': 100,
            'context_data': {'edit_mode': mode_type if enable else 'view'},
            'attachments': [{'type': 'ui_action', 'action': action}]
        }

    def _handle_create_session_ui(self, message, user, context):
        """Ouverture du formulaire de création de session"""
        # Vérifier les permissions
        agent = AgentActionService(user)
        if agent.user_role not in ['admin', 'teacher']:
            return {
                'response': "Désolé, seuls les administrateurs et enseignants peuvent créer des sessions.",
                'intent': 'create_session',
                'confidence': 100,
                'context_data': {'permission_denied': True},
                'attachments': []
            }

        action = {
            'type': 'open_session_form',
            'mode': 'create'
        }

        return {
            'response': "➕ Ouverture du formulaire de création de session",
            'intent': 'create_session',
            'confidence': 100,
            'context_data': {'opening_form': True},
            'attachments': [{'type': 'ui_action', 'action': action}]
        }

    def _handle_export_schedule_ui(self, message, user, context):
        """Export de l'emploi du temps"""
        message_lower = message.lower()

        format_type = 'excel'  # par défaut
        if 'pdf' in message_lower:
            format_type = 'pdf'
        elif 'csv' in message_lower:
            format_type = 'csv'

        action = {
            'type': 'export_schedule',
            'format': format_type
        }

        return {
            'response': f"📥 Export de l'emploi du temps en {format_type.upper()}",
            'intent': 'export_schedule',
            'confidence': 100,
            'context_data': {'exporting': True, 'format': format_type},
            'attachments': [{'type': 'ui_action', 'action': action}]
        }

    def _get_suggested_questions(self):
        """Retourne des suggestions de questions frequentes"""
        return [
            "Quel est mon emploi du temps aujourd'hui ?",
            "Quels cours sont disponibles ?",
            "Ou se trouve la salle A101 ?",
            "Quand est mon prochain cours ?",
            "Y a-t-il des conflits d'horaire ?",
            "Combien de cours y a-t-il ?",
            "Cherche le cours de mathematiques",
            "Suggere-moi un meilleur horaire",
            "Comment exporter mon emploi du temps ?",
            "Genere un emploi du temps pour L1 Medecine",
            "Detecte les conflits dans les emplois du temps",
            "Evalue la qualite de l'emploi du temps",
            "Annule le cours de Math de demain",
            "Liste les cours annules",
            "Quels cours ont ete modifies?",
        ]
