# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from .models import UserProfile, UserSession, LoginAttempt, CustomPermission


class UserProfileInline(admin.StackedInline):
    """Inline pour le profil utilisateur"""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profil'
    fk_name = 'user'

    fieldsets = (
        ('Informations Professionnelles', {
            'fields': ('role', 'employee_id', 'department')
        }),
        ('Contact', {
            'fields': ('phone', 'address', 'date_of_birth')
        }),
        ('Avatar', {
            'fields': ('avatar',),
            'classes': ('collapse',)
        }),
        ('Préférences', {
            'fields': ('language', 'timezone', 'email_notifications', 'sms_notifications'),
            'classes': ('collapse',)
        }),
        ('Sécurité', {
            'fields': ('last_login_ip', 'failed_login_attempts', 'account_locked_until', 'is_verified'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('last_login_ip', 'failed_login_attempts', 'account_locked_until', 'is_verified')


class CustomUserAdmin(BaseUserAdmin):
    """Administration personnalisée des utilisateurs"""
    inlines = (UserProfileInline,)

    list_display = ('username', 'email', 'get_full_name', 'get_role', 'get_department', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'profile__role', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'profile__employee_id')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {
            'fields': ('username', 'password')
        }),
        ('Informations Personnelles', {
            'fields': ('first_name', 'last_name', 'email')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Dates Importantes', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )

    def get_full_name(self, obj):
        """Retourne le nom complet"""
        return obj.get_full_name() or '-'
    get_full_name.short_description = 'Nom Complet'

    def get_role(self, obj):
        """Retourne le rôle de l'utilisateur"""
        if obj.is_superuser:
            return format_html('<span style="color: red; font-weight: bold;">SUPERADMIN</span>')
        if obj.is_staff:
            return format_html('<span style="color: orange; font-weight: bold;">ADMIN</span>')
        if hasattr(obj, 'profile') and obj.profile:
            role_colors = {
                'teacher': 'blue',
                'student': 'purple',
                'staff': 'green',
                'department_head': 'darkorange',
                'scheduler': 'teal'
            }
            color = role_colors.get(obj.profile.role, 'gray')
            label = obj.profile.get_role_display()
            return format_html('<span style="color: {};">{}</span>', color, label)
        return '-'
    get_role.short_description = 'Rôle'

    def get_department(self, obj):
        """Retourne le département"""
        if hasattr(obj, 'profile') and obj.profile and obj.profile.department:
            return obj.profile.department.name
        return '-'
    get_department.short_description = 'Département'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Administration des profils utilisateur"""
    list_display = ('user', 'role', 'employee_id', 'department', 'phone', 'is_verified', 'created_at')
    list_filter = ('role', 'is_verified', 'email_notifications', 'sms_notifications', 'created_at')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name', 'employee_id', 'phone')
    readonly_fields = ('created_at', 'updated_at', 'last_login_ip', 'failed_login_attempts')

    fieldsets = (
        ('Utilisateur', {
            'fields': ('user',)
        }),
        ('Informations Professionnelles', {
            'fields': ('role', 'employee_id', 'department')
        }),
        ('Contact', {
            'fields': ('phone', 'address', 'date_of_birth')
        }),
        ('Avatar', {
            'fields': ('avatar',)
        }),
        ('Préférences', {
            'fields': ('language', 'timezone', 'email_notifications', 'sms_notifications')
        }),
        ('Sécurité', {
            'fields': ('is_verified', 'verification_token', 'last_login_ip', 'failed_login_attempts', 'account_locked_until')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """Administration des sessions utilisateur"""
    list_display = ('user', 'session_key_short', 'ip_address', 'location', 'is_active', 'created_at', 'last_activity')
    list_filter = ('is_active', 'created_at', 'last_activity')
    search_fields = ('user__username', 'user__email', 'session_key', 'ip_address', 'location')
    readonly_fields = ('user', 'session_key', 'ip_address', 'user_agent', 'location', 'created_at', 'last_activity')
    date_hierarchy = 'created_at'

    def session_key_short(self, obj):
        """Affiche une version courte de la clé de session"""
        return f"{obj.session_key[:8]}..."
    session_key_short.short_description = 'Session'

    def has_add_permission(self, request):
        """Empêcher l'ajout manuel de sessions"""
        return False


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Administration de l'historique des connexions"""
    list_display = ('username', 'ip_address', 'success', 'failure_reason', 'timestamp')
    list_filter = ('success', 'timestamp')
    search_fields = ('username', 'ip_address')
    readonly_fields = ('username', 'ip_address', 'user_agent', 'success', 'failure_reason', 'timestamp')
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        """Empêcher l'ajout manuel de tentatives"""
        return False

    def has_change_permission(self, request, obj=None):
        """Empêcher la modification des tentatives"""
        return False


@admin.register(CustomPermission)
class CustomPermissionAdmin(admin.ModelAdmin):
    """Administration des permissions personnalisées"""
    list_display = ('name', 'codename', 'category', 'description')
    list_filter = ('category',)
    search_fields = ('name', 'codename', 'description')

    fieldsets = (
        (None, {
            'fields': ('name', 'codename', 'category')
        }),
        ('Description', {
            'fields': ('description',)
        }),
    )


# Désenregistrer le UserAdmin par défaut et enregistrer le personnalisé
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# Personnalisation du site admin
admin.site.site_header = "Administration OAPET"
admin.site.site_title = "OAPET Admin"
admin.site.index_title = "Bienvenue dans l'administration OAPET"
