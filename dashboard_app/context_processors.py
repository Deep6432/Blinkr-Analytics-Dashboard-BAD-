"""
Context processors for dashboard – expose user page access to templates.
"""
from .models import get_user_allowed_pages, DASHBOARD_PAGE_NAMES


def dashboard_access(request):
    """
    Add user_allowed_pages to template context.
    - None = full access (show all tabs).
    - List of url_names = restricted (show only those tabs).
    """
    allowed = get_user_allowed_pages(request.user) if request.user.is_authenticated else None
    return {
        'user_allowed_pages': allowed,
        'dashboard_page_names': DASHBOARD_PAGE_NAMES,
    }
