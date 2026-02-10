"""
Dashboard app models – user page access control.
"""
from django.db import models
from django.conf import settings


# All dashboard page URL names that can be restricted.
DASHBOARD_PAGE_NAMES = [
    'leads_summary',
    'disbursal_summary',
    'collection_summary',
    'loan_count_wise',
    'daily_performance_metrics',
    'credit_person_wise',
    'sale_performance',
    'aum_report',
]


class UserProfile(models.Model):
    """
    Stores per-user allowed dashboard pages. If allowed_pages is empty/null,
    user has access to all pages (full access).
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dashboard_profile',
    )
    # List of url_name values the user can access. Empty = full access.
    allowed_pages = models.JSONField(
        default=list,
        blank=True,
        help_text='List of page URL names (e.g. leads_summary). Empty = full access.',
    )

    class Meta:
        db_table = 'dashboard_userprofile'

    def get_allowed_pages_list(self):
        """Return list of allowed url_names. Empty list means full access."""
        if not self.allowed_pages:
            return []
        return list(self.allowed_pages) if isinstance(self.allowed_pages, list) else []


def get_user_allowed_pages(user):
    """
    Return allowed page url_names for user. Returns None for "full access"
    (no profile or empty allowed_pages).
    """
    if not user or not user.is_authenticated:
        return None
    try:
        profile = user.dashboard_profile
    except Exception:
        return None
    pages = profile.get_allowed_pages_list()
    return None if pages == [] else pages


def user_can_access_page(user, url_name):
    """Return True if user is allowed to access the given page (url_name)."""
    allowed = get_user_allowed_pages(user)
    if allowed is None:
        return True  # full access
    return url_name in allowed


def get_first_allowed_url(user):
    """Return the URL path for the first allowed page, or '/' (disbursal) if full access."""
    from django.urls import reverse
    allowed = get_user_allowed_pages(user)
    if allowed is None:
        return '/'
    for name in DASHBOARD_PAGE_NAMES:
        if name in allowed:
            try:
                return reverse(name)
            except Exception:
                continue
    return '/'
