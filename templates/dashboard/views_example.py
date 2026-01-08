"""
Example Django views for the Edge Analytics Dashboard

This file shows how to structure your views to work with the new dashboard templates.
Copy the relevant view functions to your actual views.py file.
"""

from django.shortcuts import render
from django.contrib.humanize.templatetags.humanize import intcomma
from django.utils import timezone
import json


def disbursal_summary(request):
    """
    Disbursal Summary page view
    
    Replace the example data with your actual database queries.
    """
    # TODO: Replace with your actual data fetching logic
    # Example: data = YourModel.objects.filter(...)
    
    # Prepare chart data as JSON-safe strings
    state_data = {
        'Maharashtra': 2500000,
        'Karnataka': 1800000,
        'Telangana': 1200000,
        'Haryana': 800000,
        'Delhi': 500000,
        # ... more states
    }
    
    city_data = {
        'Bengaluru Urban (Karnataka)': 1500000,
        'Pune (Maharashtra)': 1200000,
        'Mumbai Suburban (Maharashtra)': 1000000,
        'Gurugram (Haryana)': 800000,
        # ... more cities
    }
    
    context = {
        # KPI Metrics - Total Records
        'total_records': 235,
        'fresh_count': 43,
        'reloan_count': 192,
        
        # KPI Metrics - Loan Amounts
        'total_loan_amount': 6791913,
        'fresh_loan_amount': 1222415,
        'reloan_loan_amount': 5569498,
        
        # KPI Metrics - Disbursal Amounts
        'total_disbursal_amount': 6063616,
        'fresh_disbursal_amount': 1076901,
        'reloan_disbursal_amount': 4986715,
        
        # KPI Metrics - Processing Fee
        'processing_fee': 612334,
        'fresh_processing_fee': 122240,
        'reloan_processing_fee': 490094,
        
        # KPI Metrics - Interest Amount
        'interest_amount': 1935792,
        'fresh_interest_amount': 353621,
        'reloan_interest_amount': 1582171,
        
        # KPI Metrics - Repayment Amount
        'repayment_amount': 8727705,
        'fresh_repayment_amount': 1576036,
        'reloan_repayment_amount': 7151669,
        
        # Chart Data - State Distribution
        'state_labels': json.dumps(list(state_data.keys())),
        'state_values': json.dumps(list(state_data.values())),
        
        # Chart Data - City Distribution
        'city_labels': json.dumps(list(city_data.keys())),
        'city_values': json.dumps(list(city_data.values())),
        
        # Filter Options
        'states': sorted(state_data.keys()),
        'cities': sorted(city_data.keys()),
        
        # Last Updated
        'last_updated': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    
    return render(request, 'dashboard/pages/disbursal_summary.html', context)


def collection_without_fraud(request):
    """Collection Without Fraud page view"""
    # TODO: Implement your data fetching logic
    context = {
        # Add your context variables here
        'last_updated': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    return render(request, 'dashboard/pages/collection_without_fraud.html', context)


def collection_with_fraud(request):
    """Collection With Fraud page view"""
    # TODO: Implement your data fetching logic
    context = {
        # Add your context variables here
        'last_updated': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    return render(request, 'dashboard/pages/collection_with_fraud.html', context)


def loan_count_wise(request):
    """Loan Count Wise page view"""
    # TODO: Implement your data fetching logic
    context = {
        # Add your context variables here
        'last_updated': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    return render(request, 'dashboard/pages/loan_count_wise.html', context)


def daily_performance_metrics(request):
    """Daily Performance Metrics page view"""
    # TODO: Implement your data fetching logic
    context = {
        # Add your context variables here
        'last_updated': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    return render(request, 'dashboard/pages/daily_performance_metrics.html', context)


def credit_person_wise(request):
    """Credit Person Wise page view"""
    # TODO: Implement your data fetching logic
    context = {
        # Add your context variables here
        'last_updated': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    return render(request, 'dashboard/pages/credit_person_wise.html', context)


def aum_report(request):
    """AUM Report page view"""
    # TODO: Implement your data fetching logic
    context = {
        # Add your context variables here
        'last_updated': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    return render(request, 'dashboard/pages/aum_report.html', context)


# Helper function to prepare chart data from queryset
def prepare_chart_data(queryset, label_field, value_field):
    """
    Helper function to prepare chart data from a Django queryset
    
    Args:
        queryset: Django QuerySet
        label_field: Field name for labels (e.g., 'state', 'city')
        value_field: Field name for values (e.g., 'total_amount', 'count')
    
    Returns:
        tuple: (labels_json, values_json)
    """
    data = {}
    for item in queryset:
        label = getattr(item, label_field)
        value = getattr(item, value_field)
        data[label] = value
    
    labels = json.dumps(list(data.keys()))
    values = json.dumps(list(data.values()))
    
    return labels, values

