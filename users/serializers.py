# users/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import UserProfile, UserSession, LoginAttempt, CustomPermission


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer pour les profils utilisateur"""
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user_username', 'user_email', 'user_full_name',
            'role', 'phone', 'address', 'avatar', 'date_of_birth',
            'language', 'timezone', 'email_notifications', 'sms_notifications',
            'is_verified', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_verified']


class UserSessionSerializer(serializers.ModelSerializer):
    """Serializer pour les sessions utilisateur"""
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = UserSession
        fields = [
            'id', 'user_username', 'session_key', 'ip_address', 
            'user_agent', 'location', 'is_active', 'created_at', 'last_activity'
        ]
        read_only_fields = ['id', 'created_at', 'last_activity']


class LoginAttemptSerializer(serializers.ModelSerializer):
    """Serializer pour l'historique des connexions"""
    
    class Meta:
        model = LoginAttempt
        fields = [
            'id', 'username', 'ip_address', 'user_agent', 
            'success', 'failure_reason', 'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer pour l'inscription d'un nouvel utilisateur"""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES, required=False, default='student')
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password', 'password_confirm', 'role']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Les mots de passe ne correspondent pas.")
        return attrs
    
    def create(self, validated_data):
        # Retirer password_confirm et role des données
        validated_data.pop('password_confirm')
        role = validated_data.pop('role', 'student')
        
        # Créer l'utilisateur
        user = User.objects.create_user(**validated_data)
        
        # Mettre à jour le profil avec le rôle
        if hasattr(user, 'profile'):
            user.profile.role = role
            user.profile.save()
        
        return user


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer pour le changement de mot de passe"""
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("Les nouveaux mots de passe ne correspondent pas.")
        return attrs


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour du profil"""
    
    class Meta:
        model = UserProfile
        fields = [
            'phone', 'address', 'date_of_birth', 'language', 
            'timezone', 'email_notifications', 'sms_notifications'
        ]
    
    def validate_phone(self, value):
        """Validation du numéro de téléphone"""
        if value and not value.startswith(('+237', '237', '6', '2')):
            raise serializers.ValidationError("Format de téléphone camerounais invalide.")
        return value


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'utilisateurs"""
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES, required=False, default='student', write_only=True)

    # Champs pour les enseignants
    department_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    employee_id = serializers.CharField(required=False, allow_blank=True, write_only=True)
    phone = serializers.CharField(required=False, allow_blank=True, write_only=True)
    office = serializers.CharField(required=False, allow_blank=True, write_only=True)
    max_hours_per_week = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    # Champs pour les étudiants
    student_data = serializers.DictField(required=False, write_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'password', 'is_active', 'role', 'department_id', 'employee_id',
            'phone', 'office', 'max_hours_per_week', 'student_data'
        ]
        read_only_fields = ['id']

    def validate_employee_id(self, value):
        """Valider que l'employee_id est unique s'il est fourni"""
        if value:
            if UserProfile.objects.filter(employee_id=value).exists():
                raise serializers.ValidationError(
                    "Un utilisateur avec cet identifiant employé existe déjà."
                )
        return value

    def validate_student_data(self, value):
        """Valider les données de l'étudiant"""
        if value:
            from courses.models import Student
            # Vérifier si le student_id est unique
            student_id = value.get('student_id')
            if student_id and Student.objects.filter(student_id=student_id).exists():
                raise serializers.ValidationError(
                    {'student_id': "Un étudiant avec ce matricule existe déjà."}
                )
        return value

    def create(self, validated_data):
        from courses.models import Department, Teacher, Student, Curriculum, Course, CourseEnrollment
        from courses.models_class import StudentClass

        # Extraire les données du profil
        role = validated_data.pop('role', 'student')
        department_id = validated_data.pop('department_id', None)
        employee_id = validated_data.pop('employee_id', '')

        # Extraire les champs spécifiques Teacher
        phone = validated_data.pop('phone', '')
        office = validated_data.pop('office', '')
        max_hours_per_week = validated_data.pop('max_hours_per_week', 20)

        # Extraire les données de l'étudiant
        student_data = validated_data.pop('student_data', None)

        # Créer l'utilisateur
        user = User.objects.create_user(**validated_data)

        # Récupérer le département si fourni
        department = None
        if department_id:
            try:
                department = Department.objects.get(id=department_id)
            except Department.DoesNotExist:
                pass

        # Générer un employee_id unique si nécessaire
        if not employee_id and (role in ['teacher', 'professor']):
            # Générer un ID unique basé sur le rôle et l'ID utilisateur
            base_id = f"{role.upper()[:3]}-{user.id}"
            employee_id = base_id

            # Vérifier si cet ID existe déjà et ajouter un suffixe si nécessaire
            counter = 1
            while UserProfile.objects.filter(employee_id=employee_id).exists():
                employee_id = f"{base_id}-{counter}"
                counter += 1

        # Créer le profil
        if hasattr(user, 'profile'):
            user.profile.role = role
            # Ne définir employee_id que s'il n'est pas vide
            if employee_id:
                user.profile.employee_id = employee_id
            user.profile.department = department
            user.profile.save()
        else:
            profile_data = {
                'user': user,
                'role': role,
                'department': department
            }
            # Ne définir employee_id que s'il n'est pas vide
            if employee_id:
                profile_data['employee_id'] = employee_id
            UserProfile.objects.create(**profile_data)

        # Si le rôle est 'teacher' ou 'professor', créer automatiquement le Teacher
        if role in ['teacher', 'professor']:
            # Vérifier si un Teacher existe déjà pour cet utilisateur
            teacher_exists = Teacher.objects.filter(user=user).exists()

            # Ne créer le Teacher que s'il n'existe pas déjà
            if not teacher_exists:
                # Récupérer ou créer le département par défaut si nécessaire
                if not department:
                    department, _ = Department.objects.get_or_create(
                        code='DEFAULT',
                        defaults={
                            'name': 'Département par défaut',
                            'description': 'Département par défaut pour les enseignants'
                        }
                    )

                # S'assurer que l'employee_id pour Teacher est également unique
                teacher_employee_id = employee_id or f'TEACH-{user.id}'
                counter = 1
                while Teacher.objects.filter(employee_id=teacher_employee_id).exists():
                    teacher_employee_id = f"{employee_id or f'TEACH-{user.id}'}-{counter}"
                    counter += 1

                # Créer le Teacher avec tous les champs
                Teacher.objects.create(
                    user=user,
                    employee_id=teacher_employee_id,
                    department=department,
                    phone=phone,
                    office=office,
                    max_hours_per_week=max_hours_per_week,
                    is_active=user.is_active
                )

        # Si le rôle est 'student', créer automatiquement le Student
        elif role == 'student' and student_data:
            try:
                # Récupérer la classe
                student_class_id = student_data.get('student_class_id')
                if not student_class_id:
                    raise ValueError("La classe est requise pour créer un étudiant")

                student_class = StudentClass.objects.select_related('curriculum', 'department').get(id=student_class_id)

                # Extraire le niveau de la classe
                current_level = student_class.level

                # Utiliser le curriculum de la classe
                # Si la classe n'a pas de curriculum, créer ou récupérer le curriculum par défaut
                curriculum = student_class.curriculum
                if not curriculum:
                    # Si la classe n'a pas de curriculum, assigner le curriculum par défaut du département
                    if student_class.department:
                        curriculum, created = Curriculum.objects.get_or_create(
                            department=student_class.department,
                            code=f"{student_class.department.code}-DEFAULT",
                            defaults={
                                'name': f"Cursus {student_class.department.name}",
                                'level': current_level,
                                'total_credits': 180,
                                'description': f"Cursus par défaut pour {student_class.department.name}",
                                'academic_year': '2024-2025'
                            }
                        )
                        # Assigner ce curriculum à la classe pour éviter les problèmes futurs
                        student_class.curriculum = curriculum
                        student_class.save()
                    else:
                        # Curriculum générique si pas de département
                        default_dept, _ = Department.objects.get_or_create(
                            code='DEFAULT',
                            defaults={
                                'name': 'Département par défaut',
                                'description': 'Département par défaut'
                            }
                        )
                        curriculum, created = Curriculum.objects.get_or_create(
                            code='DEFAULT',
                            defaults={
                                'name': 'Cursus Général',
                                'department': default_dept,
                                'level': current_level,
                                'total_credits': 180,
                                'description': 'Cursus par défaut',
                                'academic_year': '2024-2025'
                            }
                        )
                        # Assigner ce curriculum à la classe
                        student_class.curriculum = curriculum
                        student_class.save()

                # Créer le profil étudiant
                student = Student.objects.create(
                    user=user,
                    student_id=student_data.get('student_id'),
                    curriculum=curriculum,
                    current_level=current_level,
                    entry_year=student_data.get('entry_year', 2025),
                    phone=student_data.get('phone', ''),
                    address=student_data.get('address', ''),
                    emergency_contact=student_data.get('emergency_contact', ''),
                    emergency_phone=student_data.get('emergency_phone', ''),
                    is_active=user.is_active
                )

                # Incrémenter le nombre d'étudiants dans la classe
                student_class.student_count += 1
                student_class.save()

                # Inscrire automatiquement l'étudiant aux cours de sa classe
                from courses.models_class import ClassCourse

                class_courses = ClassCourse.objects.filter(
                    student_class=student_class,
                    is_active=True
                ).select_related('course')

                enrolled_count = 0
                for class_course in class_courses:
                    CourseEnrollment.objects.get_or_create(
                        student=student,
                        course=class_course.course,
                        defaults={
                            'academic_year': student_class.academic_year or '2024-2025',
                            'semester': 'S1',
                            'is_active': True
                        }
                    )
                    enrolled_count += 1

            except (StudentClass.DoesNotExist, KeyError, ValueError) as e:
                # Si la création de l'étudiant échoue, supprimer l'utilisateur créé
                user.delete()
                raise serializers.ValidationError(
                    f"Erreur lors de la création de l'étudiant: {str(e)}"
                )

        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour d'utilisateurs"""
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES, required=False, write_only=True)
    department_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    employee_id = serializers.CharField(required=False, allow_blank=True, allow_null=True, write_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'role', 'department_id', 'employee_id'
        ]
        read_only_fields = ['id']
        
    def validate_employee_id(self, value):
        """Valider que l'employee_id est unique s'il est fourni"""
        if value:
            # Vérifier si un autre utilisateur a déjà cet employee_id
            instance = self.instance
            if UserProfile.objects.filter(employee_id=value).exclude(user=instance).exists():
                raise serializers.ValidationError(
                    "Un autre utilisateur avec cet identifiant employé existe déjà."
                )
        return value

    def update(self, instance, validated_data):
        """Mise à jour d'un utilisateur et son profil"""
        from courses.models import Department, Teacher

        # Extraire les données du profil
        role = validated_data.pop('role', None)
        department_id = validated_data.pop('department_id', None)
        employee_id = validated_data.pop('employee_id', None)

        # Sauvegarder l'ancien rôle pour détecter les changements
        old_role = instance.profile.role if hasattr(instance, 'profile') else None

        # Mettre à jour les champs de base
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.is_active = validated_data.get('is_active', instance.is_active)
        instance.save()

        # Récupérer le département si fourni
        department = None
        if department_id is not None:
            try:
                department = Department.objects.get(id=department_id)
            except Department.DoesNotExist:
                pass

        # Mettre à jour le profil si nécessaire
        if hasattr(instance, 'profile'):
            if role is not None:
                instance.profile.role = role

            if employee_id is not None:
                instance.profile.employee_id = employee_id

            if department is not None or department_id is not None:
                instance.profile.department = department

            instance.profile.save()

        # Gérer le changement de rôle vers 'teacher' ou 'professor'
        new_role = role if role is not None else old_role

        if new_role in ['teacher', 'professor'] and old_role not in ['teacher', 'professor']:
            # L'utilisateur devient enseignant, créer le Teacher s'il n'existe pas
            try:
                Teacher.objects.get(user=instance)
            except Teacher.DoesNotExist:
                # Récupérer ou créer le département par défaut si nécessaire
                if not department and not instance.profile.department:
                    department, _ = Department.objects.get_or_create(
                        code='DEFAULT',
                        defaults={
                            'name': 'Département par défaut',
                            'description': 'Département par défaut pour les enseignants'
                        }
                    )
                else:
                    department = department or instance.profile.department

                # S'assurer que l'employee_id pour Teacher est unique
                teacher_employee_id = instance.profile.employee_id or f'TEACH-{instance.id}'
                counter = 1
                while Teacher.objects.filter(employee_id=teacher_employee_id).exists():
                    teacher_employee_id = f"{instance.profile.employee_id or f'TEACH-{instance.id}'}-{counter}"
                    counter += 1

                # Créer le Teacher
                Teacher.objects.create(
                    user=instance,
                    employee_id=teacher_employee_id,
                    department=department,
                    is_active=instance.is_active
                )

        elif new_role not in ['teacher', 'professor'] and old_role in ['teacher', 'professor']:
            # L'utilisateur n'est plus enseignant, supprimer le Teacher
            try:
                teacher = Teacher.objects.get(user=instance)
                teacher.delete()
            except Teacher.DoesNotExist:
                pass

        return instance


class UserDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour les utilisateurs"""
    profile = UserProfileSerializer(read_only=True)
    role = serializers.SerializerMethodField()
    department_id = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    employee_id = serializers.SerializerMethodField()
    teacher_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'is_staff', 'is_superuser', 'last_login',
            'date_joined', 'profile', 'role', 'department_id',
            'department_name', 'employee_id', 'teacher_id'
        ]
        read_only_fields = ['id', 'last_login', 'date_joined', 'username']

    def get_role(self, obj):
        """Détermine le rôle de l'utilisateur"""
        if obj.is_superuser or obj.is_staff:
            return 'admin'

        # Vérifier si l'utilisateur a un profil
        if hasattr(obj, 'profile') and obj.profile:
            return obj.profile.role

        # Par défaut, retourner 'student'
        return 'student'

    def get_department_id(self, obj):
        """Récupère l'ID du département"""
        if hasattr(obj, 'profile') and obj.profile and obj.profile.department:
            return obj.profile.department.id
        return None

    def get_department_name(self, obj):
        """Récupère le nom du département"""
        if hasattr(obj, 'profile') and obj.profile and obj.profile.department:
            return obj.profile.department.name
        return None

    def get_employee_id(self, obj):
        """Récupère l'ID employé"""
        if hasattr(obj, 'profile') and obj.profile:
            return obj.profile.employee_id
        return None

    def get_teacher_id(self, obj):
        """Récupère l'ID du Teacher associé à l'utilisateur (pour les enseignants)"""
        try:
            from courses.models import Teacher
            teacher = Teacher.objects.get(user=obj)
            return teacher.id
        except Teacher.DoesNotExist:
            return None


class CustomPermissionSerializer(serializers.ModelSerializer):
    """Serializer pour les permissions personnalisées"""
    
    class Meta:
        model = CustomPermission
        fields = ['id', 'name', 'codename', 'description', 'category']
        read_only_fields = ['id']