"""
URL configuration for blinker_edge project.
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from dashboard_app import views as dashboard_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', dashboard_views.custom_login, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    path('', include('dashboard_app.urls')),
]

