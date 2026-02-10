"""
Dashboard admin – manage user page access.
"""
from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from .models import UserProfile, DASHBOARD_PAGE_NAMES


User = get_user_model()

PAGE_CHOICES = [(name, name.replace('_', ' ').title()) for name in DASHBOARD_PAGE_NAMES]


class UserProfileForm(forms.ModelForm):
    allowed_pages = forms.MultipleChoiceField(
        choices=PAGE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Leave all unchecked for full access. Check only the tabs this user may see.',
    )

    class Meta:
        model = UserProfile
        fields = ('user', 'allowed_pages')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['allowed_pages'] = self.instance.get_allowed_pages_list() or []

    def clean_allowed_pages(self):
        return list(self.cleaned_data.get('allowed_pages') or [])

    def save(self, commit=True):
        inst = super().save(commit=False)
        inst.allowed_pages = self.cleaned_data.get('allowed_pages') or []
        if commit:
            inst.save()
        return inst


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    form = UserProfileForm
    can_delete = True
    verbose_name = 'Dashboard access'
    verbose_name_plural = 'Dashboard access'
    fields = ('allowed_pages',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    form = UserProfileForm
    list_display = ('user', 'allowed_pages_display')
    list_filter = ()
    search_fields = ('user__username', 'user__email')
    raw_id_fields = ('user',)

    def allowed_pages_display(self, obj):
        pages = obj.get_allowed_pages_list()
        return 'Full access' if not pages else ', '.join(pages)
    allowed_pages_display.short_description = 'Allowed pages'

    def save_model(self, request, obj, form, change):
        obj.allowed_pages = form.cleaned_data.get('allowed_pages') or []
        super().save_model(request, obj, form, change)


# Optionally extend the default User admin to show UserProfile inline
try:
    admin.site.unregister(User)
except Exception:
    pass


class UserAdminWithProfile(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = BaseUserAdmin.list_display + ('has_restricted_access',)

    def has_restricted_access(self, obj):
        try:
            p = obj.dashboard_profile
            return bool(p.get_allowed_pages_list())
        except Exception:
            return False
    has_restricted_access.boolean = True
    has_restricted_access.short_description = 'Restricted'


admin.site.register(User, UserAdminWithProfile)
