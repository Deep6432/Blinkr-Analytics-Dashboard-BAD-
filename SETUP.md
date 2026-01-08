# Quick Setup Guide

## 1. Install Required Django App

Add `django.contrib.humanize` to your `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    # ... other apps
    'django.contrib.humanize',  # Required for intcomma filter
]
```

## 2. Configure Static Files

Ensure static files are configured in `settings.py`:

```python
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
```

## 3. URL Configuration

Add these URL patterns to your main `urls.py`:

```python
from django.urls import path
from . import views

urlpatterns = [
    path('disbursal-summary/', views.disbursal_summary, name='disbursal_summary'),
    path('collection-without-fraud/', views.collection_without_fraud, name='collection_without_fraud'),
    path('collection-with-fraud/', views.collection_with_fraud, name='collection_with_fraud'),
    path('loan-count-wise/', views.loan_count_wise, name='loan_count_wise'),
    path('daily-performance-metrics/', views.daily_performance_metrics, name='daily_performance_metrics'),
    path('credit-person-wise/', views.credit_person_wise, name='credit_person_wise'),
    path('aum-report/', views.aum_report, name='aum_report'),
    path('logout/', views.logout_view, name='logout'),  # Or use Django's built-in logout
]
```

## 4. View Template

Your views should return context with these variables (see `views_example.py` for full example):

**Required for KPI Cards:**
- `total_records`, `fresh_count`, `reloan_count`
- `total_loan_amount`, `fresh_loan_amount`, `reloan_loan_amount`
- `total_disbursal_amount`, `fresh_disbursal_amount`, `reloan_disbursal_amount`
- `processing_fee`, `fresh_processing_fee`, `reloan_processing_fee`
- `interest_amount`, `fresh_interest_amount`, `reloan_interest_amount`
- `repayment_amount`, `fresh_repayment_amount`, `reloan_repayment_amount`

**Required for Charts:**
- `state_labels`: JSON string array (e.g., `json.dumps(['Maharashtra', 'Karnataka'])`)
- `state_values`: JSON string array (e.g., `json.dumps([2500000, 1800000])`)
- `city_labels`: JSON string array
- `city_values`: JSON string array

**Optional:**
- `states`: List of state names for filter dropdown
- `cities`: List of city names for filter dropdown
- `products`: List of product names for filter dropdown
- `credit_persons`: List of credit person names for filter dropdown
- `last_updated`: Timestamp string

## 5. Template Usage

In your view template (e.g., `disbursal_summary.html`):

```django
{% extends 'dashboard/base.html' %}
{% load static %}
{% load humanize %}

{% block title %}Disbursal Summary{% endblock %}
{% block page_title %}Disbursal Summary{% endblock %}
{% block page_subtitle %}Advanced performance insights{% endblock %}

{% block content %}
    <!-- Your page-specific content -->
{% endblock %}
```

## 6. Testing

1. Start your Django development server: `python manage.py runserver`
2. Navigate to `/disbursal-summary/` (or your configured URL)
3. Verify:
   - Top bar displays correctly
   - Sidebar navigation works
   - Filters panel is collapsible
   - KPI cards show data
   - Charts render (if data provided)
   - Refresh controls work

## Troubleshooting

**Issue: `intcomma` filter not found**
- Solution: Ensure `django.contrib.humanize` is in `INSTALLED_APPS`

**Issue: Static files not loading**
- Solution: Run `python manage.py collectstatic` (if using production) or check `STATICFILES_DIRS` in settings

**Issue: Charts not rendering**
- Solution: Check browser console for errors. Ensure chart data is provided as JSON strings in context.

**Issue: URLs not found**
- Solution: Ensure all URL names match exactly (e.g., `disbursal_summary` not `disbursal-summary`)

## Next Steps

1. Copy view functions from `templates/dashboard/views_example.py` to your actual `views.py`
2. Replace example data with your actual database queries
3. Customize colors and spacing in `static/dashboard/styles.css`
4. Add additional pages by creating new templates in `templates/dashboard/pages/`

