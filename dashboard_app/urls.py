"""
URL configuration for dashboard_app.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.disbursal_summary, name='disbursal_summary'),
    path('dashboard/', views.disbursal_summary, name='dashboard'),  # Add dashboard route
    path('disbursal-summary/', views.disbursal_summary, name='disbursal_summary'),
    path('api/disbursal-data/', views.disbursal_data_api, name='disbursal_data_api'),  # API endpoint for AJAX refresh
    path('api/disbursal-records/', views.disbursal_records_api, name='disbursal_records_api'),  # API endpoint for records table
    path('api/prepayment-records/', views.prepayment_records_api, name='prepayment_records_api'),  # API endpoint for prepayment records table
    path('api/on-time-records/', views.on_time_records_api, name='on_time_records_api'),  # API endpoint for on_time records table
    path('api/overdue-records/', views.overdue_records_api, name='overdue_records_api'),  # API endpoint for overdue records table
    path('collection-summary/', views.collection_without_fraud, name='collection_summary'),
    path('collection-without-fraud/', views.collection_without_fraud, name='collection_without_fraud'),  # Keep for backward compatibility
    path('collection-with-fraud/', views.collection_with_fraud, name='collection_with_fraud'),  # Keep for backward compatibility
    path('loan-count-wise/', views.loan_count_wise, name='loan_count_wise'),
    path('daily-performance-metrics/', views.daily_performance_metrics, name='daily_performance_metrics'),
    path('credit-person-wise/', views.credit_person_wise, name='credit_person_wise'),
    path('aum-report/', views.aum_report, name='aum_report'),
]

