# Edge Analytics Dashboard - UI Redesign

A modern, enterprise-grade analytics dashboard UI built with Django templates, Tailwind CSS, and Chart.js. Inspired by Stripe Dashboard, Linear, and Vercel Analytics.

## Features

- ✨ **Modern Design**: Clean, minimal, premium enterprise SaaS style
- 🌙 **Dark Mode**: Default dark theme with optional light mode support
- 📱 **Fully Responsive**: Desktop-first design that works on tablet and mobile
- ♿ **Accessible**: Keyboard navigation, focus rings, proper color contrast
- 🎨 **Design System**: Consistent spacing, typography, and color tokens
- 📊 **Interactive Charts**: Chart.js powered visualizations with custom legends
- 🔄 **Auto Refresh**: Configurable refresh intervals (10s, 30s, 60s, manual)
- 🎯 **Progressive Enhancement**: HTMX support for seamless updates

## Project Structure

```
templates/dashboard/
├── base.html                    # Main layout shell
├── partials/
│   ├── _topbar.html            # Top navigation bar
│   ├── _sidebar.html           # Left sidebar navigation
│   ├── _filters.html           # Filter panel with chips
│   └── _kpi_cards.html         # KPI metrics cards
└── pages/
    └── disbursal_summary.html  # Disbursal summary page

static/dashboard/
├── styles.css                  # Custom CSS with design tokens
└── dashboard.js                # Main JavaScript for interactions
```

## Setup Instructions

### 1. Install Dependencies

Ensure your Django project has the following apps in `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    'django.contrib.humanize',  # For number formatting (intcomma filter)
    # ... your other apps
]
```

### 2. Configure Static Files

In your `settings.py`:

```python
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
```

### 3. URL Configuration

Add URLs for all dashboard pages:

```python
# urls.py
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
]
```

### 4. View Example

Here's a sample view for the Disbursal Summary page:

```python
# views.py
from django.shortcuts import render
from django.contrib.humanize.templatetags.humanize import intcomma
import json

def disbursal_summary(request):
    # Your existing data fetching logic here
    # Example context variables:
    
    context = {
        # KPI Metrics
        'total_records': 235,
        'fresh_count': 43,
        'reloan_count': 192,
        
        'total_loan_amount': 6791913,
        'fresh_loan_amount': 1222415,
        'reloan_loan_amount': 5569498,
        
        'total_disbursal_amount': 6063616,
        'fresh_disbursal_amount': 1076901,
        'reloan_disbursal_amount': 4986715,
        
        'processing_fee': 612334,
        'fresh_processing_fee': 122240,
        'reloan_processing_fee': 490094,
        
        'interest_amount': 1935792,
        'fresh_interest_amount': 353621,
        'reloan_interest_amount': 1582171,
        
        'repayment_amount': 8727705,
        'fresh_repayment_amount': 1576036,
        'reloan_repayment_amount': 7151669,
        
        # Chart Data (as JSON-safe strings)
        'state_labels': json.dumps(['Maharashtra', 'Karnataka', 'Telangana', 'Haryana', 'Delhi']),
        'state_values': json.dumps([2500000, 1800000, 1200000, 800000, 500000]),
        
        'city_labels': json.dumps(['Bengaluru Urban', 'Pune', 'Mumbai Suburban', 'Gurugram']),
        'city_values': json.dumps([1500000, 1200000, 1000000, 800000]),
        
        # Filter Options
        'states': ['Maharashtra', 'Karnataka', 'Telangana', 'Haryana', 'Delhi'],
        'cities': ['Bengaluru Urban', 'Pune', 'Mumbai Suburban', 'Gurugram'],
        
        # Last Updated
        'last_updated': '2026-01-03 14:30:00',
    }
    
    return render(request, 'dashboard/pages/disbursal_summary.html', context)
```

### 5. Template Usage

In your view templates, extend the base template:

```django
{% extends 'dashboard/base.html' %}
{% load static %}
{% load humanize %}

{% block title %}Your Page Title{% endblock %}
{% block page_title %}Your Page Title{% endblock %}
{% block page_subtitle %}Your page description{% endblock %}

{% block content %}
    <!-- Your page-specific content here -->
{% endblock %}
```

## Data Format Requirements

### KPI Cards
The KPI cards partial expects these context variables:
- `total_records`, `fresh_count`, `reloan_count`
- `total_loan_amount`, `fresh_loan_amount`, `reloan_loan_amount`
- `total_disbursal_amount`, `fresh_disbursal_amount`, `reloan_disbursal_amount`
- `processing_fee`, `fresh_processing_fee`, `reloan_processing_fee`
- `interest_amount`, `fresh_interest_amount`, `reloan_interest_amount`
- `repayment_amount`, `fresh_repayment_amount`, `reloan_repayment_amount`

### Charts
Charts require JSON-safe arrays:
- `state_labels`: JSON array of state names
- `state_values`: JSON array of numeric values
- `city_labels`: JSON array of city names
- `city_values`: JSON array of numeric values

Example in view:
```python
import json
context['state_labels'] = json.dumps(['Maharashtra', 'Karnataka'])
context['state_values'] = json.dumps([2500000, 1800000])
```

## Customization

### Colors
Edit CSS variables in `static/dashboard/styles.css`:
```css
:root {
    --accent-blue: #3b82f6;
    --accent-purple: #8b5cf6;
    --accent-green: #10b981;
}
```

### Spacing & Typography
Adjust design tokens in `styles.css`:
```css
:root {
    --space-4: 1rem;     /* 16px */
    --radius-md: 0.875rem; /* 14px */
}
```

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

## Accessibility

- WCAG 2.1 AA compliant color contrast
- Keyboard navigation support
- Focus indicators on interactive elements
- Screen reader friendly markup
- Reduced motion support

## Performance

- Lazy loading for charts
- Optimized CSS with minimal custom styles
- CDN-based dependencies (Tailwind, Chart.js, HTMX)
- Efficient DOM updates with HTMX

## License

This UI redesign is part of the Blinker Edge Analytics Dashboard project.

