"""
Decorators for dashboard – page access control.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required as django_login_required

from .models import user_can_access_page, get_first_allowed_url


def require_page_access(view_func):
    """
    Use after @login_required. Redirects to first allowed page if user
    cannot access this view's page; otherwise calls the view.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        url_name = request.resolver_match.url_name if request.resolver_match else None
        if url_name and not user_can_access_page(request.user, url_name):
            first_url = get_first_allowed_url(request.user)
            return redirect(first_url)
        return view_func(request, *args, **kwargs)
    return _wrapped


def login_required(view_func):
    """Login required + page access check for dashboard pages."""
    @wraps(view_func)
    @django_login_required
    @require_page_access
    def _wrapped(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return _wrapped
