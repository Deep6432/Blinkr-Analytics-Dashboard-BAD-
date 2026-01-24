"""
Dashboard views for Edge Analytics Dashboard
"""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse, JsonResponse
from datetime import datetime, timedelta, date
import json
import requests
from collections import defaultdict
import pytz
import os
import re


@require_http_methods(["GET", "POST"])
def custom_login(request):
    """
    Custom login view that uses the Blinkr API for authentication
    """
    if request.user.is_authenticated:
        return redirect('/')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        if not username or not password:
            messages.error(request, 'Please provide both email and password.')
            return render(request, 'dashboard/login.html')
        
        # Call the Blinkr API for login
        api_url = 'https://backend.blinkrloan.com/api/crm/employee/login'
        
        # Prepare request data - API expects email and password
        login_data = {
            'email': username,  # username field contains email
            'password': password
        }
        
        # Headers for API request
        headers = {
            'Content-Type': 'application/json',
        }
        
        try:
            response = requests.post(
                api_url,
                json=login_data,
                headers=headers,
                timeout=30
            )
            
            # Debug: Print request details
            print(f"API Login Request URL: {api_url}")
            print(f"API Login Request Data: {login_data}")
            
            # Get response data
            try:
                api_response = response.json()
            except:
                api_response = {'error': f'Invalid JSON response: {response.text[:200]}'}
            
            # Debug: Print API response for troubleshooting
            print(f"API Login Response Status: {response.status_code}")
            print(f"API Login Response: {api_response}")
            print(f"API Login Response Keys: {list(api_response.keys()) if isinstance(api_response, dict) else 'Not a dict'}")
            
            # Check if request was successful (200 or 201)
            if response.status_code in [200, 201]:
                # Check for error messages first (API might return 200 with error message)
                error_message = None
                if api_response.get('message'):
                    msg = api_response.get('message', '').lower()
                    if 'not found' in msg or 'error' in msg or 'invalid' in msg or 'failed' in msg:
                        error_message = api_response.get('message', 'Login failed. Please check your credentials.')
                
                if error_message:
                    print(f"API Login Error (in 200 response): {error_message}")
                    messages.error(request, error_message)
                # Check if login was successful - API returns token and employee object
                elif 'token' in api_response and 'employee' in api_response:
                    token = api_response.get('token')
                    employee_data = api_response.get('employee', {})
                    
                    # Employee name mapping - map specific employee IDs to display names
                    employee_id = employee_data.get('id')
                    employee_name_mapping = {
                        16: {'f_name': 'Deep', 'l_name': 'Durugkar'}
                    }
                    
                    # Get mapped name if exists, otherwise use API data
                    if employee_id in employee_name_mapping:
                        mapped_name = employee_name_mapping[employee_id]
                        f_name = mapped_name['f_name']
                        l_name = mapped_name['l_name']
                    else:
                        f_name = employee_data.get('f_name', '')
                        l_name = employee_data.get('l_name', '')
                    
                    # Store token in session for future API calls
                    request.session['blinkr_token'] = token
                    request.session['employee_id'] = employee_id
                    request.session['employee_f_name'] = f_name
                    request.session['employee_l_name'] = l_name
                    request.session['employee_roles'] = employee_data.get('roles', [])
                    
                    # Create or get Django user
                    from django.contrib.auth.models import User
                    
                    # Use email as username, or employee ID if available
                    django_username = username
                    if employee_id:
                        django_username = f"employee_{employee_id}"
                    
                    # Try to get existing user or create one
                    user, created = User.objects.get_or_create(
                        username=django_username,
                        defaults={
                            'email': username,
                            'first_name': f_name,
                            'last_name': l_name,
                            'is_staff': False,
                            'is_superuser': False,
                        }
                    )
                    
                    # Update user info if it exists
                    if not created:
                        user.email = username
                        user.first_name = f_name
                        user.last_name = l_name
                        user.save()
                    
                    # Set password for Django authentication
                    user.set_password(password)
                    user.save()
                    
                    # Authenticate and login the user
                    user = authenticate(request, username=django_username, password=password)
                    if user:
                        login(request, user)
                        messages.success(request, 'Login successful!')
                        # Store token in response context for JavaScript to save to localStorage
                        response = redirect('/')
                        # Pass token via cookie (HttpOnly=False so JavaScript can access it)
                        # Note: This is less secure but needed for localStorage access
                        # Alternative: Pass via template context on redirect page
                        response.set_cookie('blinkr_token_temp', token, max_age=5, httponly=False, samesite='Lax')
                        return response
                    else:
                        # Fallback: login directly if authenticate fails
                        login(request, user)
                        messages.success(request, 'Login successful!')
                        response = redirect('/')
                        response.set_cookie('blinkr_token_temp', token, max_age=5, httponly=False, samesite='Lax')
                        return response
                else:
                    # Handle API error response (e.g., "employee not found")
                    error_message = api_response.get('message') or api_response.get('error') or api_response.get('msg') or 'Invalid credentials. Please try again.'
                    print(f"API Login Error: {error_message}")
                    print(f"Full API Response: {api_response}")
                    messages.error(request, error_message)
            else:
                # Handle API error (non-200 status codes)
                try:
                    error_data = response.json()
                    error_message = error_data.get('message') or error_data.get('error') or error_data.get('msg') or f'Login failed with status {response.status_code}. Please try again.'
                    print(f"API Error Response ({response.status_code}): {error_data}")
                except:
                    error_message = f'Login failed with status {response.status_code}. Please try again.'
                    print(f"API Error Response Text: {response.text[:500]}")
                
                messages.error(request, error_message)
                
        except requests.RequestException as e:
            messages.error(request, f'Connection error: {str(e)}. Please try again.')
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}. Please try again.')
        
        return render(request, 'dashboard/login.html')
    
    # GET request - show login form
    return render(request, 'dashboard/login.html')


@login_required
@never_cache
def leads_summary(request):
    """
    Leads Summary page view
    """
    context = {}
    return render(request, 'dashboard/pages/leads_summary.html', context)


@login_required
@never_cache
def disbursal_summary(request):
    """
    Disbursal Summary page view - Fetches data from API and filters by disbursal_date
    """
    # Get filter parameters from request
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    state_filters = request.GET.getlist('state')  # Get multiple states
    city_filters = request.GET.getlist('city')    # Get multiple cities
    
    # Filter out empty strings
    state_filters = [s for s in state_filters if s]
    city_filters = [c for c in city_filters if c]
    
    # Set up timezone (IST - Asia/Kolkata)
    ist = pytz.timezone('Asia/Kolkata')
    utc = pytz.UTC
    
    # Parse date filters (user input is in IST)
    date_from = None
    date_to = None
    
    if date_from_str:
        try:
            # Parse as date in IST
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if date_to_str:
        try:
            # Parse as date in IST
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Set default dates if not provided (today only in IST)
    now_ist = datetime.now(ist)
    today_date = now_ist.date()
    if not date_from:
        date_from = today_date
    if not date_to:
        date_to = today_date
    
    # Build API URL with startDate and endDate parameters
    api_url = 'https://backend.blinkrloan.com/insights/v2/disbursal'
    # Format dates as YYYY-MM-DD for API
    params = {
        'startDate': date_from.strftime('%Y-%m-%d'),
        'endDate': date_to.strftime('%Y-%m-%d')
    }
    
    # Fetch data from API
    try:
        # Add headers for authentication
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Use blinkr_token from session (SAME TOKEN AS LOGIN)
        token = request.session.get('blinkr_token')
        if token:
            headers['Authorization'] = f'Bearer {token}'
            print(f"Using blinkr_token from session for disbursal API request")
        else:
            # Fallback to API key from settings/environment
            api_key = os.environ.get('BLINKR_API_KEY') or getattr(settings, 'BLINKR_API_KEY', None)
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
                print(f"Using API key from settings for API request")
            else:
                print("WARNING: No authentication token found in session or settings")
        
        # Debug: Print request details
        print(f"Disbursal API URL: {api_url}")
        print(f"Disbursal API Params: {params}")
        print(f"Disbursal API Headers: {headers}")
        
        response = requests.get(api_url, params=params, headers=headers, timeout=30)
        # Check response status
        print(f"Disbursal API Response Status: {response.status_code}")
        
        # Handle non-200 status codes
        if response.status_code != 200:
            print(f"API Error Status: {response.status_code}")
            print(f"API Error Response: {response.text[:500]}")
            try:
                error_data = response.json()
                error_message = error_data.get('message') or error_data.get('error') or f'API returned status {response.status_code}'
                print(f"API Error Message: {error_message}")
            except:
                print(f"API Error Text: {response.text[:500]}")
            records = []
            all_cities_for_dropdown = set()
            cities_by_state = defaultdict(set)
        else:
            try:
                api_data = response.json()
            except:
                print(f"ERROR: Invalid JSON response: {response.text[:500]}")
                records = []
                all_cities_for_dropdown = set()
                cities_by_state = defaultdict(set)
            else:
                # Debug: Print API response structure
                print(f"Disbursal API Response Type: {type(api_data)}")
                print(f"Disbursal API Response Keys: {list(api_data.keys()) if isinstance(api_data, dict) else 'Not a dict'}")
                print(f"Disbursal API Response Sample: {str(api_data)[:500]}")
                
                # Check for authorization error
                if isinstance(api_data, dict) and (api_data.get('message') == 'not authorised' or 'unauthorized' in str(api_data.get('message', '')).lower()):
                    print("ERROR: API returned 'not authorised' - authentication required")
                    print("Token in session:", 'blinkr_token' in request.session)
                    records = []
                # Extract result array - v2 API might have different structure
                # Try different possible keys
                elif isinstance(api_data, list):
                    records = api_data
                    print(f"API returned list with {len(records)} records")
                elif isinstance(api_data, dict):
                    # Check for error messages
                    if 'message' in api_data or 'error' in api_data:
                        error_msg = api_data.get('message', api_data.get('error', 'Unknown error'))
                        print(f"API Error in response: {error_msg}")
                        records = []
                    else:
                        # Try to extract data from various possible keys
                        records = api_data.get('result', api_data.get('data', api_data.get('records', api_data.get('disbursals', api_data.get('items', [])))))
                        print(f"Extracted {len(records)} records from API response")
                else:
                    print(f"WARNING: Unexpected API response type: {type(api_data)}")
                    records = []
                
                print(f"Final records count: {len(records)}")
                if records and len(records) > 0:
                    print(f"First record keys: {records[0].keys() if isinstance(records[0], dict) else 'Not a dict'}")
                    print(f"First record sample: {str(records[0])[:200] if isinstance(records[0], dict) else 'Not a dict'}")
                else:
                    print(f"WARNING: No records found in API response!")
                
                # Ensure records is a list
                if not isinstance(records, list):
                    print(f"WARNING: Records is not a list, type: {type(records)}")
                    records = []
        
        # Get all cities for dropdown (before applying state/city filters)
        # This is used to populate the city dropdown based on selected state
        all_cities_for_dropdown = set()
        cities_by_state = defaultdict(set)
        for record in records:
            if isinstance(record, dict):
                state = record.get('state', '').strip()
                city = record.get('city', '').strip()
                if state and city:
                    all_cities_for_dropdown.add(city)
                    cities_by_state[state].add(city)
        
        # Apply state and city filters (multiple selections)
        if state_filters:
            records = [r for r in records if isinstance(r, dict) and r.get('state', '').strip() in state_filters]
        if city_filters:
            records = [r for r in records if isinstance(r, dict) and r.get('city', '').strip() in city_filters]
        
        print(f"Final records count after filtering: {len(records)}")
        
    except requests.RequestException as e:
        # Handle API errors gracefully
        records = []
        all_cities_for_dropdown = set()
        cities_by_state = defaultdict(set)
        print(f"API Request Error: {e}")
        print(f"API URL: {api_url}")
        print(f"API Params: {params}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response Status: {e.response.status_code}")
            print(f"Response Text: {e.response.text[:500]}")
    except (KeyError, ValueError, TypeError) as e:
        # Handle data parsing errors
        records = []
        all_cities_for_dropdown = set()
        cities_by_state = defaultdict(set)
        print(f"Data Parsing Error: {e}")
        print(f"API Response: {api_data if 'api_data' in locals() else 'Not available'}")
    
    # Initialize KPI counters
    total_records = len(records)
    fresh_count = 0
    reloan_count = 0
    
    total_loan_amount = 0
    fresh_loan_amount = 0
    reloan_loan_amount = 0
    
    total_disbursal_amount = 0
    fresh_disbursal_amount = 0
    reloan_disbursal_amount = 0
    
    processing_fee = 0
    fresh_processing_fee = 0
    reloan_processing_fee = 0
    
    interest_amount = 0
    fresh_interest_amount = 0
    reloan_interest_amount = 0
    
    repayment_amount = 0
    fresh_repayment_amount = 0
    reloan_repayment_amount = 0
    
    # Tenure tracking for average calculation
    total_tenure = 0
    tenure_count = 0
    fresh_tenure_sum = 0
    fresh_tenure_count = 0
    reloan_tenure_sum = 0
    reloan_tenure_count = 0
    
    # Aggregate data by state, city, and source
    # Using dictionaries to store multiple values per state/city/source (including count)
    state_data = defaultdict(lambda: {'disbursal': 0, 'sanction': 0, 'net_disbursal': 0, 'count': 0})
    city_data = defaultdict(lambda: {'disbursal': 0, 'sanction': 0, 'net_disbursal': 0, 'count': 0})
    source_data = defaultdict(lambda: {'disbursal': 0, 'sanction': 0, 'net_disbursal': 0, 'count': 0})
    
    # Get unique states for filter dropdowns
    all_states = set()
    for record in records:
        state = record.get('state', '').strip()
        if state:
            all_states.add(state)
    
    # Process each record for KPIs and charts
    for record in records:
        # Check if reloan case
        is_reloan = record.get('is_reloan_case', False)
        
        # Count records
        if is_reloan:
            reloan_count += 1
        else:
            fresh_count += 1
        
        # Extract amounts (handle None values)
        loan_amt = float(record.get('loan_amount', 0) or 0)  # Sanction amount
        disbursal_amt = float(record.get('Disbursal_Amt', 0) or 0)  # Net disbursal amount
        proc_fee = float(record.get('processing_fee', 0) or 0)
        int_amt = float(record.get('interest_amount', 0) or 0)
        repay_amt = float(record.get('repayment_amount', 0) or 0)
        tenure_days = float(record.get('tenure', 0) or 0)  # Tenure in days
        
        # Calculate net disbursal (Disbursal_Amt is already net, but keeping for clarity)
        net_disbursal_amt = disbursal_amt
        
        # Aggregate tenure
        if tenure_days > 0:
            total_tenure += tenure_days
            tenure_count += 1
            if is_reloan:
                reloan_tenure_sum += tenure_days
                reloan_tenure_count += 1
            else:
                fresh_tenure_sum += tenure_days
                fresh_tenure_count += 1
        
        # Aggregate totals
        total_loan_amount += loan_amt
        total_disbursal_amount += disbursal_amt
        processing_fee += proc_fee
        interest_amount += int_amt
        repayment_amount += repay_amt
        
        # Aggregate by fresh/reloan
        if is_reloan:
            reloan_loan_amount += loan_amt
            reloan_disbursal_amount += disbursal_amt
            reloan_processing_fee += proc_fee
            reloan_interest_amount += int_amt
            reloan_repayment_amount += repay_amt
        else:
            fresh_loan_amount += loan_amt
            fresh_disbursal_amount += disbursal_amt
            fresh_processing_fee += proc_fee
            fresh_interest_amount += int_amt
            fresh_repayment_amount += repay_amt
        
        # Aggregate by state, city, and source for charts
        state = record.get('state', '').strip()
        city = record.get('city', '').strip()
        source = record.get('source', record.get('Source', '')).strip()  # Try both lowercase and capitalized
        
        # State chart: Aggregate sanction, disbursal, net disbursal amounts, and count
        if state:
            state_data[state]['disbursal'] += disbursal_amt
            state_data[state]['sanction'] += loan_amt
            state_data[state]['net_disbursal'] += net_disbursal_amt
            state_data[state]['count'] += 1
        
        # City chart: Aggregate sanction, disbursal, net disbursal amounts, and count
        if city:
            city_data[city]['disbursal'] += disbursal_amt
            city_data[city]['sanction'] += loan_amt
            city_data[city]['net_disbursal'] += net_disbursal_amt
            city_data[city]['count'] += 1
        
        # Source chart: Aggregate sanction, disbursal, net disbursal amounts, and count
        if source:
            source_data[source]['disbursal'] += disbursal_amt
            source_data[source]['sanction'] += loan_amt
            source_data[source]['net_disbursal'] += net_disbursal_amt
            source_data[source]['count'] += 1
    
    # Sort state, city, and source data by disbursal amount (descending) and take top 20
    sorted_states = sorted(state_data.items(), key=lambda x: x[1]['disbursal'], reverse=True)[:20]
    sorted_cities = sorted(city_data.items(), key=lambda x: x[1]['disbursal'], reverse=True)[:20]
    sorted_sources = sorted(source_data.items(), key=lambda x: x[1]['disbursal'], reverse=True)[:20]
    
    # Prepare chart data - use disbursal amount for chart size, but include all data for tooltips
    state_labels = [item[0] for item in sorted_states]
    state_values = [item[1]['disbursal'] for item in sorted_states]
    state_sanction = [item[1]['sanction'] for item in sorted_states]
    state_net_disbursal = [item[1]['net_disbursal'] for item in sorted_states]
    state_counts = [item[1]['count'] for item in sorted_states]
    
    city_labels = [item[0] for item in sorted_cities]
    city_values = [item[1]['disbursal'] for item in sorted_cities]
    city_sanction = [item[1]['sanction'] for item in sorted_cities]
    city_net_disbursal = [item[1]['net_disbursal'] for item in sorted_cities]
    city_counts = [item[1]['count'] for item in sorted_cities]
    
    source_labels = [item[0] for item in sorted_sources]
    source_values = [item[1]['disbursal'] for item in sorted_sources]
    source_sanction = [item[1]['sanction'] for item in sorted_sources]
    source_net_disbursal = [item[1]['net_disbursal'] for item in sorted_sources]
    source_counts = [item[1]['count'] for item in sorted_sources]
    
    # Filter cities dropdown: show only cities from selected states
    if state_filters:
        filtered_cities_set = set()
        for state in state_filters:
            if state in cities_by_state:
                filtered_cities_set.update(cities_by_state[state])
        filtered_cities_for_dropdown = sorted(filtered_cities_set)
    else:
        filtered_cities_for_dropdown = sorted(all_cities_for_dropdown)
    
    # Fetch Collection Metrics from API - USING SAME DATE RANGE AS DISBURSAL FILTERS
    collection_metrics = {}
    
    # Helper function to aggregate multiple rows of collection metrics
    def aggregate_collection_metrics(rows, date_from=None, date_to=None):
        """Aggregate collection metrics from multiple rows into a single dict
        Filters by date_of_received if date range is provided
        """
        if not rows or len(rows) == 0:
            return {}
        
        # Filter rows by date_of_received if date range is provided
        filtered_rows = []
        if date_from and date_to:
            print(f"[Collection Metrics] Filtering collection records by date_of_received: {date_from} to {date_to}")
            date_from_date = date_from.date() if isinstance(date_from, datetime) else date_from
            date_to_date = date_to.date() if isinstance(date_to, datetime) else date_to
            
            for row in rows:
                if not isinstance(row, dict):
                    continue
                
                # Try to find date_of_received field (various name variations)
                date_received = None
                date_fields = ['date_of_recived', 'date_of_received', 'dateOfReceived', 'date_of_receive', 'dateOfReceive', 
                              'received_date', 'receivedDate', 'collection_date', 'collectionDate',
                              'date_received', 'dateReceived']
                
                for field in date_fields:
                    if field in row:
                        date_received = row[field]
                        break
                
                # If not found, try case-insensitive search
                if date_received is None:
                    row_keys_lower = {k.lower(): k for k in row.keys()}
                    for field_lower in ['date_of_recived', 'date_of_received', 'dateofreceived', 'date_of_receive', 'dateofreceive',
                                      'received_date', 'receiveddate', 'collection_date', 'collectiondate',
                                      'date_received', 'datereceived']:
                        if field_lower in row_keys_lower:
                            actual_key = row_keys_lower[field_lower]
                            date_received = row[actual_key]
                            break
                
                # Parse date if found
                if date_received:
                    try:
                        if isinstance(date_received, str):
                            # Try various date formats
                            for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%d-%m-%Y', '%d/%m/%Y']:
                                try:
                                    record_date = datetime.strptime(date_received.split('T')[0], fmt).date()
                                    break
                                except:
                                    continue
                            else:
                                # If no format worked, skip this record
                                print(f"[Collection Metrics] Could not parse date_of_received: {date_received}")
                                continue
                        elif isinstance(date_received, datetime):
                            record_date = date_received.date()
                        else:
                            continue
                        
                        # Check if date is within range
                        if date_from_date <= record_date <= date_to_date:
                            filtered_rows.append(row)
                    except Exception as e:
                        print(f"[Collection Metrics] Error parsing date_of_received '{date_received}': {e}")
                        # Include record if date parsing fails (to be safe)
                        filtered_rows.append(row)
                else:
                    # If no date_of_received field found, include the record (to be safe)
                    filtered_rows.append(row)
            
            print(f"[Collection Metrics] Filtered {len(filtered_rows)} records out of {len(rows)} by date_of_received")
        else:
            filtered_rows = rows
            print(f"[Collection Metrics] No date filtering applied (date_from or date_to not provided)")
        
        # Initialize aggregated dict with standard field names
        aggregated = {
            'total_collection_amount': 0,
            'fresh_collection_amount': 0,
            'reloan_collection_amount': 0,
            'prepayment_amount': 0,
            'due_date_amount': 0,
            'overdue_amount': 0,
            'total_collection_count': 0,
            'fresh_collection_count': 0,
            'reloan_collection_count': 0,
            'prepayment_count': 0,
            'due_date_count': 0,
            'overdue_count': 0
        }
        
        # First, check if rows contain individual records with is_reloan_case field
        # If so, aggregate by is_reloan_case instead of looking for separate fresh/reloan fields
        has_is_reloan_case = False
        for row in filtered_rows:
            if isinstance(row, dict):
                # Check for is_reloan_case in various forms
                if ('is_reloan_case' in row or 
                    'isReloanCase' in row or 
                    'is_reloan' in row or
                    'isReloan' in row):
                    has_is_reloan_case = True
                    break
        
        if has_is_reloan_case:
            print(f"[Collection Metrics] Found is_reloan_case field in records, aggregating by loan type...")
            # Debug: Print first record to see all available fields
            if filtered_rows and len(filtered_rows) > 0 and isinstance(filtered_rows[0], dict):
                sample = filtered_rows[0]
                print(f"[Collection Metrics] ===== SAMPLE RECORD FOR COLLECTION AMOUNT DEBUG =====")
                print(f"[Collection Metrics] Sample record fields: {list(sample.keys())}")
                # Show all amount-related fields
                amount_fields = {k: v for k, v in sample.items() if 'amount' in k.lower() or 'amt' in k.lower()}
                print(f"[Collection Metrics] All amount-related fields in sample record:")
                for k, v in sorted(amount_fields.items()):
                    print(f"[Collection Metrics]   '{k}': {v} (type: {type(v).__name__})")
                print(f"[Collection Metrics] ======================================================")
            # Aggregate collection amounts by is_reloan_case
            for row in filtered_rows:
                if not isinstance(row, dict):
                    continue
                
                # Get is_reloan_case value (try multiple field name variations)
                is_reloan = (row.get('is_reloan_case') or 
                            row.get('isReloanCase') or
                            row.get('is_reloan') or
                            row.get('isReloan'))
                
                # Handle None, False, or empty string
                if is_reloan is None:
                    is_reloan = False
                elif isinstance(is_reloan, str):
                    is_reloan = is_reloan.lower() in ['true', '1', 'yes']
                elif isinstance(is_reloan, (int, float)):
                    is_reloan = bool(is_reloan)
                else:
                    is_reloan = bool(is_reloan)
                
                print(f"[Collection Metrics] Record is_reloan_case value: {is_reloan} (type: {type(is_reloan).__name__})")
                
                # Try to find collection amount field - ONLY use total_collection_amount (user specified requirement)
                collection_amount = 0
                
                # ONLY look for total_collection_amount - do not use repayment_amount or any other field
                row_keys_lower = {k.lower(): k for k in row.keys()}
                
                # Try exact match first
                if 'total_collection_amount' in row:
                    try:
                        val = float(row['total_collection_amount'] or 0)
                        collection_amount = val
                        print(f"[Collection Metrics] Found total_collection_amount (exact): {collection_amount}")
                    except (ValueError, TypeError) as e:
                        print(f"[Collection Metrics] Error parsing total_collection_amount: {e}")
                
                # If not found, try case-insensitive search
                if collection_amount == 0 and 'total_collection_amount' in row_keys_lower:
                    actual_key = row_keys_lower['total_collection_amount']
                    try:
                        val = float(row[actual_key] or 0)
                        collection_amount = val
                        print(f"[Collection Metrics] Found total_collection_amount (case-insensitive, key='{actual_key}'): {collection_amount}")
                    except (ValueError, TypeError) as e:
                        print(f"[Collection Metrics] Error parsing total_collection_amount from '{actual_key}': {e}")
                
                # If still not found, log all available fields for debugging
                if collection_amount == 0:
                    print(f"[Collection Metrics] ERROR: total_collection_amount not found in record!")
                    print(f"[Collection Metrics] Available keys: {list(row.keys())}")
                    # Show all amount-related fields
                    amount_fields = {k: row[k] for k in row.keys() if 'amount' in k.lower() or 'amt' in k.lower()}
                    if amount_fields:
                        print(f"[Collection Metrics] All amount-related fields in this record:")
                        for af, af_val in sorted(amount_fields.items()):
                            print(f"[Collection Metrics]   '{af}': {af_val} (type: {type(af_val).__name__})")
                    print(f"[Collection Metrics] This record will be skipped (collection_amount = 0)")
                
                # Only categorize if we found total_collection_amount (skip records where it's 0 or missing)
                if collection_amount > 0:
                    # Categorize by is_reloan_case
                    if is_reloan:
                        aggregated['reloan_collection_amount'] += collection_amount
                        aggregated['reloan_collection_count'] += 1
                        print(f"[Collection Metrics] Added to Reloan: {collection_amount} (total now: {aggregated['reloan_collection_amount']})")
                    else:
                        aggregated['fresh_collection_amount'] += collection_amount
                        aggregated['fresh_collection_count'] += 1
                        print(f"[Collection Metrics] Added to Fresh: {collection_amount} (total now: {aggregated['fresh_collection_amount']})")
                    
                    aggregated['total_collection_amount'] += collection_amount
                    aggregated['total_collection_count'] += 1
                else:
                    print(f"[Collection Metrics] Skipping record - total_collection_amount is 0 or not found")
            
            print(f"[Collection Metrics] Aggregated by is_reloan_case - Fresh: ₹{aggregated['fresh_collection_amount']:.2f} ({aggregated['fresh_collection_count']} records), Reloan: ₹{aggregated['reloan_collection_amount']:.2f} ({aggregated['reloan_collection_count']} records)")
            
            # Recalculate total_collection_count as sum of Fresh + Reloan (not from counting all records)
            aggregated['total_collection_count'] = aggregated['fresh_collection_count'] + aggregated['reloan_collection_count']
            aggregated['total_collection_amount'] = aggregated['fresh_collection_amount'] + aggregated['reloan_collection_amount']
            print(f"[Collection Metrics] Recalculated total_collection_count: {aggregated['total_collection_count']} (Fresh {aggregated['fresh_collection_count']} + Reloan {aggregated['reloan_collection_count']})")
            
            # Continue with other field mappings for prepayment, overdue, etc.
            # But skip fresh/reloan field matching since we already calculated them
            skip_fresh_reloan_fields = True
        else:
            skip_fresh_reloan_fields = False
            print(f"[Collection Metrics] No is_reloan_case field found, using field name matching instead...")
        
        # Field name mappings - map various API field names to our standard names
        # IMPORTANT: For total_collection_amount, fresh_collection_amount, and reloan_collection_amount,
        # ONLY use total_collection_amount field (user requirement - do not use repayment_amount or collection_amount)
        field_mappings = {
            # Amount fields - ONLY use total_collection_amount variations, NO repayment_amount or collection_amount
            'total_collection_amount': ['total_collection_amount', 'Total_Collection_Amount', 'TOTAL_COLLECTION_AMOUNT', 'totalCollectionAmount', 'TotalCollectionAmount'],
            'fresh_collection_amount': ['fresh_collection_amount', 'freshCollectionAmount', 'fresh_amount', 'fresh', 'freshCollection', 'fresh_collection', 'freshCollectionAmt', 'fresh_collection_amt', 'freshAmt', 'fresh_amt'],
            'reloan_collection_amount': ['reloan_collection_amount', 'reloanCollectionAmount', 'reloan_amount', 'reloan', 'reloanCollection', 'reloan_collection', 'reloanCollectionAmt', 'reloan_collection_amt', 'reloanAmt', 'reloan_amt'],
            'prepayment_amount': ['prepayment_amount', 'prepaymentAmount', 'prepayment', 'prepaymentAmt', 'prepayment_amt'],
            'due_date_amount': ['due_date_amount', 'dueDateAmount', 'on_time_collection', 'onTimeCollection', 'on_time_amount', 'onTimeAmount', 'ontime_amount', 'ontimeAmount', 'onTime_amount', 'on_time_collection_amount', 'onTimeCollectionAmount', 'due_date_collection', 'dueDateCollection', 'on_time_amount_collection', 'onTimeAmountCollection'],
            'overdue_amount': ['overdue_amount', 'overdueAmount', 'overdue_collection', 'overdueCollection', 'overdue_collection_amount', 'overdueCollectionAmount'],
            # Count fields
            'total_collection_count': ['total_collection_count', 'totalCollectionCount', 'total_count', 'totalCount', 'total', 'totalCollectionCnt', 'total_collection_cnt'],
            'fresh_collection_count': ['fresh_collection_count', 'freshCollectionCount', 'fresh_count', 'freshCount', 'fresh', 'freshCollection', 'fresh_collection', 'freshCollectionCnt', 'fresh_collection_cnt', 'freshCnt', 'fresh_cnt'],
            'reloan_collection_count': ['reloan_collection_count', 'reloanCollectionCount', 'reloan_count', 'reloanCount', 'reloan', 'reloanCollection', 'reloan_collection', 'reloanCollectionCnt', 'reloan_collection_cnt', 'reloanCnt', 'reloan_cnt'],
            'prepayment_count': ['prepayment_count', 'prepaymentCount', 'prepayment', 'prepaymentCnt', 'prepayment_cnt'],
            'due_date_count': ['due_date_count', 'dueDateCount', 'on_time_count', 'onTimeCount', 'onTime', 'ontime', 'ontime_count', 'onTime_count', 'on_time_collection_count', 'onTimeCollectionCount', 'due_date_collection_count', 'dueDateCollectionCount'],
            'overdue_count': ['overdue_count', 'overdueCount', 'overdue', 'overdueCnt', 'overdue_cnt']
        }
        
        for row in filtered_rows:
            if not isinstance(row, dict):
                continue
            
            # Create case-insensitive lookup
            row_keys_lower = {k.lower(): k for k in row.keys()}
            
            # For each standard field, try to find it in the row using all possible variations
            # Process overdue fields FIRST to avoid conflicts with on_time fields
            field_order = ['overdue_amount', 'overdue_count', 'due_date_amount', 'due_date_count', 
                          'total_collection_amount', 'fresh_collection_amount', 'reloan_collection_amount', 
                          'prepayment_amount', 'total_collection_count', 'fresh_collection_count', 
                          'reloan_collection_count', 'prepayment_count']
            
            # Process fields in specific order
            for standard_field in field_order:
                # Skip fresh/reloan fields if we already calculated them from is_reloan_case
                if skip_fresh_reloan_fields and ('fresh' in standard_field or 'reloan' in standard_field):
                    continue
                    
                if standard_field not in field_mappings:
                    continue
                variations = field_mappings[standard_field]
                found = False
                for variation in variations:
                    # For total_collection_amount, fresh_collection_amount, and reloan_collection_amount,
                    # ONLY accept exact matches - do not use repayment_amount or collection_amount
                    if standard_field in ['total_collection_amount', 'fresh_collection_amount', 'reloan_collection_amount']:
                        # Skip any variation that contains 'repayment' or is not 'total_collection_amount' for total
                        if standard_field == 'total_collection_amount':
                            # ONLY accept total_collection_amount variations, reject repayment_amount, collection_amount, etc.
                            if 'repayment' in variation.lower() or ('collection_amount' in variation.lower() and 'total' not in variation.lower()):
                                continue
                        # For fresh/reloan, we still use the variations but skip if it contains repayment
                        elif 'repayment' in variation.lower():
                            continue
                    
                    # Try exact match first
                    if variation in row:
                        value = row[variation]
                        if value is not None and value != '':
                            try:
                                if 'count' in standard_field:
                                    aggregated[standard_field] += int(float(value))
                                else:
                                    aggregated[standard_field] += float(value)
                                found = True
                                print(f"[Collection Metrics] Found {standard_field} in '{variation}': {value}")
                                break  # Found it, move to next field
                            except (ValueError, TypeError):
                                pass
                    # Try case-insensitive match
                    elif variation.lower() in row_keys_lower:
                        actual_key = row_keys_lower[variation.lower()]
                        # For total_collection_amount, reject if actual_key contains 'repayment' or is not total_collection_amount
                        if standard_field == 'total_collection_amount':
                            if 'repayment' in actual_key.lower() or ('collection_amount' in actual_key.lower() and 'total' not in actual_key.lower()):
                                print(f"[Collection Metrics] Rejecting '{actual_key}' for total_collection_amount - contains repayment or is not total_collection_amount")
                                continue
                        # For fresh/reloan, reject if contains repayment
                        elif standard_field in ['fresh_collection_amount', 'reloan_collection_amount']:
                            if 'repayment' in actual_key.lower():
                                print(f"[Collection Metrics] Rejecting '{actual_key}' for {standard_field} - contains repayment")
                                continue
                        
                        value = row[actual_key]
                        # For overdue fields, make sure the key doesn't contain on_time/due_date
                        if 'overdue' in standard_field:
                            if 'on_time' in actual_key.lower() or 'ontime' in actual_key.lower() or 'due_date' in actual_key.lower() or 'duedate' in actual_key.lower():
                                continue  # Skip this match, it's not an overdue field
                        # For due_date fields, make sure the key doesn't contain overdue
                        elif 'due_date' in standard_field:
                            if 'overdue' in actual_key.lower():
                                continue  # Skip this match, it's not an on_time field
                        
                        if value is not None and value != '':
                            try:
                                if 'count' in standard_field:
                                    aggregated[standard_field] += int(float(value))
                                else:
                                    aggregated[standard_field] += float(value)
                                found = True
                                print(f"[Collection Metrics] Found {standard_field} in '{actual_key}' (case-insensitive): {value}")
                                break  # Found it, move to next field
                            except (ValueError, TypeError):
                                pass
                
                # If not found with variations, try partial matching for "on_time" or "ontime" in any key
                # BUT ONLY for due_date fields, and make sure we exclude overdue fields
                if not found and 'due_date' in standard_field:
                    for key, value in row.items():
                        key_lower = key.lower()
                        # Check if key contains "on_time", "ontime", "due_date", or "duedate"
                        # BUT EXCLUDE any keys that contain "overdue" to avoid mixing them up
                        if (('on_time' in key_lower or 'ontime' in key_lower or 'due_date' in key_lower or 'duedate' in key_lower) 
                            and 'overdue' not in key_lower and value is not None and value != ''):
                            try:
                                if 'count' in standard_field and ('count' in key_lower or 'number' in key_lower):
                                    aggregated[standard_field] += int(float(value))
                                    found = True
                                    break
                                elif 'amount' in standard_field and ('amount' in key_lower or 'amt' in key_lower or 'value' in key_lower):
                                    aggregated[standard_field] += float(value)
                                    found = True
                                    break
                            except (ValueError, TypeError):
                                pass
                
                # Add partial matching for fresh fields - check any field containing "fresh"
                if not found and 'fresh' in standard_field:
                    for key, value in row.items():
                        key_lower = key.lower()
                        # Check if key contains "fresh" (but not "refresh" or other words containing "fresh")
                        if ('fresh' in key_lower 
                            and 'refresh' not in key_lower
                            and value is not None and value != ''):
                            try:
                                if 'count' in standard_field and ('count' in key_lower or 'number' in key_lower or 'cnt' in key_lower):
                                    aggregated[standard_field] += int(float(value))
                                    found = True
                                    print(f"[Collection Metrics] Found fresh field via partial match: '{key}' = {value}")
                                    break
                                elif 'amount' in standard_field and ('amount' in key_lower or 'amt' in key_lower or 'value' in key_lower):
                                    aggregated[standard_field] += float(value)
                                    found = True
                                    print(f"[Collection Metrics] Found fresh field via partial match: '{key}' = {value}")
                                    break
                            except (ValueError, TypeError):
                                pass
                
                # Add partial matching for reloan fields - check any field containing "reloan"
                if not found and 'reloan' in standard_field:
                    for key, value in row.items():
                        key_lower = key.lower()
                        # Check if key contains "reloan"
                        if ('reloan' in key_lower 
                            and value is not None and value != ''):
                            try:
                                if 'count' in standard_field and ('count' in key_lower or 'number' in key_lower or 'cnt' in key_lower):
                                    aggregated[standard_field] += int(float(value))
                                    found = True
                                    print(f"[Collection Metrics] Found reloan field via partial match: '{key}' = {value}")
                                    break
                                elif 'amount' in standard_field and ('amount' in key_lower or 'amt' in key_lower or 'value' in key_lower):
                                    aggregated[standard_field] += float(value)
                                    found = True
                                    print(f"[Collection Metrics] Found reloan field via partial match: '{key}' = {value}")
                                    break
                            except (ValueError, TypeError):
                                pass
        
        # At the end, recalculate total_collection_count as sum of Fresh + Reloan
        # This ensures it's always correct regardless of how it was calculated
        if aggregated['fresh_collection_count'] > 0 or aggregated['reloan_collection_count'] > 0:
            aggregated['total_collection_count'] = aggregated['fresh_collection_count'] + aggregated['reloan_collection_count']
            aggregated['total_collection_amount'] = aggregated['fresh_collection_amount'] + aggregated['reloan_collection_amount']
            print(f"[Collection Metrics] Final recalculation - total_collection_count: {aggregated['total_collection_count']} (Fresh {aggregated['fresh_collection_count']} + Reloan {aggregated['reloan_collection_count']})")
        
        return aggregated
    
    try:
        collection_api_url = 'https://backend.blinkrloan.com/insights/v2/collection_metrics'
        # Use the SAME date_from and date_to from filters (same as disbursal API)
        collection_params = {
            'startDate': date_from.strftime('%Y-%m-%d'),
            'endDate': date_to.strftime('%Y-%m-%d')
        }
        collection_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Use EXACT SAME token method as disbursal API (which is working)
        token = request.session.get('blinkr_token')
        if token:
            collection_headers['Authorization'] = f'Bearer {token}'
        else:
            # Fallback to API key from settings/environment (same as disbursal)
            api_key = os.environ.get('BLINKR_API_KEY') or getattr(settings, 'BLINKR_API_KEY', None)
            if api_key:
                collection_headers['Authorization'] = f'Bearer {api_key}'
        
        # Reduced timeout for faster page load (5 seconds instead of 30)
        # If it times out, we'll use empty collection_metrics and let JavaScript handle it
        try:
            collection_response = requests.get(collection_api_url, params=collection_params, headers=collection_headers, timeout=5)
        except requests.exceptions.Timeout:
            print(f"[Collection Metrics] API request timed out after 5 seconds - using empty metrics")
            collection_metrics = {}
            collection_response = None
        
        if collection_response and collection_response.status_code == 200:
            try:
                collection_data = collection_response.json()
                
                # Handle different response structures (optimized - minimal logging)
                if isinstance(collection_data, dict):
                    # Check for error messages first
                    if 'error' in collection_data:
                        collection_metrics = {}
                    elif 'message' in collection_data:
                        message = collection_data.get('message', '')
                        if 'not authorised' in str(message).lower() or 'unauthorized' in str(message).lower() or 'error' in str(message).lower():
                            print(f"[Collection Metrics] API Error: {message}")
                            collection_metrics = {}
                    
                    # Check if data is nested in 'data' key
                    if 'data' in collection_data and not collection_metrics:
                        data_value = collection_data['data']
                        if isinstance(data_value, list) and len(data_value) > 0:
                            # Aggregate all rows instead of just taking the first
                            print(f"[Collection Metrics] Found {len(data_value)} rows in 'data', aggregating all...")
                            collection_metrics = aggregate_collection_metrics(data_value, date_from, date_to)
                        elif isinstance(data_value, dict):
                            collection_metrics = data_value
                        else:
                            collection_metrics = {}
                    elif 'result' in collection_data and not collection_metrics:
                        result_value = collection_data['result']
                        if isinstance(result_value, list) and len(result_value) > 0:
                            # Aggregate all rows instead of just taking the first
                            print(f"[Collection Metrics] Found {len(result_value)} rows in 'result', aggregating all...")
                            collection_metrics = aggregate_collection_metrics(result_value, date_from, date_to)
                        else:
                            collection_metrics = result_value if isinstance(result_value, dict) else {}
                    elif 'metrics' in collection_data and not collection_metrics:
                        metrics_value = collection_data['metrics']
                        if isinstance(metrics_value, list) and len(metrics_value) > 0:
                            # Aggregate all rows instead of just taking the first
                            print(f"[Collection Metrics] Found {len(metrics_value)} rows in 'metrics', aggregating all...")
                            collection_metrics = aggregate_collection_metrics(metrics_value)
                        else:
                            collection_metrics = metrics_value if isinstance(metrics_value, dict) else {}
                    elif not collection_metrics:
                        collection_metrics = collection_data
                        print(f"[Collection Metrics] Using collection_data directly as metrics: {list(collection_metrics.keys()) if isinstance(collection_metrics, dict) else 'Not a dict'}")
                elif isinstance(collection_data, list) and len(collection_data) > 0:
                    # Aggregate all rows instead of just taking the first
                    print(f"[Collection Metrics] Found {len(collection_data)} rows in list, aggregating all...")
                    # Debug: Print sample row to see what fields are actually in the API response
                    if collection_data and len(collection_data) > 0:
                        print(f"[Collection Metrics] Sample row keys: {list(collection_data[0].keys()) if isinstance(collection_data[0], dict) else 'Not a dict'}")
                        print(f"[Collection Metrics] Sample row (first 1000 chars): {str(collection_data[0])[:1000] if isinstance(collection_data[0], dict) else collection_data[0]}")
                        collection_metrics = aggregate_collection_metrics(collection_data, date_from, date_to)
                    # Debug: Print what fields were found
                    if collection_metrics:
                        print(f"[Collection Metrics] Aggregated metrics keys: {list(collection_metrics.keys())}")
                        print(f"[Collection Metrics] Fresh amount: {collection_metrics.get('fresh_collection_amount', 0)}, Fresh count: {collection_metrics.get('fresh_collection_count', 0)}")
                        print(f"[Collection Metrics] Reloan amount: {collection_metrics.get('reloan_collection_amount', 0)}, Reloan count: {collection_metrics.get('reloan_collection_count', 0)}")
                        print(f"[Collection Metrics] Total amount: {collection_metrics.get('total_collection_amount', 0)}, Total count: {collection_metrics.get('total_collection_count', 0)}")
                else:
                    collection_metrics = {}
            except Exception as e:
                print(f"[Collection Metrics] Error parsing JSON: {e}")
                collection_metrics = {}
        else:
            print(f"[Collection Metrics] API Error: {collection_response.status_code}")
            collection_metrics = {}
    except requests.exceptions.Timeout:
        print(f"[Collection Metrics] API request timed out")
        collection_metrics = {}
    except requests.exceptions.RequestException as e:
        print(f"[Collection Metrics] API request failed: {e}")
        collection_metrics = {}
    except Exception as e:
        print(f"[Collection Metrics] Unexpected error: {e}")
        collection_metrics = {}
    
        # Use collection metrics API values directly - don't override with calculations
        # The API should return Fresh/Reloan amounts directly
        if collection_metrics:
            # Get Fresh and Reloan values first
            fresh_collection_amt = collection_metrics.get('fresh_collection_amount', 0) or 0
            reloan_collection_amt = collection_metrics.get('reloan_collection_amount', 0) or 0
            fresh_collection_cnt = collection_metrics.get('fresh_collection_count', 0) or 0
            reloan_collection_cnt = collection_metrics.get('reloan_collection_count', 0) or 0
            
            # Calculate total count as sum of Fresh + Reloan (not from total_collection_count which might include other categories)
            total_collection_cnt = fresh_collection_cnt + reloan_collection_cnt
            
            # Always calculate total amount as sum of Fresh + Reloan (even if one is zero)
            total_collection_amt = fresh_collection_amt + reloan_collection_amt
            print(f"[Collection Metrics] Calculated total amount from Fresh ({fresh_collection_amt:.2f}) + Reloan ({reloan_collection_amt:.2f}) = ₹{total_collection_amt:.2f}")
            
            print(f"[Collection Metrics] API Response Values:")
            print(f"[Collection Metrics]   Total: ₹{total_collection_amt:.2f} ({total_collection_cnt} count = Fresh {fresh_collection_cnt} + Reloan {reloan_collection_cnt})")
            print(f"[Collection Metrics]   Fresh: ₹{fresh_collection_amt:.2f} ({fresh_collection_cnt} count)")
            print(f"[Collection Metrics]   Reloan: ₹{reloan_collection_amt:.2f} ({reloan_collection_cnt} count)")
            print(f"[Collection Metrics] All collection_metrics keys: {list(collection_metrics.keys())}")
            
            # Log warning if Fresh/Reloan are zero but total exists
            if total_collection_amt > 0 and (fresh_collection_amt == 0 and reloan_collection_amt == 0):
                print(f"[Collection Metrics] WARNING: Fresh/Reloan amounts are zero in API response but total exists.")
                print(f"[Collection Metrics] The collection metrics API should return Fresh/Reloan breakdown.")
            
            print(f"[Collection Metrics] Final values being used - Total: ₹{total_collection_amt:.2f} ({total_collection_cnt} count), Fresh: ₹{fresh_collection_amt:.2f} ({fresh_collection_cnt} count), Reloan: ₹{reloan_collection_amt:.2f} ({reloan_collection_cnt} count)")
            
            # Update collection_metrics dict with recalculated values
            collection_metrics['total_collection_count'] = total_collection_cnt
            collection_metrics['total_collection_amount'] = total_collection_amt
            collection_metrics['fresh_collection_count'] = fresh_collection_cnt
            collection_metrics['reloan_collection_count'] = reloan_collection_cnt
            collection_metrics['fresh_collection_amount'] = fresh_collection_amt
            collection_metrics['reloan_collection_amount'] = reloan_collection_amt
    
    context = {
        # KPI Metrics - Total Records
        'total_records': total_records,
        'fresh_count': fresh_count,
        'reloan_count': reloan_count,
        
        # KPI Metrics - Loan Amounts
        'total_loan_amount': total_loan_amount,
        'fresh_loan_amount': fresh_loan_amount,
        'reloan_loan_amount': reloan_loan_amount,
        
        # KPI Metrics - Disbursal Amounts
        'total_disbursal_amount': total_disbursal_amount,
        'fresh_disbursal_amount': fresh_disbursal_amount,
        'reloan_disbursal_amount': reloan_disbursal_amount,
        
        # KPI Metrics - Processing Fee
        'processing_fee': processing_fee,
        'fresh_processing_fee': fresh_processing_fee,
        'reloan_processing_fee': reloan_processing_fee,
        
        # KPI Metrics - Interest Amount
        'interest_amount': interest_amount,
        'fresh_interest_amount': fresh_interest_amount,
        'reloan_interest_amount': reloan_interest_amount,
        
        # KPI Metrics - Repayment Amount
        'repayment_amount': repayment_amount,
        'fresh_repayment_amount': fresh_repayment_amount,
        'reloan_repayment_amount': reloan_repayment_amount,
        
        # KPI Metrics - Average Tenure
        'average_tenure': round(total_tenure / tenure_count, 1) if tenure_count > 0 else 0,
        'fresh_average_tenure': round(fresh_tenure_sum / fresh_tenure_count, 1) if fresh_tenure_count > 0 else 0,
        'reloan_average_tenure': round(reloan_tenure_sum / reloan_tenure_count, 1) if reloan_tenure_count > 0 else 0,
        
        # Chart Data - State Distribution
        'state_labels': json.dumps(state_labels),
        'state_values': json.dumps(state_values),
        'state_sanction': json.dumps(state_sanction),
        'state_net_disbursal': json.dumps(state_net_disbursal),
        'state_counts': json.dumps(state_counts),
        
        # Chart Data - City Distribution
        'city_labels': json.dumps(city_labels),
        'city_values': json.dumps(city_values),
        'city_sanction': json.dumps(city_sanction),
        'city_net_disbursal': json.dumps(city_net_disbursal),
        'city_counts': json.dumps(city_counts),
        
        # Chart Data - Lead Source Distribution
        'source_labels': json.dumps(source_labels),
        'source_values': json.dumps(source_values),
        'source_sanction': json.dumps(source_sanction),
        'source_net_disbursal': json.dumps(source_net_disbursal),
        'source_counts': json.dumps(source_counts),
        
        # Filter Options
        'states': sorted(all_states),
        'cities': filtered_cities_for_dropdown,
        
        # Cities by state mapping for dynamic filtering (convert sets to lists for JSON)
        'cities_by_state_json': json.dumps({state: sorted(cities) for state, cities in cities_by_state.items()}),
        
        # Last Updated
        'last_updated': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        
        # Today's date for default date range
        'today_date': today_date.strftime('%Y-%m-%d'),
        
        # Collection Metrics - Convert to JSON string for template
        'collection_metrics': collection_metrics,
        # Include debug info if empty
        'collection_metrics_json': json.dumps(collection_metrics) if collection_metrics else '{}',
        'collection_metrics_debug': 'EMPTY' if not collection_metrics or len(collection_metrics) == 0 else 'HAS_DATA',
    }
    
    # Debug: Print collection_metrics before rendering
    print(f"=== COLLECTION METRICS DEBUG ===")
    print(f"Collection Metrics in context: {collection_metrics}")
    print(f"Collection Metrics type: {type(collection_metrics)}")
    if isinstance(collection_metrics, dict):
        print(f"Collection Metrics keys: {list(collection_metrics.keys())}")
        for key, value in collection_metrics.items():
            print(f"  {key}: {value} (type: {type(value)})")
    print(f"Collection Metrics JSON: {json.dumps(collection_metrics) if collection_metrics else '{}'}")
    print(f"================================")
    
    return render(request, 'dashboard/pages/disbursal_summary.html', context)


@login_required
@never_cache
def disbursal_data_api(request):
    """
    API endpoint that returns JSON data for disbursal summary
    Used for AJAX refresh without page reload
    """
    from django.http import JsonResponse
    
    # Get filter parameters from request
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    state_filters = request.GET.getlist('state')
    city_filters = request.GET.getlist('city')
    
    # Filter out empty strings
    state_filters = [s for s in state_filters if s]
    city_filters = [c for c in city_filters if c]
    
    # Set up timezone (IST - Asia/Kolkata)
    ist = pytz.timezone('Asia/Kolkata')
    
    # Parse date filters
    date_from = None
    date_to = None
    
    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Set default dates if not provided (today only in IST)
    now_ist = datetime.now(ist)
    if not date_from:
        date_from = now_ist.date()
    if not date_to:
        date_to = now_ist.date()
    
    # Build API URL with startDate and endDate parameters
    api_url = 'https://backend.blinkrloan.com/insights/v2/disbursal'
    params = {
        'startDate': date_from.strftime('%Y-%m-%d'),
        'endDate': date_to.strftime('%Y-%m-%d')
    }
    
    # Fetch data from API
    try:
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Use token from session
        token = request.session.get('blinkr_token')
        if token:
            headers['Authorization'] = f'Bearer {token}'
        else:
            api_key = os.environ.get('BLINKR_API_KEY') or getattr(settings, 'BLINKR_API_KEY', None)
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
        
        response = requests.get(api_url, params=params, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return JsonResponse({'error': f'API returned status {response.status_code}'}, status=500)
        
        try:
            api_data = response.json()
        except:
            return JsonResponse({'error': 'Invalid JSON response from API'}, status=500)
        
        # Extract records
        if isinstance(api_data, list):
            records = api_data
        elif isinstance(api_data, dict):
            if 'message' in api_data or 'error' in api_data:
                return JsonResponse({'error': api_data.get('message', api_data.get('error', 'Unknown error'))}, status=400)
            records = api_data.get('result', api_data.get('data', api_data.get('records', api_data.get('disbursals', api_data.get('items', [])))))
        else:
            records = []
        
        if not isinstance(records, list):
            records = []
        
        # Apply state and city filters
        if state_filters:
            records = [r for r in records if isinstance(r, dict) and r.get('state', '').strip() in state_filters]
        if city_filters:
            records = [r for r in records if isinstance(r, dict) and r.get('city', '').strip() in city_filters]
        
        # Process data (same logic as disbursal_summary view)
        total_records = len(records)
        fresh_count = 0
        reloan_count = 0
        
        total_loan_amount = 0
        fresh_loan_amount = 0
        reloan_loan_amount = 0
        
        total_disbursal_amount = 0
        fresh_disbursal_amount = 0
        reloan_disbursal_amount = 0
        
        processing_fee = 0
        fresh_processing_fee = 0
        reloan_processing_fee = 0
        
        interest_amount = 0
        fresh_interest_amount = 0
        reloan_interest_amount = 0
        
        repayment_amount = 0
        fresh_repayment_amount = 0
        reloan_repayment_amount = 0
        
        total_tenure = 0
        tenure_count = 0
        fresh_tenure_sum = 0
        fresh_tenure_count = 0
        reloan_tenure_sum = 0
        reloan_tenure_count = 0
        
        state_data = defaultdict(lambda: {'disbursal': 0, 'sanction': 0, 'net_disbursal': 0, 'count': 0})
        city_data = defaultdict(lambda: {'disbursal': 0, 'sanction': 0, 'net_disbursal': 0, 'count': 0})
        source_data = defaultdict(lambda: {'disbursal': 0, 'sanction': 0, 'net_disbursal': 0, 'count': 0})
        
        for record in records:
            is_reloan = record.get('is_reloan_case', False)
            
            if is_reloan:
                reloan_count += 1
            else:
                fresh_count += 1
            
            loan_amt = float(record.get('loan_amount', 0) or 0)
            disbursal_amt = float(record.get('Disbursal_Amt', 0) or 0)
            proc_fee = float(record.get('processing_fee', 0) or 0)
            int_amt = float(record.get('interest_amount', 0) or 0)
            repay_amt = float(record.get('repayment_amount', 0) or 0)
            tenure_days = float(record.get('tenure', 0) or 0)
            
            if tenure_days > 0:
                total_tenure += tenure_days
                tenure_count += 1
                if is_reloan:
                    reloan_tenure_sum += tenure_days
                    reloan_tenure_count += 1
                else:
                    fresh_tenure_sum += tenure_days
                    fresh_tenure_count += 1
            
            total_loan_amount += loan_amt
            total_disbursal_amount += disbursal_amt
            processing_fee += proc_fee
            interest_amount += int_amt
            repayment_amount += repay_amt
            
            if is_reloan:
                reloan_loan_amount += loan_amt
                reloan_disbursal_amount += disbursal_amt
                reloan_processing_fee += proc_fee
                reloan_interest_amount += int_amt
                reloan_repayment_amount += repay_amt
            else:
                fresh_loan_amount += loan_amt
                fresh_disbursal_amount += disbursal_amt
                fresh_processing_fee += proc_fee
                fresh_interest_amount += int_amt
                fresh_repayment_amount += repay_amt
            
            state = record.get('state', '').strip()
            city = record.get('city', '').strip()
            source = record.get('source', record.get('Source', '')).strip()  # Try both lowercase and capitalized
            
            if state:
                state_data[state]['disbursal'] += disbursal_amt
                state_data[state]['sanction'] += loan_amt
                state_data[state]['net_disbursal'] += disbursal_amt
                state_data[state]['count'] += 1
            
            if city:
                city_data[city]['disbursal'] += disbursal_amt
                city_data[city]['sanction'] += loan_amt
                city_data[city]['net_disbursal'] += disbursal_amt
                city_data[city]['count'] += 1
            
            if source:
                source_data[source]['disbursal'] += disbursal_amt
                source_data[source]['sanction'] += loan_amt
                source_data[source]['net_disbursal'] += disbursal_amt
                source_data[source]['count'] += 1
        
        # Sort and prepare chart data
        sorted_states = sorted(state_data.items(), key=lambda x: x[1]['disbursal'], reverse=True)[:20]
        sorted_cities = sorted(city_data.items(), key=lambda x: x[1]['disbursal'], reverse=True)[:20]
        sorted_sources = sorted(source_data.items(), key=lambda x: x[1]['disbursal'], reverse=True)[:20]
        
        state_labels = [item[0] for item in sorted_states]
        state_values = [item[1]['disbursal'] for item in sorted_states]
        state_sanction = [item[1]['sanction'] for item in sorted_states]
        state_counts = [item[1]['count'] for item in sorted_states]
        
        city_labels = [item[0] for item in sorted_cities]
        city_values = [item[1]['disbursal'] for item in sorted_cities]
        city_sanction = [item[1]['sanction'] for item in sorted_cities]
        city_counts = [item[1]['count'] for item in sorted_cities]
        
        source_labels = [item[0] for item in sorted_sources]
        source_values = [item[1]['disbursal'] for item in sorted_sources]
        source_sanction = [item[1]['sanction'] for item in sorted_sources]
        source_counts = [item[1]['count'] for item in sorted_sources]
        
        # Fetch Collection Metrics from API - USING SAME DATE RANGE AS DISBURSAL FILTERS
        # OPTIMIZATION: Skip collection metrics on initial page load to speed up page rendering (10-12 sec delay)
        # The data will be loaded via AJAX after page loads for better user experience
        print(f"[Collection Metrics] ⚡ OPTIMIZATION: Skipping collection metrics on initial page load for faster rendering")
        print(f"[Collection Metrics] Data will be loaded via AJAX endpoint after page loads")
        collection_metrics = {}
        
        # Skip the entire API call to speed up page load
        # Collection metrics will be fetched via /api/disbursal-data/ endpoint which is called by JavaScript
        
        # Helper function to aggregate multiple rows of collection metrics
        def aggregate_collection_metrics(rows, date_from=None, date_to=None):
            """Aggregate collection metrics from multiple rows into a single dict
            Filters by date_of_received if date range is provided
            """
            if not rows or len(rows) == 0:
                return {}
            
            # Filter rows by date_of_received if date range is provided
            filtered_rows = []
            if date_from and date_to:
                print(f"[API Endpoint] Filtering collection records by date_of_received: {date_from} to {date_to}")
                date_from_date = date_from.date() if isinstance(date_from, datetime) else date_from
                date_to_date = date_to.date() if isinstance(date_to, datetime) else date_to
                
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    
                    # Try to find date_of_received field (various name variations)
                    date_received = None
                    date_fields = ['date_of_recived', 'date_of_received', 'dateOfReceived', 'date_of_receive', 'dateOfReceive', 
                                  'received_date', 'receivedDate', 'collection_date', 'collectionDate',
                                  'date_received', 'dateReceived']
                    
                    for field in date_fields:
                        if field in row:
                            date_received = row[field]
                            break
                    
                    # If not found, try case-insensitive search
                    if date_received is None:
                        row_keys_lower = {k.lower(): k for k in row.keys()}
                        for field_lower in ['date_of_recived', 'date_of_received', 'dateofreceived', 'date_of_receive', 'dateofreceive',
                                          'received_date', 'receiveddate', 'collection_date', 'collectiondate',
                                          'date_received', 'datereceived']:
                            if field_lower in row_keys_lower:
                                actual_key = row_keys_lower[field_lower]
                                date_received = row[actual_key]
                                break
                    
                    # Parse date if found
                    if date_received:
                        try:
                            if isinstance(date_received, str):
                                # Try various date formats
                                for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%d-%m-%Y', '%d/%m/%Y']:
                                    try:
                                        record_date = datetime.strptime(date_received.split('T')[0], fmt).date()
                                        break
                                    except:
                                        continue
                                else:
                                    # If no format worked, skip this record
                                    print(f"[API Endpoint] Could not parse date_of_received: {date_received}")
                                    continue
                            elif isinstance(date_received, datetime):
                                record_date = date_received.date()
                            else:
                                continue
                            
                            # Check if date is within range
                            if date_from_date <= record_date <= date_to_date:
                                filtered_rows.append(row)
                            else:
                                print(f"[API Endpoint] Record date {record_date} is outside range {date_from_date} to {date_to_date}")
                        except Exception as e:
                            print(f"[API Endpoint] Error parsing date_of_received '{date_received}': {e}")
                            # Include record if date parsing fails (to be safe)
                            filtered_rows.append(row)
                    else:
                        # If no date_of_received field found, include the record (to be safe)
                        print(f"[API Endpoint] No date_of_received field found in record, including it anyway")
                        filtered_rows.append(row)
                
                print(f"[API Endpoint] Filtered {len(filtered_rows)} records out of {len(rows)} by date_of_received")
            else:
                filtered_rows = rows
                print(f"[API Endpoint] No date filtering applied (date_from or date_to not provided)")
            
            # Initialize aggregated dict with standard field names
            aggregated = {
                'total_collection_amount': 0,
                'fresh_collection_amount': 0,
                'reloan_collection_amount': 0,
                'prepayment_amount': 0,
                'due_date_amount': 0,
                'overdue_amount': 0,
                'total_collection_count': 0,
                'fresh_collection_count': 0,
                'reloan_collection_count': 0,
                'prepayment_count': 0,
                'due_date_count': 0,
                'overdue_count': 0
            }
            
            # First, check if rows contain individual records with is_reloan_case field
            # If so, aggregate by is_reloan_case instead of looking for separate fresh/reloan fields
            has_is_reloan_case = False
            for row in filtered_rows:
                if isinstance(row, dict):
                    # Check for is_reloan_case in various forms
                    if ('is_reloan_case' in row or 
                        'isReloanCase' in row or 
                        'is_reloan' in row or
                        'isReloan' in row):
                        has_is_reloan_case = True
                        break
            
            if has_is_reloan_case:
                print(f"[API Endpoint] Found is_reloan_case field in collection records, aggregating by loan type...")
                # Debug: Print first 3 records to see all available fields
                for i, sample_row in enumerate(filtered_rows[:3]):
                    if isinstance(sample_row, dict):
                        print(f"[API Endpoint] ===== Record #{i+1} (Sample - After Date Filter) =====")
                        print(f"[API Endpoint] All keys: {list(sample_row.keys())}")
                        print(f"[API Endpoint] All key-value pairs:")
                        for k, v in sample_row.items():
                            print(f"[API Endpoint]   '{k}': {v} (type: {type(v).__name__})")
                        print(f"[API Endpoint] ===== End Record #{i+1} =====")
                # Aggregate collection amounts by is_reloan_case
                for row in filtered_rows:
                    if not isinstance(row, dict):
                        continue
                    
                    # Get is_reloan_case value (try multiple field name variations)
                    is_reloan = (row.get('is_reloan_case') or 
                                row.get('isReloanCase') or
                                row.get('is_reloan') or
                                row.get('isReloan'))
                    
                    # Handle None, False, or empty string
                    if is_reloan is None:
                        is_reloan = False
                    elif isinstance(is_reloan, str):
                        is_reloan = is_reloan.lower() in ['true', '1', 'yes']
                    elif isinstance(is_reloan, (int, float)):
                        is_reloan = bool(is_reloan)
                    else:
                        is_reloan = bool(is_reloan)
                    
                    # Try to find collection amount field - prioritize collection-specific fields
                    # Avoid generic "amount" fields which might be loan_amount or disbursal_amount
                    collection_amount = 0
                    
                    # First, try collection-specific field names (most specific)
                    # DO NOT include generic 'amount' - it might be loan_amount or disbursal_amount
                    # ONLY use total_collection_amount - do not use repayment_amount or any other field
                    # Try exact match first
                    if 'total_collection_amount' in row:
                        try:
                            val = float(row['total_collection_amount'] or 0)
                            collection_amount = val
                            print(f"[API Endpoint] Found total_collection_amount (exact): {collection_amount}")
                        except (ValueError, TypeError) as e:
                            print(f"[API Endpoint] Error parsing total_collection_amount: {e}")
                    
                    # If not found, try case-insensitive search
                    if collection_amount == 0:
                        row_keys_lower = {k.lower(): k for k in row.keys()}
                        if 'total_collection_amount' in row_keys_lower:
                            actual_key = row_keys_lower['total_collection_amount']
                            try:
                                val = float(row[actual_key] or 0)
                                collection_amount = val
                                print(f"[API Endpoint] Found total_collection_amount (case-insensitive, key='{actual_key}'): {collection_amount}")
                            except (ValueError, TypeError) as e:
                                print(f"[API Endpoint] Error parsing total_collection_amount from '{actual_key}': {e}")
                    
                    # ONLY use total_collection_amount - do not use repayment_amount or any other field
                    # If not found, try case-insensitive search for total_collection_amount
                    if collection_amount == 0:
                        row_keys_lower = {k.lower(): k for k in row.keys()}
                        if 'total_collection_amount' in row_keys_lower:
                            actual_key = row_keys_lower['total_collection_amount']
                            try:
                                val = float(row[actual_key] or 0)
                                collection_amount = val
                                print(f"[API Endpoint] Found total_collection_amount (case-insensitive, key='{actual_key}'): {collection_amount}")
                            except (ValueError, TypeError) as e:
                                print(f"[API Endpoint] Error parsing total_collection_amount from '{actual_key}': {e}")
                    
                    # If still not found, log all available fields for debugging
                    if collection_amount == 0:
                        record_num = aggregated['total_collection_count'] + 1
                        if record_num <= 3:  # Only log for first 3 records to avoid spam
                            print(f"[API Endpoint] ERROR: total_collection_amount not found in record #{record_num}!")
                            print(f"[API Endpoint] Available keys: {list(row.keys())}")
                            # Show all amount-related fields
                            amount_fields = {k: row[k] for k in row.keys() if 'amount' in k.lower() or 'amt' in k.lower()}
                            if amount_fields:
                                print(f"[API Endpoint] All amount-related fields in record #{record_num}:")
                                for af, af_val in sorted(amount_fields.items()):
                                    print(f"[API Endpoint]   '{af}': {af_val} (type: {type(af_val).__name__})")
                            print(f"[API Endpoint] This record will be skipped (collection_amount = 0)")
                    else:
                        record_num = aggregated['total_collection_count'] + 1
                        print(f"[API Endpoint] ✓ Found total_collection_amount: ₹{collection_amount:.2f} for record #{record_num} (is_reloan={is_reloan})")
                    
                    # Only categorize if we found total_collection_amount (skip records where it's 0 or missing)
                    if collection_amount > 0:
                        # Categorize by is_reloan_case
                        if is_reloan:
                            aggregated['reloan_collection_amount'] += collection_amount
                            aggregated['reloan_collection_count'] += 1
                            print(f"[API Endpoint] Added to Reloan: {collection_amount} (total now: {aggregated['reloan_collection_amount']})")
                        else:
                            aggregated['fresh_collection_amount'] += collection_amount
                            aggregated['fresh_collection_count'] += 1
                            print(f"[API Endpoint] Added to Fresh: {collection_amount} (total now: {aggregated['fresh_collection_amount']})")
                        
                        aggregated['total_collection_amount'] += collection_amount
                        aggregated['total_collection_count'] += 1
                    else:
                        print(f"[API Endpoint] Skipping record - total_collection_amount is 0 or not found")
                
                print(f"[API Endpoint] Aggregated by is_reloan_case - Fresh: ₹{aggregated['fresh_collection_amount']:.2f} ({aggregated['fresh_collection_count']} records), Reloan: ₹{aggregated['reloan_collection_amount']:.2f} ({aggregated['reloan_collection_count']} records)")
                
                # Recalculate total_collection_count as sum of Fresh + Reloan (not from counting all records)
                aggregated['total_collection_count'] = aggregated['fresh_collection_count'] + aggregated['reloan_collection_count']
                aggregated['total_collection_amount'] = aggregated['fresh_collection_amount'] + aggregated['reloan_collection_amount']
                print(f"[API Endpoint] Recalculated total_collection_count: {aggregated['total_collection_count']} (Fresh {aggregated['fresh_collection_count']} + Reloan {aggregated['reloan_collection_count']})")
                
                # Continue with other field mappings for prepayment, overdue, etc.
                # But skip fresh/reloan field matching since we already calculated them
                skip_fresh_reloan_fields = True
            else:
                skip_fresh_reloan_fields = False
                print(f"[API Endpoint] No is_reloan_case field found, using field name matching instead...")
            
            # Field name mappings - map various API field names to our standard names
            # IMPORTANT: For total_collection_amount, fresh_collection_amount, and reloan_collection_amount,
            # ONLY use total_collection_amount field (user requirement - do not use repayment_amount or collection_amount)
            field_mappings = {
                # Amount fields - ONLY use total_collection_amount variations, NO repayment_amount or collection_amount
                'total_collection_amount': ['total_collection_amount', 'Total_Collection_Amount', 'TOTAL_COLLECTION_AMOUNT', 'totalCollectionAmount', 'TotalCollectionAmount'],
                'fresh_collection_amount': ['fresh_collection_amount', 'freshCollectionAmount', 'fresh_amount', 'fresh', 'freshCollection', 'fresh_collection', 'freshCollectionAmt', 'fresh_collection_amt', 'freshAmt', 'fresh_amt'],
                'reloan_collection_amount': ['reloan_collection_amount', 'reloanCollectionAmount', 'reloan_amount', 'reloan', 'reloanCollection', 'reloan_collection', 'reloanCollectionAmt', 'reloan_collection_amt', 'reloanAmt', 'reloan_amt'],
                'prepayment_amount': ['prepayment_amount', 'prepaymentAmount', 'prepayment', 'prepaymentAmt', 'prepayment_amt'],
                'due_date_amount': ['due_date_amount', 'dueDateAmount', 'on_time_collection', 'onTimeCollection', 'on_time_amount', 'onTimeAmount', 'ontime_amount', 'ontimeAmount', 'onTime_amount', 'on_time_collection_amount', 'onTimeCollectionAmount', 'due_date_collection', 'dueDateCollection', 'on_time_amount_collection', 'onTimeAmountCollection'],
                'overdue_amount': ['overdue_amount', 'overdueAmount', 'overdue_collection', 'overdueCollection', 'overdue_collection_amount', 'overdueCollectionAmount'],
                # Count fields
                'total_collection_count': ['total_collection_count', 'totalCollectionCount', 'total_count', 'totalCount', 'total', 'totalCollectionCnt', 'total_collection_cnt'],
                'fresh_collection_count': ['fresh_collection_count', 'freshCollectionCount', 'fresh_count', 'freshCount', 'fresh', 'freshCollection', 'fresh_collection', 'freshCollectionCnt', 'fresh_collection_cnt', 'freshCnt', 'fresh_cnt'],
                'reloan_collection_count': ['reloan_collection_count', 'reloanCollectionCount', 'reloan_count', 'reloanCount', 'reloan', 'reloanCollection', 'reloan_collection', 'reloanCollectionCnt', 'reloan_collection_cnt', 'reloanCnt', 'reloan_cnt'],
                'prepayment_count': ['prepayment_count', 'prepaymentCount', 'prepayment', 'prepaymentCnt', 'prepayment_cnt'],
                'due_date_count': ['due_date_count', 'dueDateCount', 'on_time_count', 'onTimeCount', 'onTime', 'ontime', 'ontime_count', 'onTime_count', 'on_time_collection_count', 'onTimeCollectionCount', 'due_date_collection_count', 'dueDateCollectionCount'],
                'overdue_count': ['overdue_count', 'overdueCount', 'overdue', 'overdueCnt', 'overdue_cnt']
            }
            
            for row in filtered_rows:
                if not isinstance(row, dict):
                    continue
                
                # Create case-insensitive lookup
                row_keys_lower = {k.lower(): k for k in row.keys()}
                
                # For each standard field, try to find it in the row using all possible variations
                # Process overdue fields FIRST to avoid conflicts with on_time fields
                field_order = ['overdue_amount', 'overdue_count', 'due_date_amount', 'due_date_count', 
                              'total_collection_amount', 'fresh_collection_amount', 'reloan_collection_amount', 
                              'prepayment_amount', 'total_collection_count', 'fresh_collection_count', 
                              'reloan_collection_count', 'prepayment_count']
                
                # Process fields in specific order
                for standard_field in field_order:
                    # Skip fresh/reloan fields if we already calculated them from is_reloan_case
                    if skip_fresh_reloan_fields and ('fresh' in standard_field or 'reloan' in standard_field):
                        continue
                        
                    if standard_field not in field_mappings:
                        continue
                    variations = field_mappings[standard_field]
                    found = False
                    for variation in variations:
                        # For total_collection_amount, fresh_collection_amount, and reloan_collection_amount,
                        # ONLY accept exact matches - do not use repayment_amount or collection_amount
                        if standard_field in ['total_collection_amount', 'fresh_collection_amount', 'reloan_collection_amount']:
                            # Skip any variation that contains 'repayment' or is not 'total_collection_amount' for total
                            if standard_field == 'total_collection_amount':
                                # ONLY accept total_collection_amount variations, reject repayment_amount, collection_amount, etc.
                                if 'repayment' in variation.lower() or ('collection_amount' in variation.lower() and 'total' not in variation.lower()):
                                    continue
                            # For fresh/reloan, we still use the variations but skip if it contains repayment
                            elif 'repayment' in variation.lower():
                                continue
                        
                        # Try exact match first
                        if variation in row:
                            value = row[variation]
                            if value is not None and value != '':
                                try:
                                    if 'count' in standard_field:
                                        aggregated[standard_field] += int(float(value))
                                    else:
                                        aggregated[standard_field] += float(value)
                                    found = True
                                    print(f"[API Endpoint] Found {standard_field} in '{variation}': {value}")
                                    break  # Found it, move to next field
                                except (ValueError, TypeError):
                                    pass
                        # Try case-insensitive match
                        elif variation.lower() in row_keys_lower:
                            actual_key = row_keys_lower[variation.lower()]
                            # For total_collection_amount, reject if actual_key contains 'repayment' or is not total_collection_amount
                            if standard_field == 'total_collection_amount':
                                if 'repayment' in actual_key.lower() or ('collection_amount' in actual_key.lower() and 'total' not in actual_key.lower()):
                                    print(f"[API Endpoint] Rejecting '{actual_key}' for total_collection_amount - contains repayment or is not total_collection_amount")
                                    continue
                            # For fresh/reloan, reject if contains repayment
                            elif standard_field in ['fresh_collection_amount', 'reloan_collection_amount']:
                                if 'repayment' in actual_key.lower():
                                    print(f"[API Endpoint] Rejecting '{actual_key}' for {standard_field} - contains repayment")
                                    continue
                            
                            value = row[actual_key]
                            # For overdue fields, make sure the key doesn't contain on_time/due_date
                            if 'overdue' in standard_field:
                                if 'on_time' in actual_key.lower() or 'ontime' in actual_key.lower() or 'due_date' in actual_key.lower() or 'duedate' in actual_key.lower():
                                    continue  # Skip this match, it's not an overdue field
                            # For due_date fields, make sure the key doesn't contain overdue
                            elif 'due_date' in standard_field:
                                if 'overdue' in actual_key.lower():
                                    continue  # Skip this match, it's not an on_time field
                            
                            if value is not None and value != '':
                                try:
                                    if 'count' in standard_field:
                                        aggregated[standard_field] += int(float(value))
                                    else:
                                        aggregated[standard_field] += float(value)
                                    found = True
                                    break  # Found it, move to next field
                                except (ValueError, TypeError):
                                    pass
                    
                    # If not found with variations, try partial matching for "on_time" or "ontime" in any key
                    # BUT ONLY for due_date fields, and make sure we exclude overdue fields
                    if not found and 'due_date' in standard_field:
                        for key, value in row.items():
                            key_lower = key.lower()
                            # Check if key contains "on_time", "ontime", "due_date", or "duedate"
                            # BUT EXCLUDE any keys that contain "overdue" to avoid mixing them up
                            if (('on_time' in key_lower or 'ontime' in key_lower or 'due_date' in key_lower or 'duedate' in key_lower) 
                                and 'overdue' not in key_lower and value is not None and value != ''):
                                try:
                                    if 'count' in standard_field and ('count' in key_lower or 'number' in key_lower):
                                        aggregated[standard_field] += int(float(value))
                                        found = True
                                        break
                                    elif 'amount' in standard_field and ('amount' in key_lower or 'amt' in key_lower or 'value' in key_lower):
                                        aggregated[standard_field] += float(value)
                                        found = True
                                        break
                                except (ValueError, TypeError):
                                    pass
                    
                    # Also add partial matching for overdue fields, but exclude on_time/due_date fields
                    if not found and 'overdue' in standard_field:
                        for key, value in row.items():
                            key_lower = key.lower()
                            # Check if key contains "overdue" but EXCLUDE any keys that contain "on_time", "ontime", "due_date", or "duedate"
                            if ('overdue' in key_lower 
                                and 'on_time' not in key_lower and 'ontime' not in key_lower 
                                and 'due_date' not in key_lower and 'duedate' not in key_lower
                                and value is not None and value != ''):
                                try:
                                    if 'count' in standard_field and ('count' in key_lower or 'number' in key_lower):
                                        aggregated[standard_field] += int(float(value))
                                        found = True
                                        break
                                    elif 'amount' in standard_field and ('amount' in key_lower or 'amt' in key_lower or 'value' in key_lower):
                                        aggregated[standard_field] += float(value)
                                        found = True
                                        break
                                except (ValueError, TypeError):
                                    pass
                    
                    # Add partial matching for fresh fields - check any field containing "fresh"
                    if not found and 'fresh' in standard_field:
                        for key, value in row.items():
                            key_lower = key.lower()
                            # Check if key contains "fresh" (but not "refresh" or other words containing "fresh")
                            if ('fresh' in key_lower 
                                and 'refresh' not in key_lower
                                and value is not None and value != ''):
                                try:
                                    if 'count' in standard_field and ('count' in key_lower or 'number' in key_lower or 'cnt' in key_lower):
                                        aggregated[standard_field] += int(float(value))
                                        found = True
                                        print(f"[Collection Metrics] Found fresh field via partial match: '{key}' = {value}")
                                        break
                                    elif 'amount' in standard_field and ('amount' in key_lower or 'amt' in key_lower or 'value' in key_lower):
                                        aggregated[standard_field] += float(value)
                                        found = True
                                        print(f"[Collection Metrics] Found fresh field via partial match: '{key}' = {value}")
                                        break
                                except (ValueError, TypeError):
                                    pass
                    
                    # Add partial matching for reloan fields - check any field containing "reloan"
                    if not found and 'reloan' in standard_field:
                        for key, value in row.items():
                            key_lower = key.lower()
                            # Check if key contains "reloan"
                            if ('reloan' in key_lower 
                                and value is not None and value != ''):
                                try:
                                    if 'count' in standard_field and ('count' in key_lower or 'number' in key_lower or 'cnt' in key_lower):
                                        aggregated[standard_field] += int(float(value))
                                        found = True
                                        print(f"[Collection Metrics] Found reloan field via partial match: '{key}' = {value}")
                                        break
                                    elif 'amount' in standard_field and ('amount' in key_lower or 'amt' in key_lower or 'value' in key_lower):
                                        aggregated[standard_field] += float(value)
                                        found = True
                                        print(f"[Collection Metrics] Found reloan field via partial match: '{key}' = {value}")
                                        break
                                except (ValueError, TypeError):
                                    pass
                    
                    # Add partial matching for prepayment fields - check any field containing "prepayment"
                    if not found and 'prepayment' in standard_field:
                        for key, value in row.items():
                            key_lower = key.lower()
                            # Check if key contains "prepayment"
                            if ('prepayment' in key_lower 
                                and value is not None and value != ''):
                                try:
                                    if 'count' in standard_field and ('count' in key_lower or 'number' in key_lower or 'cnt' in key_lower):
                                        aggregated[standard_field] += int(float(value))
                                        found = True
                                        print(f"[Collection Metrics] Found prepayment field via partial match: '{key}' = {value}")
                                        break
                                    elif 'amount' in standard_field and ('amount' in key_lower or 'amt' in key_lower or 'value' in key_lower):
                                        aggregated[standard_field] += float(value)
                                        found = True
                                        print(f"[Collection Metrics] Found prepayment field via partial match: '{key}' = {value}")
                                        break
                                except (ValueError, TypeError):
                                    pass
            
            # At the end, recalculate total_collection_count as sum of Fresh + Reloan
            # This ensures it's always correct regardless of how it was calculated
            if aggregated['fresh_collection_count'] > 0 or aggregated['reloan_collection_count'] > 0:
                aggregated['total_collection_count'] = aggregated['fresh_collection_count'] + aggregated['reloan_collection_count']
                aggregated['total_collection_amount'] = aggregated['fresh_collection_amount'] + aggregated['reloan_collection_amount']
                print(f"[API Endpoint] Final recalculation - total_collection_count: {aggregated['total_collection_count']} (Fresh {aggregated['fresh_collection_count']} + Reloan {aggregated['reloan_collection_count']})")
            
            return aggregated
        try:
            collection_api_url = 'https://backend.blinkrloan.com/insights/v2/collection_metrics'
            # Use the SAME date_from and date_to from filters (same as disbursal API)
            collection_params = {
                'startDate': date_from.strftime('%Y-%m-%d'),
                'endDate': date_to.strftime('%Y-%m-%d')
            }
            print(f"[API Endpoint] Collection Metrics API will use date range: {collection_params['startDate']} to {collection_params['endDate']}")
            
            collection_headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Use EXACT SAME token method as disbursal API (which is working)
            token = request.session.get('blinkr_token')
            if token:
                collection_headers['Authorization'] = f'Bearer {token}'
                print(f"[API Endpoint] Using blinkr_token from session for collection metrics API (SAME AS DISBURSAL)")
            else:
                # Fallback to API key from settings/environment (same as disbursal)
                api_key = os.environ.get('BLINKR_API_KEY') or getattr(settings, 'BLINKR_API_KEY', None)
                if api_key:
                    collection_headers['Authorization'] = f'Bearer {api_key}'
                    print(f"[API Endpoint] Using API key from settings for collection metrics API")
                else:
                    print(f"[API Endpoint] WARNING: No authentication token found in session or settings")
            
            print(f"[API Endpoint] Collection Metrics API URL: {collection_api_url}")
            print(f"[API Endpoint] Collection Metrics API Params: {collection_params}")
            print(f"[API Endpoint] Collection Metrics API Headers: {dict(collection_headers)}")
            
            # Reduced timeout for faster response (8 seconds)
            collection_response = requests.get(collection_api_url, params=collection_params, headers=collection_headers, timeout=8)
            print(f"[API Endpoint] Collection Metrics API Response Status: {collection_response.status_code}")
            print(f"[API Endpoint] Collection Metrics API Response URL: {collection_response.url}")
            
            if collection_response and collection_response.status_code == 200:
                try:
                    collection_data = collection_response.json()
                    print(f"[API Endpoint] Collection Metrics API Response Type: {type(collection_data)}")
                    print(f"[API Endpoint] Collection Metrics API Response (first 2000 chars): {str(collection_data)[:2000]}")
                    
                    # Handle different response structures
                    if isinstance(collection_data, dict):
                        # Check for error messages FIRST (but only if it's actually an error)
                        if 'error' in collection_data:
                            error_msg = collection_data.get('error')
                            print(f"[API Endpoint] Collection Metrics API Error: {error_msg}")
                            collection_metrics = {}  # Set to empty if error
                        elif 'message' in collection_data:
                            message = collection_data.get('message', '')
                            # Only treat as error if message contains error keywords
                            if 'not authorised' in str(message).lower() or 'unauthorized' in str(message).lower() or 'error' in str(message).lower():
                                print(f"[API Endpoint] Collection Metrics API Error Message: {message}")
                                if 'not authorised' in str(message).lower() or 'unauthorized' in str(message).lower():
                                    print(f"[API Endpoint] AUTHENTICATION FAILED - Token may be invalid or expired")
                                    print(f"[API Endpoint] Token being used: {token[:30] if token else 'None'}...")
                                collection_metrics = {}  # Set to empty if error
                            else:
                                # Message is not an error (e.g., "Data fetched successfully!"), continue processing
                                print(f"[API Endpoint] Collection Metrics API Message (not an error): {message}")
                                # Don't set collection_metrics to {} here, continue to check for 'data' key
                        
                        # Check if data is nested in 'data' key (API returns: {"success": true, "data": [...]})
                        if 'data' in collection_data and not collection_metrics:
                            data_value = collection_data['data']
                            print(f"[API Endpoint] Collection Metrics found 'data' key, type: {type(data_value)}")
                            # Check if data is an array (API structure: {"data": [{...}]})
                            if isinstance(data_value, list) and len(data_value) > 0:
                                # Aggregate all rows instead of just taking the first
                                print(f"[API Endpoint] Collection Metrics found {len(data_value)} rows, aggregating all...")
                                # Debug: Print sample row
                                if data_value and len(data_value) > 0:
                                    print(f"[API Endpoint] Sample row keys: {list(data_value[0].keys()) if isinstance(data_value[0], dict) else 'Not a dict'}")
                                    print(f"[API Endpoint] Sample row (first 500 chars): {str(data_value[0])[:500] if isinstance(data_value[0], dict) else data_value[0]}")
                                collection_metrics = aggregate_collection_metrics(data_value, date_from, date_to)
                                print(f"[API Endpoint] Collection Metrics aggregated from all rows: {collection_metrics}")
                                # Debug: Print Fresh and Reloan values
                                if collection_metrics:
                                    print(f"[API Endpoint] Fresh amount: {collection_metrics.get('fresh_collection_amount', 0)}, Fresh count: {collection_metrics.get('fresh_collection_count', 0)}")
                                    print(f"[API Endpoint] Reloan amount: {collection_metrics.get('reloan_collection_amount', 0)}, Reloan count: {collection_metrics.get('reloan_collection_count', 0)}")
                            elif isinstance(data_value, dict):
                                # Data is already a dict
                                collection_metrics = data_value
                                print(f"[API Endpoint] Collection Metrics found in 'data' key (dict): {collection_metrics}")
                            else:
                                print(f"[API Endpoint] Collection Metrics 'data' key has unexpected type: {type(data_value)}")
                                collection_metrics = {}
                        elif 'result' in collection_data and not collection_metrics:
                            result_value = collection_data['result']
                            if isinstance(result_value, list) and len(result_value) > 0:
                                # Aggregate all rows instead of just taking the first
                                print(f"[API Endpoint] Collection Metrics found {len(result_value)} rows in 'result', aggregating all...")
                                # Debug: Print sample row
                                if result_value and len(result_value) > 0:
                                    print(f"[API Endpoint] Sample row keys: {list(result_value[0].keys()) if isinstance(result_value[0], dict) else 'Not a dict'}")
                                collection_metrics = aggregate_collection_metrics(result_value, date_from, date_to)
                                print(f"[API Endpoint] Collection Metrics aggregated from 'result': {collection_metrics}")
                                # Debug: Print Fresh and Reloan values
                                if collection_metrics:
                                    print(f"[API Endpoint] Fresh amount: {collection_metrics.get('fresh_collection_amount', 0)}, Fresh count: {collection_metrics.get('fresh_collection_count', 0)}")
                                    print(f"[API Endpoint] Reloan amount: {collection_metrics.get('reloan_collection_amount', 0)}, Reloan count: {collection_metrics.get('reloan_collection_count', 0)}")
                            else:
                                collection_metrics = result_value if isinstance(result_value, dict) else {}
                                print(f"[API Endpoint] Collection Metrics found in 'result' key: {collection_metrics}")
                        elif 'metrics' in collection_data and not collection_metrics:
                            metrics_value = collection_data['metrics']
                            if isinstance(metrics_value, list) and len(metrics_value) > 0:
                                # Aggregate all rows instead of just taking the first
                                print(f"[API Endpoint] Collection Metrics found {len(metrics_value)} rows in 'metrics', aggregating all...")
                                collection_metrics = aggregate_collection_metrics(metrics_value, date_from, date_to)
                                print(f"[API Endpoint] Collection Metrics aggregated from 'metrics': {collection_metrics}")
                            else:
                                collection_metrics = metrics_value if isinstance(metrics_value, dict) else {}
                                print(f"[API Endpoint] Collection Metrics found in 'metrics' key: {collection_metrics}")
                        else:
                            # Use the full response as metrics
                            collection_metrics = collection_data
                            print(f"[API Endpoint] Collection Metrics using full response: {collection_metrics}")
                            print(f"[API Endpoint] Collection Metrics Keys: {list(collection_metrics.keys()) if isinstance(collection_metrics, dict) else 'N/A'}")
                            # Print all key-value pairs
                            if isinstance(collection_metrics, dict) and collection_metrics:
                                for k, v in collection_metrics.items():
                                    print(f"[API Endpoint]   '{k}': {v} (type: {type(v).__name__})")
                    elif isinstance(collection_data, list) and len(collection_data) > 0:
                        # Aggregate all rows instead of just taking the first
                        print(f"[API Endpoint] Collection Metrics found {len(collection_data)} rows in list, aggregating all...")
                        # Debug: Print sample row to see what fields are actually in the API response
                        if collection_data and len(collection_data) > 0:
                            print(f"[API Endpoint] Sample row keys: {list(collection_data[0].keys()) if isinstance(collection_data[0], dict) else 'Not a dict'}")
                            print(f"[API Endpoint] Sample row (first 500 chars): {str(collection_data[0])[:500] if isinstance(collection_data[0], dict) else collection_data[0]}")
                        collection_metrics = aggregate_collection_metrics(collection_data, date_from, date_to)
                        print(f"[API Endpoint] Collection Metrics aggregated from all rows: {collection_metrics}")
                        # Debug: Print what fields were found for Fresh and Reloan
                        if collection_metrics:
                            print(f"[API Endpoint] Fresh amount: {collection_metrics.get('fresh_collection_amount', 0)}, Fresh count: {collection_metrics.get('fresh_collection_count', 0)}")
                            print(f"[API Endpoint] Reloan amount: {collection_metrics.get('reloan_collection_amount', 0)}, Reloan count: {collection_metrics.get('reloan_collection_count', 0)}")
                except Exception as e:
                    print(f"[API Endpoint] Error parsing collection metrics JSON: {e}")
                    print(f"[API Endpoint] Response text: {collection_response.text[:500]}")
                    collection_metrics = {}
            else:
                print(f"[API Endpoint] Collection Metrics API Error Status: {collection_response.status_code}")
                print(f"[API Endpoint] Collection Metrics API Error Response: {collection_response.text[:500]}")
                collection_metrics = {}
        except Exception as e:
            print(f"[API Endpoint] Exception while fetching collection metrics: {e}")
            import traceback
            print(f"[API Endpoint] Traceback: {traceback.format_exc()}")
            collection_metrics = {}
        
        # The collection metrics API should return Fresh/Reloan amounts directly
        # Use the API response values as-is - don't override with calculations
        if collection_metrics:
            fresh_collection_amt = collection_metrics.get('fresh_collection_amount', 0) or 0
            reloan_collection_amt = collection_metrics.get('reloan_collection_amount', 0) or 0
            fresh_collection_cnt = collection_metrics.get('fresh_collection_count', 0) or 0
            reloan_collection_cnt = collection_metrics.get('reloan_collection_count', 0) or 0
            
            # Calculate total count as sum of Fresh + Reloan (not from total_collection_count which might include other categories)
            total_collection_cnt = fresh_collection_cnt + reloan_collection_cnt
            
            # Always calculate total amount as sum of Fresh + Reloan (even if one is zero)
            total_collection_amt = fresh_collection_amt + reloan_collection_amt
            print(f"[API Endpoint] Calculated total amount from Fresh ({fresh_collection_amt:.2f}) + Reloan ({reloan_collection_amt:.2f}) = ₹{total_collection_amt:.2f}")
            
            print(f"[API Endpoint] Collection Metrics API Response - Total: ₹{total_collection_amt:.2f} ({total_collection_cnt} = Fresh {fresh_collection_cnt} + Reloan {reloan_collection_cnt}), Fresh: ₹{fresh_collection_amt:.2f} ({fresh_collection_cnt}), Reloan: ₹{reloan_collection_amt:.2f} ({reloan_collection_cnt})")
            
            # If Fresh/Reloan amounts are zero but we have total, log a warning
            if total_collection_amt > 0 and (fresh_collection_amt == 0 and reloan_collection_amt == 0):
                print(f"[API Endpoint] WARNING: Fresh/Reloan amounts are zero in API response.")
                print(f"[API Endpoint] Available keys in collection_metrics: {list(collection_metrics.keys())}")
            
            # Update collection_metrics dict with recalculated values
            collection_metrics['total_collection_count'] = total_collection_cnt
            collection_metrics['total_collection_amount'] = total_collection_amt
            collection_metrics['fresh_collection_count'] = fresh_collection_cnt
            collection_metrics['reloan_collection_count'] = reloan_collection_cnt
            collection_metrics['fresh_collection_amount'] = fresh_collection_amt
            collection_metrics['reloan_collection_amount'] = reloan_collection_amt
            
            print(f"[API Endpoint] Updated collection_metrics dict:")
            print(f"[API Endpoint]   total_collection_amount: {collection_metrics.get('total_collection_amount')}")
            print(f"[API Endpoint]   fresh_collection_amount: {collection_metrics.get('fresh_collection_amount')}")
            print(f"[API Endpoint]   reloan_collection_amount: {collection_metrics.get('reloan_collection_amount')}")
            print(f"[API Endpoint]   prepayment_amount: {collection_metrics.get('prepayment_amount')}")
            print(f"[API Endpoint]   prepayment_count: {collection_metrics.get('prepayment_count')}")
            print(f"[API Endpoint]   due_date_amount: {collection_metrics.get('due_date_amount')}")
            print(f"[API Endpoint]   overdue_amount: {collection_metrics.get('overdue_amount')}")
        
        # Debug: Print collection metrics before returning
        print(f"[API Endpoint] ===== COLLECTION METRICS RESULT =====")
        print(f"[API Endpoint] Collection Metrics being sent to frontend: {collection_metrics}")
        print(f"[API Endpoint] Collection Metrics type: {type(collection_metrics)}")
        if isinstance(collection_metrics, dict):
            print(f"[API Endpoint] Collection Metrics keys: {list(collection_metrics.keys())}")
            if collection_metrics:
                for k, v in collection_metrics.items():
                    print(f"[API Endpoint]   {k}: {v}")
            else:
                print(f"[API Endpoint] Collection Metrics dict is EMPTY!")
        else:
            print(f"[API Endpoint] Collection Metrics is not a dict!")
        print(f"[API Endpoint] ======================================")
        
        # Return JSON response
        response_data = {
            'total_records': total_records,
            'fresh_count': fresh_count,
            'reloan_count': reloan_count,
            'total_loan_amount': total_loan_amount,
            'fresh_loan_amount': fresh_loan_amount,
            'reloan_loan_amount': reloan_loan_amount,
            'total_disbursal_amount': total_disbursal_amount,
            'fresh_disbursal_amount': fresh_disbursal_amount,
            'reloan_disbursal_amount': reloan_disbursal_amount,
            'processing_fee': processing_fee,
            'fresh_processing_fee': fresh_processing_fee,
            'reloan_processing_fee': reloan_processing_fee,
            'interest_amount': interest_amount,
            'fresh_interest_amount': fresh_interest_amount,
            'reloan_interest_amount': reloan_interest_amount,
            'repayment_amount': repayment_amount,
            'fresh_repayment_amount': fresh_repayment_amount,
            'reloan_repayment_amount': reloan_repayment_amount,
            'average_tenure': round(total_tenure / tenure_count, 1) if tenure_count > 0 else 0,
            'fresh_average_tenure': round(fresh_tenure_sum / fresh_tenure_count, 1) if fresh_tenure_count > 0 else 0,
            'reloan_average_tenure': round(reloan_tenure_sum / reloan_tenure_count, 1) if reloan_tenure_count > 0 else 0,
            'state_labels': state_labels,
            'state_values': state_values,
            'state_sanction': state_sanction,
            'state_counts': state_counts,
            'city_labels': city_labels,
            'city_values': city_values,
            'city_sanction': city_sanction,
            'city_counts': city_counts,
            'source_labels': source_labels,
            'source_values': source_values,
            'source_sanction': source_sanction,
            'source_counts': source_counts,
            'collection_metrics': collection_metrics,
            'last_updated': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        print(f"Full API Response being sent (collection_metrics part): {response_data.get('collection_metrics')}")
        
        return JsonResponse(response_data)
        
    except requests.RequestException as e:
        return JsonResponse({'error': f'API request failed: {str(e)}'}, status=500)
    except Exception as e:
        return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)


@login_required
@never_cache
def disbursal_records_api(request):
    """
    API endpoint that returns raw records data for the records table modal
    """
    # Get filter parameters from request
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    state_filters = request.GET.getlist('state')
    city_filters = request.GET.getlist('city')
    
    # Filter out empty strings
    state_filters = [s for s in state_filters if s]
    city_filters = [c for c in city_filters if c]
    
    # Set up timezone (IST - Asia/Kolkata)
    ist = pytz.timezone('Asia/Kolkata')
    
    # Parse date filters
    date_from = None
    date_to = None
    
    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Set default dates if not provided (today only in IST)
    now_ist = datetime.now(ist)
    if not date_from:
        date_from = now_ist.date()
    if not date_to:
        date_to = now_ist.date()
    
    # Build API URL with startDate and endDate parameters
    api_url = 'https://backend.blinkrloan.com/insights/v2/disbursal'
    params = {
        'startDate': date_from.strftime('%Y-%m-%d'),
        'endDate': date_to.strftime('%Y-%m-%d')
    }
    
    # Fetch data from API
    try:
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Use token from session
        token = request.session.get('blinkr_token')
        if token:
            headers['Authorization'] = f'Bearer {token}'
        else:
            api_key = os.environ.get('BLINKR_API_KEY') or getattr(settings, 'BLINKR_API_KEY', None)
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
        
        response = requests.get(api_url, params=params, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return JsonResponse({'error': f'API returned status {response.status_code}'}, status=500)
        
        try:
            api_data = response.json()
        except:
            return JsonResponse({'error': 'Invalid JSON response from API'}, status=500)
        
        # Extract records
        if isinstance(api_data, list):
            records = api_data
        elif isinstance(api_data, dict):
            if 'message' in api_data or 'error' in api_data:
                return JsonResponse({'error': api_data.get('message', api_data.get('error', 'Unknown error'))}, status=400)
            records = api_data.get('result', api_data.get('data', api_data.get('records', api_data.get('disbursals', api_data.get('items', [])))))
        else:
            records = []
        
        if not isinstance(records, list):
            records = []
        
        # Apply state and city filters
        if state_filters:
            records = [r for r in records if isinstance(r, dict) and r.get('state', '').strip() in state_filters]
        if city_filters:
            records = [r for r in records if isinstance(r, dict) and r.get('city', '').strip() in city_filters]
        
        # Return raw records data
        return JsonResponse({
            'records': records,
            'count': len(records)
        })
        
    except requests.RequestException as e:
        return JsonResponse({'error': f'API request failed: {str(e)}'}, status=500)
    except Exception as e:
        return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)


@login_required
@never_cache
def collection_without_fraud(request):
    """
    Collection Summary page view.
    IMPORTANT: This page uses ONLY insights/v2/collection_summary (no other APIs).
    """
    # --- Parse filters ---
    ist = pytz.timezone('Asia/Kolkata')
    today_date = datetime.now(ist).date()

    date_from_str = request.GET.get('date_from') or ''
    date_to_str = request.GET.get('date_to') or ''

    try:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date() if date_from_str else today_date
    except ValueError:
        date_from = today_date
    try:
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date() if date_to_str else today_date
    except ValueError:
        date_to = today_date

    if date_from > date_to:
        date_from, date_to = date_to, date_from

    state_filters = [s.strip() for s in request.GET.getlist('state') if str(s).strip()]
    city_filters = [c.strip() for c in request.GET.getlist('city') if str(c).strip()]
    actual_repayment_bucket = (request.GET.get('actual_repayment_bucket') or '').strip()
    loan_pre_post_ontime_status = (request.GET.get('loan_pre_post_ontime_status') or '').strip()
    date_type = (request.GET.get('date_type') or 'repayment').strip().lower()  # Default to 'repayment'

    # --- Fetch ONLY collection_summary API ---
    api_url = 'https://backend.blinkrloan.com/insights/v2/collection_summary'

    params = [
        ('startDate', date_from.strftime('%Y-%m-%d')),
        ('endDate', date_to.strftime('%Y-%m-%d')),
    ]
    # Pass optional filters if API supports them (safe; we also filter server-side below)
    for s in state_filters:
        params.append(('state', s))
    for c in city_filters:
        params.append(('city', c))
    if actual_repayment_bucket:
        params.append(('actual_repayment_bucket', actual_repayment_bucket))
    if loan_pre_post_ontime_status:
        params.append(('loan_pre_post_ontime_status', loan_pre_post_ontime_status))

    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    token = request.session.get('blinkr_token')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    else:
        api_key = os.environ.get('BLINKR_API_KEY') or getattr(settings, 'BLINKR_API_KEY', None)
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

    rows = []
    api_error = None
    try:
        resp = requests.get(api_url, params=params, headers=headers, timeout=30)
        if resp.status_code != 200:
            api_error = f"collection_summary API returned {resp.status_code}"
        else:
            api_data = resp.json()
            # Handle common wrappers
            if isinstance(api_data, dict):
                candidate = None
                for key in ('data', 'result', 'collection_summary', 'items', 'records'):
                    if key in api_data:
                        candidate = api_data[key]
                        break
                if candidate is None:
                    candidate = api_data
            else:
                candidate = api_data

            if isinstance(candidate, list):
                rows = candidate
            elif isinstance(candidate, dict):
                # If dict is actually a single row
                rows = [candidate]
            else:
                rows = []
    except requests.RequestException as e:
        api_error = f"collection_summary API request failed: {e}"
        rows = []
    except Exception as e:
        api_error = f"collection_summary unexpected error: {e}"
        rows = []

    # --- Server-side filtering (still ONLY from this API response) ---
    def _norm(x):
        return str(x).strip()

    if state_filters:
        state_set = set(state_filters)
        rows = [r for r in rows if isinstance(r, dict) and _norm(r.get('state', '')) in state_set]
    if city_filters:
        city_set = set(city_filters)
        rows = [r for r in rows if isinstance(r, dict) and _norm(r.get('city', '')) in city_set]
    if actual_repayment_bucket:
        rows = [r for r in rows if isinstance(r, dict) and _norm(r.get('actual_repayment_bucket', '')) == actual_repayment_bucket]
    if loan_pre_post_ontime_status:
        rows = [r for r in rows if isinstance(r, dict) and _norm(r.get('loan_pre_post_ontime_status', '')) == loan_pre_post_ontime_status]

    # --- Date filtering by date_type (Repayment Date or Disbursal Date) ---
    def parse_date_any(value):
        """Parse various date formats from API response."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        s = str(value).strip()
        if not s:
            return None
        # Try various date formats
        formats = [
            '%Y-%m-%d',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%d-%m-%Y',
            '%d/%m/%Y',
            '%Y/%m/%d',
        ]
        for fmt in formats:
            try:
                return datetime.strptime(s.split('T')[0], fmt).date()
            except (ValueError, AttributeError):
                continue
        # Try epoch timestamp (seconds or milliseconds)
        try:
            ts = float(s)
            if ts > 1e12:  # milliseconds
                ts = ts / 1000
            return datetime.fromtimestamp(ts).date()
        except (ValueError, OSError, OverflowError):
            pass
        return None

    # Filter by date_type (repayment or disbursal date)
    if date_from and date_to:
        filtered_rows = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            
            # Determine which date field to use based on date_type
            date_value = None
            if date_type == 'disbursal':
                # Try disbursal date fields
                date_fields = [
                    'disbursal_date', 'disbursalDate', 'disbursal_date_ist',
                    'disbursement_date', 'disbursementDate',
                    'loan_disbursal_date', 'loanDisbursalDate',
                    'disbursed_date', 'disbursedDate',
                ]
            else:  # repayment (default)
                # Try repayment/received date fields
                date_fields = [
                    'date_of_received', 'date_of_recived', 'dateOfReceived',
                    'received_date', 'receivedDate',
                    'collection_date', 'collectionDate',
                    'repayment_date', 'repaymentDate',
                    'date_received', 'dateReceived',
                ]
            
            # Try exact match first
            for field in date_fields:
                if field in r:
                    date_value = r[field]
                    break
            
            # Try case-insensitive match
            if date_value is None:
                row_keys_lower = {k.lower(): k for k in r.keys()}
                for field in date_fields:
                    field_lower = field.lower()
                    if field_lower in row_keys_lower:
                        actual_key = row_keys_lower[field_lower]
                        date_value = r[actual_key]
                        break
            
            # Parse the date
            row_date = parse_date_any(date_value)
            
            # Include row if date is within range, or if date couldn't be parsed (to be safe)
            if row_date is None:
                # If date couldn't be parsed, include the row (to avoid excluding valid data)
                filtered_rows.append(r)
            elif date_from <= row_date <= date_to:
                filtered_rows.append(r)
        
        rows = filtered_rows
        print(f"[Collection Summary] Filtered by {date_type} date ({date_from} to {date_to}): {len(rows)} rows remaining")

    # --- Aggregations / dropdown options ---
    def to_float(v):
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            try:
                return float(v)
            except Exception:
                return 0.0
        s = str(v).strip()
        if s == '':
            return 0.0
        # Normalize common formatting: currency symbol, commas, spaces
        s = s.replace('₹', '').replace(',', '').strip()
        # Try direct float first
        try:
            return float(s)
        except (ValueError, TypeError):
            pass
        # Fallback: extract first numeric token (handles "₹12,345.00", "12,345 INR", etc.)
        try:
            m = re.search(r'-?\d+(?:\.\d+)?', s)
            if m:
                return float(m.group(0))
        except Exception:
            pass
        return 0.0

    def get_pending_collection_value(r):
        if not isinstance(r, dict):
            return 0.0
        return to_float(
            r.get('pending_collection') or r.get('pendingCollection') or
            r.get('pending_collection_amount') or r.get('pendingCollectionAmount') or
            r.get('pendingCollectionAmt') or r.get('pending_collection_amt')
        )

    def parse_date_any(v):
        """Return date object or None."""
        if v is None:
            return None
        # Epoch timestamps (seconds or milliseconds)
        if isinstance(v, (int, float)):
            try:
                ts = float(v)
                # Heuristic: milliseconds are usually >= 1e12 for current-era timestamps
                if ts >= 1e12:
                    ts = ts / 1000.0
                dt = datetime.fromtimestamp(ts, tz=pytz.UTC).astimezone(ist)
                return dt.date()
            except Exception:
                return None
        if hasattr(v, 'date'):
            try:
                return v.date()
            except Exception:
                pass
        s = str(v).strip()
        if not s:
            return None
        # Numeric string epoch timestamp
        if s.isdigit():
            try:
                ts = float(s)
                if ts >= 1e12:
                    ts = ts / 1000.0
                dt = datetime.fromtimestamp(ts, tz=pytz.UTC).astimezone(ist)
                return dt.date()
            except Exception:
                pass
        # ISO-ish: 2025-12-01T00:00:00.000Z -> 2025-12-01
        if len(s) >= 10 and s[4] == '-' and s[7] == '-':
            try:
                return datetime.strptime(s[:10], '%Y-%m-%d').date()
            except ValueError:
                pass
        # Fallback formats
        for fmt in ('%d-%m-%Y', '%Y/%m/%d', '%d/%m/%Y'):
            try:
                return datetime.strptime(s[:10], fmt).date()
            except ValueError:
                continue
        return None

    # KPI sums
    loan_nos = set()
    principal_amount = 0.0
    net_disbursal = 0.0
    repayment_amount = 0.0
    collected_amount = 0.0
    pending_collection = 0.0
    pending_principal = 0.0
    principal_collection_excl_90 = 0.0

    # KPI Fresh/Reloan splits (same idea as Disbursal Summary cards)
    fresh_loan_nos = set()
    reloan_loan_nos = set()
    fresh_principal_amount = 0.0
    reloan_principal_amount = 0.0
    fresh_net_disbursal = 0.0
    reloan_net_disbursal = 0.0
    fresh_repayment_amount = 0.0
    reloan_repayment_amount = 0.0
    fresh_collected_amount = 0.0
    reloan_collected_amount = 0.0
    fresh_pending_collection = 0.0
    reloan_pending_collection = 0.0
    fresh_pending_principal = 0.0
    reloan_pending_principal = 0.0
    fresh_principal_collection_excl_90_dpd = 0.0
    reloan_principal_collection_excl_90_dpd = 0.0

    def as_bool(v):
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return float(v) != 0.0
        s = str(v).strip().lower()
        if s in ('true', '1', 'yes', 'y', 'reloan', 're-loan'):
            return True
        if s in ('false', '0', 'no', 'n', 'fresh', 'new'):
            return False
        return False

    def is_reloan_row(r):
        if not isinstance(r, dict):
            return False
        # direct keys
        for k in ('is_reloan_case', 'isReloanCase', 'is_reloan', 'isReloan', 'reloan_case', 'reloanCase'):
            if k in r:
                return as_bool(r.get(k))
        # case-insensitive keys
        lower_map = {str(k).lower(): k for k in r.keys()}
        for lk in ('is_reloan_case', 'isreloancase', 'is_reloan', 'isreloan'):
            if lk in lower_map:
                return as_bool(r.get(lower_map[lk]))
        # loan type strings
        for k in ('loan_type', 'loanType', 'type'):
            if k in r and r.get(k) is not None:
                s = str(r.get(k)).strip().lower()
                if 'reloan' in s:
                    return True
                if 'fresh' in s or 'new' in s:
                    return False
        return False

    # Dropdown options
    states = set()
    cities = set()
    actual_repayment_buckets = set()
    loan_pre_post_ontime_statuses = set()
    cities_by_state = defaultdict(set)

    # DPD distribution
    dpd_buckets = defaultdict(lambda: {'count': 0, 'amount': 0.0})

    # Amount Received Over Time (daily)
    # NOTE:
    # - For single-day ranges we may need to bucket rows even if row-level date is missing.
    # - For multi-day ranges we MUST NOT bucket unknown/out-of-range rows into date_from,
    #   otherwise tooltips become incorrect. Instead we auto-detect the best date field and
    #   only aggregate rows into days we can confidently parse.
    is_single_day = (date_from == date_to)
    daily = defaultdict(lambda: {'repayment': 0.0, 'net_disbursal': 0.0, 'collected': 0.0, 'principal': 0.0})
    daily_loan_nos = defaultdict(set)

    # Candidate date keys (from sample rows)
    candidate_date_keys = []
    try:
        sample_rows = [r for r in rows[:25] if isinstance(r, dict)]
        keys = set()
        for sr in sample_rows:
            for k in sr.keys():
                lk = str(k).lower()
                if (
                    'date' in lk or
                    lk.endswith('dt') or '_dt' in lk or
                    'time' in lk or
                    'received' in lk or 'collection' in lk or
                    'txn' in lk or 'transaction' in lk
                ):
                    keys.add(k)
        candidate_date_keys = sorted(list(keys))
    except Exception:
        candidate_date_keys = []

    # Preferred date keys for chart bucketing (collection/received first)
    priority_date_keys = [
        'date_of_received', 'date_of_recived', 'date_of_received_ist', 'date_of_recived_ist',
        'received_date', 'receivedDate',
        'collection_date', 'collectionDate', 'collection_date_ist',
        'transaction_date', 'txn_date',
        'date',
    ]

    # Auto-detect the best single key that yields the most in-range dates
    best_date_key = None
    try:
        keys_to_score = []
        # Keep priority keys first, then any other candidates
        for k in priority_date_keys:
            if k not in keys_to_score:
                keys_to_score.append(k)
        for k in candidate_date_keys:
            if k not in keys_to_score:
                keys_to_score.append(k)

        def score_key(k):
            hits = 0
            checked = 0
            for rr in rows[:200]:
                if not isinstance(rr, dict) or k not in rr:
                    continue
                checked += 1
                d0 = parse_date_any(rr.get(k))
                if d0 and date_from <= d0 <= date_to:
                    hits += 1
            return hits, checked

        best_hits = -1
        for k in keys_to_score:
            hits, checked = score_key(k)
            if hits > best_hits:
                best_hits = hits
                best_date_key = k
        if best_hits <= 0:
            best_date_key = None
    except Exception:
        best_date_key = None

    def extract_chart_date(row_dict):
        """Return the best in-range date for chart bucketing, or None."""
        # 1) Use the detected best key (if any)
        if best_date_key and best_date_key in row_dict:
            d0 = parse_date_any(row_dict.get(best_date_key))
            if d0:
                return d0

        # 2) Try priority keys
        for k in priority_date_keys:
            if k in row_dict:
                d0 = parse_date_any(row_dict.get(k))
                if d0:
                    return d0

        # 3) Try any remaining candidates
        for k in candidate_date_keys:
            if k in row_dict:
                try:
                    d0 = parse_date_any(row_dict.get(k))
                    if d0:
                        return d0
                except Exception:
                    continue
        return None

    # Determine which amount field to use for DPD bucket "Amount"
    # Prefer total_collection_amount, otherwise received_amount, otherwise loan_amount.
    def pick_amount_for_dpd(r):
        for key in ('total_collection_amount', 'received_amount', 'loan_amount'):
            if key in r and r.get(key) not in (None, ''):
                return to_float(r.get(key))
        return 0.0

    for r in rows:
        if not isinstance(r, dict):
            continue

        loan_no = r.get('loan_no') or r.get('loanNo') or r.get('loan_number')
        if loan_no:
            loan_nos.add(_norm(loan_no))
        reloan_flag = is_reloan_row(r)
        if loan_no:
            (reloan_loan_nos if reloan_flag else fresh_loan_nos).add(_norm(loan_no))

        principal_v = to_float(r.get('loan_amount') or r.get('principal_amount'))
        net_v = to_float(r.get('net_disbursal') or r.get('net_disbursed') or r.get('netDisbursal') or r.get('netDisbursed'))
        repay_v = to_float(r.get('actual_repayment') or r.get('repayment_amount') or r.get('repaymentAmount') or r.get('actualRepayment'))
        collected_v = to_float(r.get('received_amount') or r.get('receivedAmount') or r.get('collected_amount') or r.get('collectedAmount'))
        pending_coll_v = to_float(r.get('pending_collection') or r.get('pendingCollection') or r.get('pending_collection_amount'))
        pending_prin_v = to_float(r.get('pending_principal') or r.get('pendingPrincipal') or r.get('principal_outstanding') or r.get('principalOutstanding'))

        principal_amount += principal_v
        net_disbursal += net_v
        repayment_amount += repay_v
        collected_amount += collected_v
        pending_collection += pending_coll_v
        pending_principal += pending_prin_v

        if reloan_flag:
            reloan_principal_amount += principal_v
            reloan_net_disbursal += net_v
            reloan_repayment_amount += repay_v
            reloan_collected_amount += collected_v
            reloan_pending_collection += pending_coll_v
            reloan_pending_principal += pending_prin_v
        else:
            fresh_principal_amount += principal_v
            fresh_net_disbursal += net_v
            fresh_repayment_amount += repay_v
            fresh_collected_amount += collected_v
            fresh_pending_collection += pending_coll_v
            fresh_pending_principal += pending_prin_v

        st = r.get('state')
        ct = r.get('city')
        arb = r.get('actual_repayment_bucket')
        lps = r.get('loan_pre_post_ontime_status')
        if st:
            states.add(_norm(st))
        if ct:
            cities.add(_norm(ct))
        if st and ct:
            cities_by_state[_norm(st)].add(_norm(ct))
        if arb:
            actual_repayment_buckets.add(_norm(arb))
        if lps:
            loan_pre_post_ontime_statuses.add(_norm(lps))

        dpd_bucket = r.get('dpd_bucket') or r.get('dpdBucket')
        if dpd_bucket is not None and str(dpd_bucket).strip() != '':
            bucket = _norm(dpd_bucket)
            dpd_buckets[bucket]['count'] += 1
            dpd_buckets[bucket]['amount'] += pick_amount_for_dpd(r)

            # Principal Collection Excl. 90+ DPD (best-effort)
            b_lower = bucket.lower()
            is_90_plus = ('90' in b_lower and '+' in b_lower) or b_lower.strip() in ('90+', '90+dpd', '90+ dpd')
            if not is_90_plus:
                excl_v = to_float(r.get('total_collection_amount') or r.get('received_amount') or r.get('collection_amount'))
                principal_collection_excl_90 += excl_v
                if reloan_flag:
                    reloan_principal_collection_excl_90_dpd += excl_v
                else:
                    fresh_principal_collection_excl_90_dpd += excl_v

        # daily time series
        d = extract_chart_date(r)

        # For multi-day ranges: only bucket rows with a reliable in-range date.
        # For single-day: bucket unknown/missing dates into the selected day (so totals match).
        if d is None:
            if is_single_day:
                d = date_from
            else:
                continue
        if d < date_from or d > date_to:
            if is_single_day:
                d = date_from
            else:
                continue

        ds = d.strftime('%Y-%m-%d')
        daily[ds]['repayment'] += to_float(r.get('actual_repayment') or r.get('repayment_amount') or r.get('repaymentAmount'))
        daily[ds]['net_disbursal'] += to_float(r.get('net_disbursal') or r.get('net_disbursed') or r.get('netDisbursal') or r.get('netDisbursed'))
        # Keep chart "Collected" consistent with KPI "Collected Amount"
        daily[ds]['collected'] += to_float(r.get('received_amount') or r.get('receivedAmount') or r.get('collected_amount') or r.get('collectedAmount'))
        # Principal amount for tooltip (keep consistent with KPI Principal Amount)
        daily[ds]['principal'] += to_float(r.get('loan_amount') or r.get('principal_amount'))

        ln = r.get('loan_no') or r.get('loanNo') or r.get('loan_number')
        if ln:
            daily_loan_nos[ds].add(_norm(ln))

    total_applications = len(loan_nos)
    fresh_total_applications = len(fresh_loan_nos)
    reloan_total_applications = len(reloan_loan_nos)

    dpd_bucket_distribution = [
        {'dpd_bucket': b, 'count': v['count'], 'amount': v['amount']}
        for b, v in sorted(dpd_buckets.items(), key=lambda kv: kv[0])
    ]

    # Received Amount by State (bar chart) - from same filtered collection_summary rows only
    received_by_state = defaultdict(float)
    pending_by_state = defaultdict(float)
    for r in rows:
        if not isinstance(r, dict):
            continue
        st = r.get('state')
        if not st:
            continue
        st_norm = _norm(st)
        received_by_state[st_norm] += to_float(
            r.get('received_amount') or r.get('receivedAmount') or
            r.get('collected_amount') or r.get('collectedAmount')
        )
        # Pending amount: use pending_collection fields (consistent with KPI Pending Collection)
        pending_by_state[st_norm] += get_pending_collection_value(r)

    received_state_sorted = sorted(received_by_state.items(), key=lambda kv: kv[1], reverse=True)
    top_n = 15
    top_states = received_state_sorted[:top_n]
    other_sum = sum(v for _, v in received_state_sorted[top_n:])
    other_pending_sum = sum(pending_by_state.get(k, 0.0) for k, _ in received_state_sorted[top_n:])
    if other_sum > 0:
        top_states.append(('Others', other_sum))
    received_state_labels = [k for k, _ in top_states]
    received_state_values = [v for _, v in top_states]
    pending_state_values = [
        other_pending_sum if k == 'Others' else pending_by_state.get(k, 0.0)
        for k in received_state_labels
    ]

    # Top Cities – Collection Rate (%) (horizontal bar)
    # Define collection rate as Collected / (Collected + Pending) * 100
    city_stats = defaultdict(lambda: {'collected': 0.0, 'pending': 0.0})
    for r in rows:
        if not isinstance(r, dict):
            continue
        city = r.get('city')
        if not city:
            continue
        city_key = _norm(city)
        city_stats[city_key]['collected'] += to_float(
            r.get('received_amount') or r.get('receivedAmount') or
            r.get('collected_amount') or r.get('collectedAmount')
        )
        city_stats[city_key]['pending'] += get_pending_collection_value(r)

    def rate_color(pct):
        # Match screenshot-like bands
        if pct >= 94:
            return '#064e3b'  # dark green
        if pct >= 90:
            return '#22c55e'  # green
        if pct >= 80:
            return '#f97316'  # orange
        return '#ef4444'      # red

    city_rates = []
    for city, agg in city_stats.items():
        denom = (agg['collected'] + agg['pending'])
        pct = (agg['collected'] / denom * 100.0) if denom > 0 else 0.0
        city_rates.append({
            'city': city,
            'pct': pct,
            'collected': agg['collected'],
            'pending': agg['pending'],
            'color': rate_color(pct),
        })

    city_rates.sort(key=lambda x: x['pct'], reverse=True)
    top_city_rates = city_rates[:10]

    top_city_rate_labels = [x['city'] for x in top_city_rates]
    top_city_rate_values = [round(x['pct'], 2) for x in top_city_rates]
    top_city_rate_colors = [x['color'] for x in top_city_rates]
    top_city_rate_collected = [x['collected'] for x in top_city_rates]
    top_city_rate_pending = [x['pending'] for x in top_city_rates]

    # Pending Cases by Amount Bucket (mixed chart)
    # Buckets based on pending amount (pending_collection) in INR
    pending_bucket_labels = ['<5k', '5-10k', '10-20k', '20-30k', '30-40k', '40-50k', '50-60k', '60-70k', '70-80k', '80-90k', '90+k']
    pending_bucket_bounds = [0, 5000, 10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000, 90000]  # last is 90k+

    # Build per-loan pending to avoid double counting
    loan_pending = {}
    for idx, r in enumerate(rows):
        if not isinstance(r, dict):
            continue
        ln = r.get('loan_no') or r.get('loanNo') or r.get('loan_number') or r.get('loanNumber')
        rid = r.get('id') or r.get('loan_id') or r.get('loanId')
        key = _norm(ln) if ln else (str(rid) if rid is not None and str(rid).strip() != '' else f'row-{idx}')
        pv = get_pending_collection_value(r)
        if pv <= 0:
            continue
        prev = loan_pending.get(key)
        if prev is None or pv > prev:
            loan_pending[key] = pv

    pending_bucket_amounts = [0.0 for _ in pending_bucket_labels]
    pending_bucket_case_sets = [set() for _ in pending_bucket_labels]

    def bucket_index(amount):
        # amount is > 0
        for i in range(len(pending_bucket_bounds) - 1):
            lo = pending_bucket_bounds[i]
            hi = pending_bucket_bounds[i + 1]
            if lo <= amount < hi:
                return i
        return len(pending_bucket_labels) - 1  # 90k+

    for loan_key, amount in loan_pending.items():
        bi = bucket_index(amount)
        pending_bucket_case_sets[bi].add(loan_key)
        pending_bucket_amounts[bi] += amount

    pending_bucket_counts = [len(s) for s in pending_bucket_case_sets]

    # build full date range for chart (fill gaps with zeros)
    chart_dates = []
    chart_repayment = []
    chart_net_disbursal = []
    chart_collected = []
    chart_principal = []
    chart_counts = []
    cur = date_from
    while cur <= date_to:
        ds = cur.strftime('%Y-%m-%d')
        chart_dates.append(ds)
        chart_repayment.append(daily[ds]['repayment'] if ds in daily else 0.0)
        chart_net_disbursal.append(daily[ds]['net_disbursal'] if ds in daily else 0.0)
        chart_collected.append(daily[ds]['collected'] if ds in daily else 0.0)
        chart_principal.append(daily[ds]['principal'] if ds in daily else 0.0)
        chart_counts.append(len(daily_loan_nos.get(ds, set())))
        cur += timedelta(days=1)

    amount_received_over_time = json.dumps({
        'dates': chart_dates,
        'repayment_amounts': chart_repayment,
        'net_disbursal_amounts': chart_net_disbursal,
        'collected_amounts': chart_collected,
        'principal_amounts': chart_principal,
        'counts': chart_counts,
    })

    # Data table preview (avoid rendering thousands of rows by default)
    total_rows = len(rows)
    preview_limit = 200
    rows_preview = rows[:preview_limit] if isinstance(rows, list) else []

    context = {
        'api_error': api_error,
        'today_date': today_date.strftime('%Y-%m-%d'),
        'date_from': date_from.strftime('%Y-%m-%d'),
        'date_to': date_to.strftime('%Y-%m-%d'),
        'states': sorted(states),
        'cities': sorted(cities),
        'cities_by_state_json': json.dumps({k: sorted(list(v)) for k, v in sorted(cities_by_state.items(), key=lambda kv: kv[0])}),
        'actual_repayment_buckets': sorted(actual_repayment_buckets),
        'loan_pre_post_ontime_statuses': sorted(loan_pre_post_ontime_statuses),
        'selected_states': state_filters,
        'selected_cities': city_filters,
        'selected_actual_repayment_bucket': actual_repayment_bucket,
        'selected_loan_pre_post_ontime_status': loan_pre_post_ontime_status,
        'date_type': date_type,

        # KPIs
        'total_applications': total_applications,
        'principal_amount': principal_amount,
        'net_disbursal': net_disbursal,
        'repayment_amount': repayment_amount,
        'collected_amount': collected_amount,
        'pending_collection': pending_collection,
        'pending_principal': pending_principal,
        'principal_collection_excl_90_dpd': principal_collection_excl_90,

        # KPI splits
        'fresh_total_applications': fresh_total_applications,
        'reloan_total_applications': reloan_total_applications,
        'fresh_principal_amount': fresh_principal_amount,
        'reloan_principal_amount': reloan_principal_amount,
        'fresh_net_disbursal': fresh_net_disbursal,
        'reloan_net_disbursal': reloan_net_disbursal,
        'fresh_repayment_amount': fresh_repayment_amount,
        'reloan_repayment_amount': reloan_repayment_amount,
        'fresh_collected_amount': fresh_collected_amount,
        'reloan_collected_amount': reloan_collected_amount,
        'fresh_pending_collection': fresh_pending_collection,
        'reloan_pending_collection': reloan_pending_collection,
        'fresh_pending_principal': fresh_pending_principal,
        'reloan_pending_principal': reloan_pending_principal,
        'fresh_principal_collection_excl_90_dpd': fresh_principal_collection_excl_90_dpd,
        'reloan_principal_collection_excl_90_dpd': reloan_principal_collection_excl_90_dpd,

        # Tables / chart
        'dpd_bucket_distribution': dpd_bucket_distribution,
        'amount_received_over_time': amount_received_over_time,
        'received_state_labels': json.dumps(received_state_labels),
        'received_state_values': json.dumps(received_state_values),
        'pending_state_values': json.dumps(pending_state_values),
        'top_city_rate_labels': json.dumps(top_city_rate_labels),
        'top_city_rate_values': json.dumps(top_city_rate_values),
        'top_city_rate_colors': json.dumps(top_city_rate_colors),
        'top_city_rate_collected': json.dumps(top_city_rate_collected),
        'top_city_rate_pending': json.dumps(top_city_rate_pending),
        'pending_bucket_labels': json.dumps(pending_bucket_labels),
        'pending_bucket_counts': json.dumps(pending_bucket_counts),
        'pending_bucket_amounts': json.dumps(pending_bucket_amounts),
        # Backward-compatible (if referenced elsewhere)
        'received_state_data': json.dumps({'labels': received_state_labels, 'values': received_state_values}),
        'collection_data_total': total_rows,
        'collection_data_preview': rows_preview,
        'collection_data_preview_limit': preview_limit,
    }

    return render(request, 'dashboard/pages/collection_summary.html', context)


@login_required
@never_cache
def collection_with_fraud(request):
    """Collection With Fraud page view - Under Development"""
    return render(request, 'dashboard/pages/collection_summary.html')


@login_required
@never_cache
def loan_count_wise(request):
    """Loan Count Wise page view - Under Development"""
    return render(request, 'dashboard/pages/loan_count_wise.html')


@login_required
@never_cache
def daily_performance_metrics(request):
    """Daily Performance Metrics page view - Under Development"""
    return render(request, 'dashboard/pages/daily_performance_metrics.html')


@login_required
@never_cache
def credit_person_wise(request):
    """Credit Person Wise page view - Under Development"""
    return render(request, 'dashboard/pages/credit_person_wise.html')


@login_required
@never_cache
def aum_report(request):
    """
    AUM Report page view.
    IMPORTANT: This page uses ONLY api/collection/aum_static_data (no other APIs).
    """
    # --- Parse filters ---
    ist = pytz.timezone('Asia/Kolkata')
    today_date = datetime.now(ist).date()

    date_from_str = request.GET.get('date_from') or ''
    date_to_str = request.GET.get('date_to') or ''

    try:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date() if date_from_str else today_date
    except ValueError:
        date_from = today_date
    try:
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date() if date_to_str else today_date
    except ValueError:
        date_to = today_date

    if date_from > date_to:
        date_from, date_to = date_to, date_from

    state_filters = [s.strip() for s in request.GET.getlist('state') if str(s).strip()]
    city_filters = [c.strip() for c in request.GET.getlist('city') if str(c).strip()]

    # --- Fetch ONLY aum_static_data API ---
    api_url = 'https://backend.blinkrloan.com/api/collection/aum_static_data'

    params = [
        ('startDate', date_from.strftime('%Y-%m-%d')),
        ('endDate', date_to.strftime('%Y-%m-%d')),
    ]
    # Pass optional filters if API supports them (safe; we also filter server-side below)
    for s in state_filters:
        params.append(('state', s))
    for c in city_filters:
        params.append(('city', c))

    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    token = request.session.get('blinkr_token')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    else:
        api_key = os.environ.get('BLINKR_API_KEY') or getattr(settings, 'BLINKR_API_KEY', None)
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

    rows = []
    api_error = None
    try:
        print(f"[AUM Report] Fetching from: {api_url}")
        print(f"[AUM Report] Params: {params}")
        resp = requests.get(api_url, params=params, headers=headers, timeout=30)
        print(f"[AUM Report] Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            api_error = f"aum_static_data API returned {resp.status_code}: {resp.text[:200]}"
            print(f"[AUM Report] API Error: {api_error}")
        else:
            api_data = resp.json()
            print(f"[AUM Report] Response type: {type(api_data)}")
            print(f"[AUM Report] Response keys (if dict): {list(api_data.keys()) if isinstance(api_data, dict) else 'N/A (not a dict)'}")
            
            # Handle common wrappers
            if isinstance(api_data, dict):
                candidate = None
                for key in ('data', 'result', 'aum_static_data', 'aum_dpd_report', 'items', 'records', 'aum', 'dpd_report', 'response'):
                    if key in api_data:
                        candidate = api_data[key]
                        print(f"[AUM Report] Found data under key: {key}")
                        break
                if candidate is None:
                    # Check if the dict itself looks like a list of rows (unlikely but possible)
                    candidate = api_data
                    print(f"[AUM Report] Using entire dict as candidate")
            else:
                candidate = api_data
                print(f"[AUM Report] Response is not a dict, using directly")

            if isinstance(candidate, list):
                rows = candidate
                print(f"[AUM Report] ✓ Found {len(rows)} rows in list")
                if rows and len(rows) > 0:
                    print(f"[AUM Report] Sample row keys: {list(rows[0].keys()) if isinstance(rows[0], dict) else 'Not a dict'}")
                    if isinstance(rows[0], dict):
                        print(f"[AUM Report] Sample row (first 2000 chars): {str(rows[0])[:2000]}")
                        # Print all keys and their types
                        for key, value in list(rows[0].items())[:20]:  # First 20 fields
                            print(f"[AUM Report]   {key}: {type(value).__name__} = {str(value)[:100]}")
            elif isinstance(candidate, dict):
                # If dict is actually a single row
                rows = [candidate]
                print(f"[AUM Report] ✓ Treated dict as single row")
            else:
                rows = []
                print(f"[AUM Report] ⚠ Candidate is neither list nor dict: {type(candidate)}")
    except requests.RequestException as e:
        api_error = f"aum_static_data API request failed: {e}"
        print(f"[AUM Report] RequestException: {api_error}")
        rows = []
    except Exception as e:
        api_error = f"aum_static_data unexpected error: {e}"
        print(f"[AUM Report] Exception: {api_error}")
        import traceback
        traceback.print_exc()
        rows = []

    # --- Server-side filtering (still ONLY from this API response) ---
    def _norm(x):
        return str(x).strip()

    if state_filters:
        state_set = set(state_filters)
        rows = [r for r in rows if isinstance(r, dict) and _norm(r.get('state', '')) in state_set]
    if city_filters:
        city_set = set(city_filters)
        rows = [r for r in rows if isinstance(r, dict) and _norm(r.get('city', '')) in city_set]

    # --- Extract dropdown options from API response ---
    states = set()
    cities = set()
    cities_by_state = defaultdict(set)

    for r in rows:
        if not isinstance(r, dict):
            continue
        st = r.get('state')
        ct = r.get('city')
        if st:
            states.add(_norm(st))
        if ct:
            cities.add(_norm(ct))
        if st and ct:
            cities_by_state[_norm(st)].add(_norm(ct))

    # --- Process AUM data into monthly format ---
    def parse_date_any(value):
        """Parse various date formats from API response."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        s = str(value).strip()
        if not s:
            return None
        formats = [
            '%Y-%m-%d',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%d-%m-%Y',
            '%d/%m/%Y',
            '%Y/%m/%d',
            '%b-%y',  # Jun-25
            '%b %Y',  # Jun 2025
        ]
        for fmt in formats:
            try:
                return datetime.strptime(s.split('T')[0], fmt).date()
            except (ValueError, AttributeError):
                continue
        return None

    def to_float(v):
        """Convert value to float, handling currency symbols and commas."""
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace('₹', '').replace(',', '').replace(' ', '')
        try:
            return float(s)
        except (ValueError, TypeError):
            return 0.0

    # Helper function to determine if a row is reloan
    def as_bool(v):
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return float(v) != 0.0
        s = str(v).strip().lower()
        if s in ('true', '1', 'yes', 'y', 'reloan', 're-loan'):
            return True
        if s in ('false', '0', 'no', 'n', 'fresh', 'new'):
            return False
        return False

    def is_reloan_row(r):
        if not isinstance(r, dict):
            return False
        # direct keys
        for k in ('is_reloan_case', 'isReloanCase', 'is_reloan', 'isReloan', 'reloan_case', 'reloanCase'):
            if k in r:
                return as_bool(r.get(k))
        # case-insensitive keys
        lower_map = {str(k).lower(): k for k in r.keys()}
        for lk in ('is_reloan_case', 'isreloancase', 'is_reloan', 'isreloan'):
            if lk in lower_map:
                return as_bool(r.get(lower_map[lk]))
        # loan type strings
        for k in ('loan_type', 'loanType', 'type'):
            if k in r and r.get(k) is not None:
                s = str(r.get(k)).strip().lower()
                if 'reloan' in s:
                    return True
                if 'fresh' in s or 'new' in s:
                    return False
        return False

    # Group data by month with Fresh/Reloan splits
    monthly_data = defaultdict(lambda: {
        'stpl_units': 0, 'stpl_sum': 0.0,
        'stpl_fresh_units': 0, 'stpl_fresh_sum': 0.0,
        'stpl_reloan_units': 0, 'stpl_reloan_sum': 0.0,
        'loan_disbursed_fresh_units': 0, 'loan_disbursed_fresh_sum': 0.0,
        'loan_disbursed_repeat_units': 0, 'loan_disbursed_repeat_sum': 0.0,
        'loan_disbursed_total_units': 0, 'loan_disbursed_total_sum': 0.0,
        'running_cases_units': 0, 'running_cases_sum': 0.0,
        'running_cases_fresh_units': 0, 'running_cases_fresh_sum': 0.0,
        'running_cases_reloan_units': 0, 'running_cases_reloan_sum': 0.0,
        'overdue_1_30_units': 0, 'overdue_1_30_sum': 0.0,
        'overdue_31_90_units': 0, 'overdue_31_90_sum': 0.0,
        'overdue_90_plus_units': 0, 'overdue_90_plus_sum': 0.0,
        'loan_book_aum_units': 0, 'loan_book_aum_sum': 0.0,
        'loan_book_aum_fresh_units': 0, 'loan_book_aum_fresh_sum': 0.0,
        'loan_book_aum_reloan_units': 0, 'loan_book_aum_reloan_sum': 0.0,
        'ats': 0.0,
        'dpd_1_plus': 0.0,
        'dpd_30_plus': 0.0,
        'dpd_90_plus': 0.0,
        'pf_income': 0.0,
        'interest_income': 0.0,
        'avg_pf': 0.0,
        'avg_roi': 0.0,
        'avg_tenure': 0.0,
    })

    # Process rows and aggregate by month
    print(f"[AUM Report] Processing {len(rows)} rows for monthly aggregation...")
    processed_count = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        
        # Try to extract month from various date fields
        month_key = None
        date_fields_to_try = ['month', 'date', 'report_date', 'period', 'month_year', 'report_month', 'month_year', 'reporting_month', 'as_on_date', 'as_of_date']
        
        # First, check if any key contains 'month' or 'date' (case-insensitive)
        for key, value in r.items():
            key_lower = str(key).lower()
            if any(term in key_lower for term in ['month', 'date', 'period']):
                date_val = parse_date_any(value)
                if date_val:
                    month_key = date_val.strftime('%b-%y')  # Jun-25 format
                    print(f"[AUM Report] Found month from field '{key}': {month_key}")
                    break
        
        # If still not found, try explicit field names
        if not month_key:
            for date_field in date_fields_to_try:
                if date_field in r:
                    date_val = parse_date_any(r[date_field])
                    if date_val:
                        month_key = date_val.strftime('%b-%y')
                        print(f"[AUM Report] Found month from explicit field '{date_field}': {month_key}")
                        break
        
        # If no date found, try to infer from date range or use a default
        if not month_key:
            # Generate months from date range
            current_date = date_from
            months_in_range = []
            while current_date <= date_to:
                months_in_range.append(current_date.strftime('%b-%y'))
                # Move to next month
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)
            
            if months_in_range:
                month_key = months_in_range[0]  # Use first month in range
                print(f"[AUM Report] No date field found, using first month in range: {month_key}")
            else:
                month_key = date_from.strftime('%b-%y')
                print(f"[AUM Report] No date field found, using date_from: {month_key}")
        
        month_data = monthly_data[month_key]
        
        # Determine if this is a reloan
        is_reloan = is_reloan_row(r)
        
        # Map API fields to our structure (flexible field matching)
        def get_value(field_variations, default=0.0):
            for var in field_variations:
                if var in r:
                    return to_float(r[var])
                # Try case-insensitive
                for k, v in r.items():
                    if str(k).lower() == str(var).lower():
                        return to_float(v)
            return default
        
        # Get loan amount/disbursal amount for this row
        loan_amount = get_value(['loan_amount', 'loan_amt', 'principal_amount', 'principal', 'disbursal_amount', 'disbursal_amt', 'disbursed_amount'], 0.0)
        loan_count = 1  # Each row typically represents one loan
        
        # STPL - with Fresh/Reloan split
        stpl_amt = get_value(['stpl_units', 'stpl_count', 'stpl_loans', 'stpl_units_count', 'loan_amount', 'loan_amt'], loan_amount)
        stpl_sum = get_value(['stpl_sum', 'stpl_amount', 'stpl_total', 'stpl_amt', 'loan_amount', 'loan_amt'], loan_amount)
        month_data['stpl_units'] += int(stpl_amt) if stpl_amt > 0 else loan_count
        month_data['stpl_sum'] += stpl_sum
        if is_reloan:
            month_data['stpl_reloan_units'] += int(stpl_amt) if stpl_amt > 0 else loan_count
            month_data['stpl_reloan_sum'] += stpl_sum
        else:
            month_data['stpl_fresh_units'] += int(stpl_amt) if stpl_amt > 0 else loan_count
            month_data['stpl_fresh_sum'] += stpl_sum
        
        # Loan Disbursed - FRESH
        fresh_amt = get_value(['loan_disbursed_fresh_units', 'fresh_units', 'fresh_count', 'fresh_loans'], 0) if not is_reloan else 0
        fresh_sum = get_value(['loan_disbursed_fresh_sum', 'fresh_amount', 'fresh_total', 'fresh_amt'], loan_amount) if not is_reloan else 0.0
        month_data['loan_disbursed_fresh_units'] += int(fresh_amt) if fresh_amt > 0 else (loan_count if not is_reloan else 0)
        month_data['loan_disbursed_fresh_sum'] += fresh_sum
        
        # Loan Disbursed - REPEAT (Reloan)
        repeat_amt = get_value(['loan_disbursed_repeat_units', 'repeat_units', 'repeat_count', 'repeat_loans'], 0) if is_reloan else 0
        repeat_sum = get_value(['loan_disbursed_repeat_sum', 'repeat_amount', 'repeat_total', 'repeat_amt'], loan_amount) if is_reloan else 0.0
        month_data['loan_disbursed_repeat_units'] += int(repeat_amt) if repeat_amt > 0 else (loan_count if is_reloan else 0)
        month_data['loan_disbursed_repeat_sum'] += repeat_sum
        
        # Loan Disbursed - Total
        total_amt = get_value(['loan_disbursed_total_units', 'total_units', 'total_count', 'total_loans'], loan_count)
        total_sum = get_value(['loan_disbursed_total_sum', 'total_amount', 'total_total', 'total_amt'], loan_amount)
        month_data['loan_disbursed_total_units'] += int(total_amt) if total_amt > 0 else loan_count
        month_data['loan_disbursed_total_sum'] += total_sum
        
        # Running Cases - with Fresh/Reloan split
        running_amt = get_value(['running_cases_units', 'running_cases_count', 'active_cases', 'active_loans'], loan_count)
        running_sum = get_value(['running_cases_sum', 'running_cases_amount', 'active_amount', 'active_total'], loan_amount)
        month_data['running_cases_units'] += int(running_amt) if running_amt > 0 else loan_count
        month_data['running_cases_sum'] += running_sum
        if is_reloan:
            month_data['running_cases_reloan_units'] += int(running_amt) if running_amt > 0 else loan_count
            month_data['running_cases_reloan_sum'] += running_sum
        else:
            month_data['running_cases_fresh_units'] += int(running_amt) if running_amt > 0 else loan_count
            month_data['running_cases_fresh_sum'] += running_sum
        
        # Over Due +1-30 Day
        month_data['overdue_1_30_units'] += int(get_value(['overdue_1_30_units', 'overdue_1_30_count', 'dpd_1_30_count', 'dpd_1_30_units'], 0))
        month_data['overdue_1_30_sum'] += get_value(['overdue_1_30_sum', 'overdue_1_30_amount', 'dpd_1_30_amount', 'dpd_1_30_sum'], 0.0)
        
        # Over Due +31-90 Day
        month_data['overdue_31_90_units'] += int(get_value(['overdue_31_90_units', 'overdue_31_90_count', 'dpd_31_90_count', 'dpd_31_90_units'], 0))
        month_data['overdue_31_90_sum'] += get_value(['overdue_31_90_sum', 'overdue_31_90_amount', 'dpd_31_90_amount', 'dpd_31_90_sum'], 0.0)
        
        # Over Due 90+ Day
        month_data['overdue_90_plus_units'] += int(get_value(['overdue_90_plus_units', 'overdue_90_plus_count', 'dpd_90_plus_count', 'dpd_90_plus_units'], 0))
        month_data['overdue_90_plus_sum'] += get_value(['overdue_90_plus_sum', 'overdue_90_plus_amount', 'dpd_90_plus_amount', 'dpd_90_plus_sum'], 0.0)
        
        # Loan Book(AUM) - sum of running cases with Fresh/Reloan split
        month_data['loan_book_aum_units'] = month_data['running_cases_units']
        month_data['loan_book_aum_sum'] = month_data['running_cases_sum']
        month_data['loan_book_aum_fresh_units'] = month_data['running_cases_fresh_units']
        month_data['loan_book_aum_fresh_sum'] = month_data['running_cases_fresh_sum']
        month_data['loan_book_aum_reloan_units'] = month_data['running_cases_reloan_units']
        month_data['loan_book_aum_reloan_sum'] = month_data['running_cases_reloan_sum']
        
        # ATS (Average Ticket Size)
        if month_data['running_cases_units'] > 0:
            month_data['ats'] = month_data['running_cases_sum'] / month_data['running_cases_units']
        
        # DPD Percentages
        if month_data['running_cases_sum'] > 0:
            month_data['dpd_1_plus'] = ((month_data['overdue_1_30_sum'] + month_data['overdue_31_90_sum'] + month_data['overdue_90_plus_sum']) / month_data['running_cases_sum']) * 100
            month_data['dpd_30_plus'] = ((month_data['overdue_31_90_sum'] + month_data['overdue_90_plus_sum']) / month_data['running_cases_sum']) * 100
            month_data['dpd_90_plus'] = (month_data['overdue_90_plus_sum'] / month_data['running_cases_sum']) * 100
        
        # Income metrics
        month_data['pf_income'] += get_value(['pf_income', 'processing_fee_income', 'pf_income_gst'], 0.0)
        month_data['interest_income'] += get_value(['interest_income', 'interest'], 0.0)
        month_data['avg_pf'] += get_value(['avg_pf', 'average_pf', 'avg_processing_fee'], 0.0)
        month_data['avg_roi'] += get_value(['avg_roi', 'average_roi', 'roi'], 0.0)
        month_data['avg_tenure'] += get_value(['avg_tenure', 'average_tenure', 'tenure'], 0.0)
        
        processed_count += 1
        if processed_count <= 3:  # Log first 3 rows for debugging
            print(f"[AUM Report] Processed row {processed_count}, month_key: {month_key}, sample fields: {list(r.keys())[:10]}")

    print(f"[AUM Report] Processed {processed_count} rows into monthly data")
    
    # Sort months chronologically
    def month_sort_key(month_str):
        try:
            return datetime.strptime(month_str, '%b-%y')
        except:
            return datetime.min
    
    sorted_months = sorted(monthly_data.keys(), key=month_sort_key)
    
    # If no months found, generate months from date range
    if not sorted_months:
        print(f"[AUM Report] No months found in data, generating from date range: {date_from} to {date_to}")
        current_date = date_from
        while current_date <= date_to:
            month_str = current_date.strftime('%b-%y')
            if month_str not in monthly_data:
                monthly_data[month_str] = {
                    'stpl_units': 0, 'stpl_sum': 0.0,
                    'stpl_fresh_units': 0, 'stpl_fresh_sum': 0.0,
                    'stpl_reloan_units': 0, 'stpl_reloan_sum': 0.0,
                    'loan_disbursed_fresh_units': 0, 'loan_disbursed_fresh_sum': 0.0,
                    'loan_disbursed_repeat_units': 0, 'loan_disbursed_repeat_sum': 0.0,
                    'loan_disbursed_total_units': 0, 'loan_disbursed_total_sum': 0.0,
                    'running_cases_units': 0, 'running_cases_sum': 0.0,
                    'running_cases_fresh_units': 0, 'running_cases_fresh_sum': 0.0,
                    'running_cases_reloan_units': 0, 'running_cases_reloan_sum': 0.0,
                    'overdue_1_30_units': 0, 'overdue_1_30_sum': 0.0,
                    'overdue_31_90_units': 0, 'overdue_31_90_sum': 0.0,
                    'overdue_90_plus_units': 0, 'overdue_90_plus_sum': 0.0,
                    'loan_book_aum_units': 0, 'loan_book_aum_sum': 0.0,
                    'loan_book_aum_fresh_units': 0, 'loan_book_aum_fresh_sum': 0.0,
                    'loan_book_aum_reloan_units': 0, 'loan_book_aum_reloan_sum': 0.0,
                    'ats': 0.0,
                    'dpd_1_plus': 0.0,
                    'dpd_30_plus': 0.0,
                    'dpd_90_plus': 0.0,
                    'pf_income': 0.0,
                    'interest_income': 0.0,
                    'avg_pf': 0.0,
                    'avg_roi': 0.0,
                    'avg_tenure': 0.0,
                }
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        sorted_months = sorted(monthly_data.keys(), key=month_sort_key)
        print(f"[AUM Report] Generated {len(sorted_months)} months from date range: {sorted_months}")
    
    # Calculate total loan book AUM
    total_loan_book_aum = sum(month_data['loan_book_aum_sum'] for month_data in monthly_data.values())
    
    # Convert monthly_data to a list format for easier template access
    monthly_data_list = [{'month': month, 'data': monthly_data[month]} for month in sorted_months]

    # Data table preview (avoid rendering thousands of rows by default)
    total_rows = len(rows)
    preview_limit = 200
    rows_preview = rows[:preview_limit] if isinstance(rows, list) else []

    print(f"[AUM Report] Total rows after filtering: {total_rows}")
    print(f"[AUM Report] Preview rows: {len(rows_preview)}")
    print(f"[AUM Report] API error: {api_error}")
    print(f"[AUM Report] Monthly data keys: {sorted_months}")
    print(f"[AUM Report] Monthly data count: {len(monthly_data)}")
    if monthly_data:
        sample_month = sorted_months[0] if sorted_months else None
        if sample_month:
            print(f"[AUM Report] Sample month data ({sample_month}): {monthly_data[sample_month]}")

    context = {
        'api_error': api_error,
        'today_date': today_date.strftime('%Y-%m-%d'),
        'date_from': date_from.strftime('%Y-%m-%d'),
        'date_to': date_to.strftime('%Y-%m-%d'),
        'states': sorted(states),
        'cities': sorted(cities),
        'cities_by_state_json': json.dumps({k: sorted(list(v)) for k, v in sorted(cities_by_state.items(), key=lambda kv: kv[0])}),
        'selected_states': state_filters,
        'selected_cities': city_filters,
        'aum_data_total': total_rows,
        'aum_data_preview': rows_preview,
        'aum_data_preview_limit': preview_limit,
        'monthly_data': {month: monthly_data[month] for month in sorted_months},
        'monthly_data_list': monthly_data_list,
        'sorted_months': sorted_months,
        'total_loan_book_aum': total_loan_book_aum,
    }

    return render(request, 'dashboard/pages/aum_report.html', context)


@login_required
@never_cache
def prepayment_records_api(request):
    """
    API endpoint that returns prepayment records from collection API
    Used for opening prepayment records table from prepayment button
    """
    from django.http import JsonResponse
    
    # Get filter parameters from request
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    state_filters = request.GET.getlist('state')
    city_filters = request.GET.getlist('city')
    
    # Filter out empty strings
    state_filters = [s for s in state_filters if s]
    city_filters = [c for c in city_filters if c]
    
    # Set up timezone (IST - Asia/Kolkata)
    ist = pytz.timezone('Asia/Kolkata')
    
    # Parse date filters
    date_from = None
    date_to = None
    
    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Set default dates if not provided (today only in IST)
    now_ist = datetime.now(ist)
    if not date_from:
        date_from = now_ist.date()
    if not date_to:
        date_to = now_ist.date()
    
    # Fetch prepayment records from API
    try:
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Use token from session
        token = request.session.get('blinkr_token')
        if token:
            headers['Authorization'] = f'Bearer {token}'
        else:
            api_key = os.environ.get('BLINKR_API_KEY') or getattr(settings, 'BLINKR_API_KEY', None)
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
        
        records = []
        
        # Use collection_metrics API endpoint (same as used for collection metrics aggregation)
        # This endpoint returns individual collection records that we can filter for prepayment
        collection_api_url = 'https://backend.blinkrloan.com/insights/v2/collection_metrics'
        collection_params = {
            'startDate': date_from.strftime('%Y-%m-%d'),
            'endDate': date_to.strftime('%Y-%m-%d')
        }
        
        collection_found = False
        all_collection_records = []
        
        try:
            print(f"[Prepayment Records] Fetching from collection_metrics API: {collection_api_url}")
            print(f"[Prepayment Records] Date range: {date_from} to {date_to}")
            print(f"[Prepayment Records] Params: {collection_params}")
            print(f"[Prepayment Records] Full URL: {collection_api_url}?startDate={collection_params['startDate']}&endDate={collection_params['endDate']}")
            collection_response = requests.get(collection_api_url, params=collection_params, headers=headers, timeout=10)
            print(f"[Prepayment Records] Response status: {collection_response.status_code}")
            
            if collection_response and collection_response.status_code == 200:
                collection_data = collection_response.json()
                print(f"[Prepayment Records] Response type: {type(collection_data)}")
                
                # Log the full response structure first
                print(f"[Collection Metrics API] ===== FULL API RESPONSE STRUCTURE =====")
                if isinstance(collection_data, dict):
                    print(f"[Collection Metrics API] Top-level keys: {list(collection_data.keys())}")
                    for key in collection_data.keys():
                        value = collection_data[key]
                        print(f"[Collection Metrics API]   '{key}': type={type(value).__name__}, length={len(value) if isinstance(value, (list, dict, str)) else 'N/A'}")
                elif isinstance(collection_data, list):
                    print(f"[Collection Metrics API] Response is a list with {len(collection_data)} items")
                print(f"[Collection Metrics API] ======================================")
                
                # Extract records from response (same logic as collection metrics aggregation)
                if isinstance(collection_data, list):
                    all_collection_records = collection_data
                    collection_found = True
                    print(f"[Prepayment Records] ✓ Found {len(all_collection_records)} records (list response) from collection_metrics API")
                elif isinstance(collection_data, dict):
                    # Try different keys (same as collection metrics aggregation)
                    for key in ['data', 'result', 'records', 'items', 'collection_records', 'collections']:
                        if key in collection_data:
                            potential_records = collection_data[key]
                            if isinstance(potential_records, list) and len(potential_records) > 0:
                                all_collection_records = potential_records
                                collection_found = True
                                print(f"[Prepayment Records] ✓ Found {len(all_collection_records)} records in key '{key}' from collection_metrics API")
                                break
                    
                    # If no list found in common keys, check if the dict itself contains records
                    if not collection_found and len(collection_data) > 0:
                        print(f"[Prepayment Records] Response dict keys: {list(collection_data.keys())}")
                        # Check if any value is a list of records
                        for key, value in collection_data.items():
                            if isinstance(value, list) and len(value) > 0:
                                # Check if it looks like records (list of dicts)
                                if isinstance(value[0], dict):
                                    all_collection_records = value
                                    collection_found = True
                                    print(f"[Prepayment Records] ✓ Found {len(all_collection_records)} records in key '{key}' from collection_metrics API")
                                    break
            else:
                print(f"[Prepayment Records] API returned status {collection_response.status_code}")
                if collection_response.status_code != 200:
                    print(f"[Prepayment Records] Response text: {collection_response.text[:500]}")
        except requests.exceptions.Timeout:
            print(f"[Prepayment Records] API request timed out after 10 seconds")
        except Exception as e:
            print(f"[Prepayment Records] Error fetching from collection_metrics API: {str(e)}")
            import traceback
            print(f"[Prepayment Records] Traceback: {traceback.format_exc()}")
        
        if not collection_found:
            print(f"[Prepayment Records] ⚠ No collection records found from collection_metrics API")
        
        # If we found collection records, filter for prepayment
        if collection_found and all_collection_records:
            print(f"[Prepayment Records] ⚠ WARNING: API returned {len(all_collection_records)} records")
            print(f"[Prepayment Records] Date filter requested: {date_from} to {date_to}")
            print(f"[Prepayment Records] API may not be filtering by date - will filter client-side")
            print(f"[Prepayment Records] Filtering {len(all_collection_records)} collection records for prepayment...")
            
            # Debug: Print sample record to see available fields
            if all_collection_records and len(all_collection_records) > 0:
                sample = all_collection_records[0]
                print(f"[Prepayment Records] Sample record keys: {list(sample.keys()) if isinstance(sample, dict) else 'Not a dict'}")
                # Check what date fields are available
                date_fields_found = []
                for key in sample.keys() if isinstance(sample, dict) else []:
                    if 'date' in key.lower() or 'received' in key.lower():
                        date_fields_found.append(key)
                print(f"[Prepayment Records] Date-related fields found: {date_fields_found}")
                if date_fields_found:
                    print(f"[Prepayment Records] Sample date value: {sample.get(date_fields_found[0])}")
            
            # Filter records from collection_metrics API where prepayment_count OR prepayment_Amount is not zero
            # The user specified two fields: prepayment_count and prepayment_Amount (note capital A)
            for r in all_collection_records:
                if not isinstance(r, dict):
                    continue
                
                # Debug: Log ALL fields from collection_metrics for first record
                if len(records) == 0 and r == all_collection_records[0]:
                    print(f"[Collection Metrics API] ===== ALL FIELDS IN FIRST RECORD =====")
                    print(f"[Collection Metrics API] Total fields: {len(r.keys())}")
                    print(f"[Collection Metrics API] All field names:")
                    for i, key in enumerate(sorted(r.keys()), 1):
                        value = r[key]
                        value_str = str(value)
                        if len(value_str) > 100:
                            value_str = value_str[:100] + "..."
                        value_type = type(value).__name__
                        print(f"[Collection Metrics API]   {i:3d}. '{key}' ({value_type}): {value_str}")
                    
                    # Group fields by category for easier reading
                    print(f"\n[Collection Metrics API] ===== FIELD CATEGORIES =====")
                    
                    # Amount fields
                    amount_fields = [k for k in r.keys() if 'amount' in k.lower() or 'amt' in k.lower()]
                    print(f"[Collection Metrics API] Amount fields ({len(amount_fields)}): {amount_fields}")
                    
                    # Count fields
                    count_fields = [k for k in r.keys() if 'count' in k.lower() or 'cnt' in k.lower()]
                    print(f"[Collection Metrics API] Count fields ({len(count_fields)}): {count_fields}")
                    
                    # Date fields
                    date_fields = [k for k in r.keys() if 'date' in k.lower() or 'dt' in k.lower() or 'time' in k.lower()]
                    print(f"[Collection Metrics API] Date fields ({len(date_fields)}): {date_fields}")
                    
                    # Received/Collection fields
                    received_fields = [k for k in r.keys() if 'received' in k.lower() or 'receive' in k.lower() or 'collection' in k.lower()]
                    print(f"[Collection Metrics API] Received/Collection fields ({len(received_fields)}): {received_fields}")
                    
                    # Prepayment fields
                    prepayment_fields = [k for k in r.keys() if 'prepayment' in k.lower() or 'pre_payment' in k.lower()]
                    print(f"[Collection Metrics API] Prepayment fields ({len(prepayment_fields)}): {prepayment_fields}")
                    
                    # On-time/Due date fields
                    ontime_fields = [k for k in r.keys() if 'on_time' in k.lower() or 'ontime' in k.lower() or 'due_date' in k.lower() or 'duedate' in k.lower()]
                    print(f"[Collection Metrics API] On-time/Due date fields ({len(ontime_fields)}): {ontime_fields}")
                    
                    # Overdue fields
                    overdue_fields = [k for k in r.keys() if 'overdue' in k.lower()]
                    print(f"[Collection Metrics API] Overdue fields ({len(overdue_fields)}): {overdue_fields}")
                    
                    # Customer/Loan fields
                    customer_fields = [k for k in r.keys() if any(x in k.lower() for x in ['name', 'fullname', 'pan', 'mobile', 'phone', 'email', 'loan', 'city', 'state', 'address'])]
                    print(f"[Collection Metrics API] Customer/Loan fields ({len(customer_fields)}): {customer_fields}")
                    
                    print(f"[Collection Metrics API] ==========================================")
                
                # Check for prepayment_count field (exact match first, then case-insensitive)
                prepayment_count = 0
                row_keys_lower = {k.lower(): k for k in r.keys()}
                
                # Try all variations
                for field_name in ['prepayment_count', 'prepaymentCount', 'Prepayment_Count', 'PREPAYMENT_COUNT']:
                    if field_name in r:
                        try:
                            val = r[field_name]
                            prepayment_count = float(val if val is not None and val != '' else 0)
                            if len(records) < 3:  # Log first few
                                print(f"[Prepayment Records] Found prepayment_count in '{field_name}': {val} (converted to {prepayment_count})")
                            break
                        except (ValueError, TypeError) as e:
                            if len(records) < 3:
                                print(f"[Prepayment Records] Error converting prepayment_count from '{field_name}': {e}")
                            pass
                
                # Try case-insensitive if not found
                if prepayment_count == 0 and 'prepayment_count' in row_keys_lower:
                    actual_key = row_keys_lower['prepayment_count']
                    try:
                        val = r[actual_key]
                        prepayment_count = float(val if val is not None and val != '' else 0)
                        if len(records) < 3:
                            print(f"[Prepayment Records] Found prepayment_count in '{actual_key}' (case-insensitive): {val} (converted to {prepayment_count})")
                    except (ValueError, TypeError):
                        pass
                
                # Check for prepayment_Amount field (note: capital A as user specified)
                prepayment_amount = 0
                # Try all variations including exact case
                for field_name in ['prepayment_Amount', 'prepayment_amount', 'prepaymentAmount', 'Prepayment_Amount', 'PREPAYMENT_AMOUNT']:
                    if field_name in r:
                        try:
                            val = r[field_name]
                            prepayment_amount = float(val if val is not None and val != '' else 0)
                            if len(records) < 3:  # Log first few
                                print(f"[Prepayment Records] Found prepayment_Amount in '{field_name}': {val} (converted to {prepayment_amount})")
                            break
                        except (ValueError, TypeError) as e:
                            if len(records) < 3:
                                print(f"[Prepayment Records] Error converting prepayment_Amount from '{field_name}': {e}")
                            pass
                
                # Try case-insensitive if not found
                if prepayment_amount == 0 and 'prepayment_amount' in row_keys_lower:
                    actual_key = row_keys_lower['prepayment_amount']
                    try:
                        val = r[actual_key]
                        prepayment_amount = float(val if val is not None and val != '' else 0)
                        if len(records) < 3:
                            print(f"[Prepayment Records] Found prepayment_Amount in '{actual_key}' (case-insensitive): {val} (converted to {prepayment_amount})")
                    except (ValueError, TypeError):
                        pass
                
                # Debug: Log values for first few records
                if len(records) < 3:
                    print(f"[Prepayment Records] Record #{len(all_collection_records) - (len(all_collection_records) - len(records))}: prepayment_count={prepayment_count}, prepayment_Amount={prepayment_amount}")
                
                # Apply date filtering BEFORE adding to records
                # RELAXED date filtering: Include records if date matches OR if date field is missing (to avoid excluding valid records)
                date_match = True  # Default to True - include if date can't be determined
                if date_from and date_to:
                    date_received = None
                    date_fields = ['date_of_recived', 'date_of_received', 'dateOfReceived', 'received_date', 'receivedDate', 
                                  'collection_date', 'collectionDate', 'date_received', 'dateReceived']
                    
                    for field in date_fields:
                        if field in r:
                            date_received = r[field]
                            break
                    
                    # Try case-insensitive search
                    if date_received is None:
                        for field_lower in ['date_of_recived', 'date_of_received', 'dateofreceived', 'date_of_receive', 'dateofreceive',
                                          'received_date', 'receiveddate', 'collection_date', 'collectiondate',
                                          'date_received', 'datereceived']:
                            if field_lower in row_keys_lower:
                                actual_key = row_keys_lower[field_lower]
                                date_received = r[actual_key]
                                break
                    
                    if date_received:
                        try:
                            record_date = None
                            if isinstance(date_received, str):
                                for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%d-%m-%Y', '%d/%m/%Y']:
                                    try:
                                        record_date = datetime.strptime(date_received.split('T')[0], fmt).date()
                                        break
                                    except:
                                        continue
                            elif isinstance(date_received, datetime):
                                record_date = date_received.date()
                            
                            if record_date:
                                date_match = date_from <= record_date <= date_to
                                if len(records) < 3:
                                    print(f"[Prepayment Records] Date check: record_date={record_date}, range={date_from} to {date_to}, match={date_match}")
                            else:
                                # If can't parse date, include the record (RELAXED - don't exclude due to date parsing issues)
                                date_match = True
                                if len(records) < 3:
                                    print(f"[Prepayment Records] Could not parse date '{date_received}', including record anyway")
                        except Exception as e:
                            # If error parsing date, include the record (RELAXED)
                            date_match = True
                            if len(records) < 3:
                                print(f"[Prepayment Records] Error parsing date: {e}, including record anyway")
                    else:
                        # If no date field found, include the record (RELAXED - don't exclude due to missing date field)
                        date_match = True
                        if len(records) < 3:
                            print(f"[Prepayment Records] No date field found, including record anyway")
                
                # Include record if (prepayment_count > 0 OR prepayment_Amount > 0) AND date matches
                if (prepayment_count > 0 or prepayment_amount > 0) and date_match:
                    records.append(r)
                    if len(records) <= 5:  # Log first few matches
                        print(f"[Prepayment Records] ✓ Added record #{len(records)}: prepayment_count={prepayment_count}, prepayment_Amount={prepayment_amount}")
                else:
                    # Skip records where both prepayment fields are 0 or date doesn't match
                    if prepayment_count > 0 or prepayment_amount > 0:
                        if len(records) < 3:  # Log why records are excluded
                            print(f"[Prepayment Records] ⚠ Excluded record: prepayment_count={prepayment_count}, prepayment_Amount={prepayment_amount}, date_match={date_match}")
                    continue
            
            print(f"[Prepayment Records] ✓ Filtered {len(records)} prepayment records from {len(all_collection_records)} collection records")
        
        # DISABLED FALLBACK: Don't use disbursal records as fallback - only use collection records
        # This ensures we only show actual prepayment records from collection metrics API
        # The fallback was causing too many records (3857) to be included instead of the expected 12
        # if not collection_found or len(records) == 0:
        #     print(f"[Prepayment Records] Collection records API not available or no prepayment found, trying disbursal records as fallback...")
        #     ... (entire fallback block disabled)
        
        if not isinstance(records, list):
            records = []
        
        # Apply state and city filters
        if state_filters:
            records = [r for r in records if isinstance(r, dict) and r.get('state', '').strip() in state_filters]
        if city_filters:
            records = [r for r in records if isinstance(r, dict) and r.get('city', '').strip() in city_filters]
        
        # Debug: Print summary
        print(f"[Prepayment Records] Final result: {len(records)} records after filtering")
        if len(records) > 0:
            print(f"[Prepayment Records] Sample record keys: {list(records[0].keys())}")
        
        # If no records found, provide helpful debug info
        debug_info = None
        if len(records) == 0:
            debug_info = {
                'collection_api_found': collection_found,
                'total_collection_records': len(all_collection_records) if collection_found else 0,
                'message': 'No prepayment records found. Please verify the collection records API endpoint is available.'
            }
            if collection_found and all_collection_records:
                print(f"[Prepayment Records] No prepayment records found, but we have {len(all_collection_records)} collection records")
                if all_collection_records:
                    print(f"[Prepayment Records] Sample collection record keys: {list(all_collection_records[0].keys())}")
                    debug_info['sample_record_keys'] = list(all_collection_records[0].keys()) if all_collection_records else []
        
        # Debug: Print final records summary
        print(f"[Prepayment Records] ===== FINAL RESULT =====")
        print(f"[Prepayment Records] Total prepayment records found: {len(records)}")
        if len(records) > 0:
            print(f"[Prepayment Records] Sample record (first): {str(records[0])[:500]}")
            print(f"[Prepayment Records] Sample record keys: {list(records[0].keys()) if isinstance(records[0], dict) else 'Not a dict'}")
        print(f"[Prepayment Records] =========================")
        
        return JsonResponse({
            'records': records,
            'count': len(records),
            'type': 'prepayment',
            'debug_info': debug_info
        })
        
    except requests.RequestException as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[Prepayment Records] RequestException: {str(e)}")
        print(f"[Prepayment Records] Traceback: {error_trace}")
        return JsonResponse({'error': f'API request failed: {str(e)}'}, status=500)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[Prepayment Records] Exception: {str(e)}")
        print(f"[Prepayment Records] Traceback: {error_trace}")
        return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)


@login_required
@never_cache
def on_time_records_api(request):
    """
    API endpoint that returns on_time records from collection_metrics API
    Used for opening on_time records table from on_time button
    """
    from django.http import JsonResponse
    
    # Get filter parameters from request
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    state_filters = request.GET.getlist('state')
    city_filters = request.GET.getlist('city')
    
    # Filter out empty strings
    state_filters = [s for s in state_filters if s]
    city_filters = [c for c in city_filters if c]
    
    # Set up timezone (IST - Asia/Kolkata)
    ist = pytz.timezone('Asia/Kolkata')
    
    # Parse date filters
    date_from = None
    date_to = None
    
    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Set default dates if not provided (today only in IST)
    now_ist = datetime.now(ist)
    if not date_from:
        date_from = now_ist.date()
    if not date_to:
        date_to = now_ist.date()
    
    # Fetch on_time records from collection_metrics API
    try:
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Use token from session
        token = request.session.get('blinkr_token')
        if token:
            headers['Authorization'] = f'Bearer {token}'
        else:
            api_key = os.environ.get('BLINKR_API_KEY') or getattr(settings, 'BLINKR_API_KEY', None)
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
        
        records = []
        
        # Use collection_metrics API endpoint (same as prepayment)
        collection_api_url = 'https://backend.blinkrloan.com/insights/v2/collection_metrics'
        collection_params = {
            'startDate': date_from.strftime('%Y-%m-%d'),
            'endDate': date_to.strftime('%Y-%m-%d')
        }
        
        collection_found = False
        all_collection_records = []
        
        try:
            print(f"[On Time Records] Fetching from collection_metrics API: {collection_api_url}")
            print(f"[On Time Records] Date range: {date_from} to {date_to}")
            collection_response = requests.get(collection_api_url, params=collection_params, headers=headers, timeout=10)
            print(f"[On Time Records] Response status: {collection_response.status_code}")
            
            if collection_response and collection_response.status_code == 200:
                collection_data = collection_response.json()
                print(f"[On Time Records] Response type: {type(collection_data)}")
                
                # Extract records from response (same logic as prepayment)
                if isinstance(collection_data, list):
                    all_collection_records = collection_data
                    collection_found = True
                    print(f"[On Time Records] ✓ Found {len(all_collection_records)} records (list response)")
                elif isinstance(collection_data, dict):
                    for key in ['data', 'result', 'records', 'items', 'collection_records', 'collections']:
                        if key in collection_data:
                            potential_records = collection_data[key]
                            if isinstance(potential_records, list) and len(potential_records) > 0:
                                all_collection_records = potential_records
                                collection_found = True
                                print(f"[On Time Records] ✓ Found {len(all_collection_records)} records in key '{key}'")
                                break
                    
                    if not collection_found and len(collection_data) > 0:
                        print(f"[On Time Records] Response dict keys: {list(collection_data.keys())}")
                        for key, value in collection_data.items():
                            if isinstance(value, list) and len(value) > 0:
                                if isinstance(value[0], dict):
                                    all_collection_records = value
                                    collection_found = True
                                    print(f"[On Time Records] ✓ Found {len(all_collection_records)} records in key '{key}'")
                                    break
        except requests.exceptions.Timeout:
            print(f"[On Time Records] API request timed out after 10 seconds")
        except Exception as e:
            print(f"[On Time Records] Error fetching from collection_metrics API: {str(e)}")
            import traceback
            print(f"[On Time Records] Traceback: {traceback.format_exc()}")
        
        if not collection_found:
            print(f"[On Time Records] ⚠ No collection records found from collection_metrics API")
        
        # Filter records from collection_metrics API where due_date_amount OR on_time_amount is not zero
        if collection_found and all_collection_records:
            print(f"[On Time Records] Filtering {len(all_collection_records)} collection records for on_time...")
            
            # Debug: Log available columns from collection_metrics for first record
            if len(records) == 0 and all_collection_records and len(all_collection_records) > 0:
                sample = all_collection_records[0]
                print(f"[On Time Records] ===== COLLECTION_METRICS RECORD COLUMNS =====")
                print(f"[On Time Records] All columns: {list(sample.keys()) if isinstance(sample, dict) else 'Not a dict'}")
                on_time_keys = [k for k in sample.keys() if isinstance(sample, dict) and ('on_time' in k.lower() or 'due_date' in k.lower() or 'ontime' in k.lower())]
                print(f"[On Time Records] On-time-related columns: {on_time_keys}")
                if on_time_keys:
                    for key in on_time_keys:
                        print(f"[On Time Records]   '{key}': {sample[key]}")
                print(f"[On Time Records] ================================================")
            
            for r in all_collection_records:
                if not isinstance(r, dict):
                    continue
                
                # Check for due_date_amount and on_time_amount fields
                due_date_amount = 0
                on_time_amount = 0
                row_keys_lower = {k.lower(): k for k in r.keys()}
                
                # Check due_date_amount field variations
                for field_name in ['due_date_amount', 'dueDateAmount', 'due_date', 'dueDate', 'Due_Date_Amount', 'DUE_DATE_AMOUNT']:
                    if field_name in r:
                        try:
                            val = r[field_name]
                            due_date_amount = float(val if val is not None and val != '' else 0)
                            if due_date_amount > 0:
                                break
                        except (ValueError, TypeError):
                            pass
                
                # Try case-insensitive for due_date_amount
                if due_date_amount == 0 and 'due_date_amount' in row_keys_lower:
                    try:
                        val = r[row_keys_lower['due_date_amount']]
                        due_date_amount = float(val if val is not None and val != '' else 0)
                    except (ValueError, TypeError):
                        pass
                
                # Check on_time_amount field variations
                for field_name in ['on_time_amount', 'onTimeAmount', 'on_time_collection', 'onTimeCollection', 'on_time', 'onTime', 'On_Time_Amount', 'ON_TIME_AMOUNT']:
                    if field_name in r:
                        try:
                            val = r[field_name]
                            on_time_amount = float(val if val is not None and val != '' else 0)
                            if on_time_amount > 0:
                                break
                        except (ValueError, TypeError):
                            pass
                
                # Try case-insensitive for on_time_amount
                if on_time_amount == 0 and 'on_time_amount' in row_keys_lower:
                    try:
                        val = r[row_keys_lower['on_time_amount']]
                        on_time_amount = float(val if val is not None and val != '' else 0)
                    except (ValueError, TypeError):
                        pass
                
                # Apply date filtering (relaxed - include if date can't be determined)
                date_match = True
                if date_from and date_to:
                    date_received = None
                    date_fields = ['date_of_recived', 'date_of_received', 'dateOfReceived', 'received_date', 'receivedDate', 
                                  'collection_date', 'collectionDate', 'date_received', 'dateReceived']
                    
                    for field in date_fields:
                        if field in r:
                            date_received = r[field]
                            break
                    
                    if date_received is None:
                        for field_lower in ['date_of_recived', 'date_of_received', 'dateofreceived', 'date_of_receive', 'dateofreceive',
                                          'received_date', 'receiveddate', 'collection_date', 'collectiondate',
                                          'date_received', 'datereceived']:
                            if field_lower in row_keys_lower:
                                date_received = r[row_keys_lower[field_lower]]
                                break
                    
                    if date_received:
                        try:
                            record_date = None
                            if isinstance(date_received, str):
                                for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%d-%m-%Y', '%d/%m/%Y']:
                                    try:
                                        record_date = datetime.strptime(date_received.split('T')[0], fmt).date()
                                        break
                                    except:
                                        continue
                            elif isinstance(date_received, datetime):
                                record_date = date_received.date()
                            
                            if record_date:
                                date_match = date_from <= record_date <= date_to
                            else:
                                date_match = True  # Include if can't parse
                        except Exception as e:
                            date_match = True  # Include if error parsing
                    else:
                        date_match = True  # Include if no date field
                
                # Include record if (due_date_amount > 0 OR on_time_amount > 0) AND date matches
                if (due_date_amount > 0 or on_time_amount > 0) and date_match:
                    records.append(r)
                    if len(records) <= 5:
                        print(f"[On Time Records] ✓ Added record #{len(records)}: due_date_amount={due_date_amount}, on_time_amount={on_time_amount}")
            
            print(f"[On Time Records] ✓ Filtered {len(records)} on_time records from {len(all_collection_records)} collection records")
        
        # Apply state and city filters
        if state_filters:
            records = [r for r in records if isinstance(r, dict) and r.get('state', '').strip() in state_filters]
        if city_filters:
            records = [r for r in records if isinstance(r, dict) and r.get('city', '').strip() in city_filters]
        
        print(f"[On Time Records] Final result: {len(records)} records after filtering")
        
        return JsonResponse({
            'records': records,
            'count': len(records),
            'type': 'on_time'
        })
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[On Time Records] Exception: {str(e)}")
        print(f"[On Time Records] Traceback: {error_trace}")
        return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)


@login_required
@never_cache
def overdue_records_api(request):
    """
    API endpoint that returns overdue records from collection_metrics API
    Used for opening overdue records table from overdue button
    """
    from django.http import JsonResponse
    
    # Get filter parameters from request
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    state_filters = request.GET.getlist('state')
    city_filters = request.GET.getlist('city')
    
    # Filter out empty strings
    state_filters = [s for s in state_filters if s]
    city_filters = [c for c in city_filters if c]
    
    # Set up timezone (IST - Asia/Kolkata)
    ist = pytz.timezone('Asia/Kolkata')
    
    # Parse date filters
    date_from = None
    date_to = None
    
    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Set default dates if not provided (today only in IST)
    now_ist = datetime.now(ist)
    if not date_from:
        date_from = now_ist.date()
    if not date_to:
        date_to = now_ist.date()
    
    # Fetch overdue records from collection_metrics API
    try:
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Use token from session
        token = request.session.get('blinkr_token')
        if token:
            headers['Authorization'] = f'Bearer {token}'
        else:
            api_key = os.environ.get('BLINKR_API_KEY') or getattr(settings, 'BLINKR_API_KEY', None)
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
        
        records = []
        
        # Use collection_metrics API endpoint (same as prepayment)
        collection_api_url = 'https://backend.blinkrloan.com/insights/v2/collection_metrics'
        collection_params = {
            'startDate': date_from.strftime('%Y-%m-%d'),
            'endDate': date_to.strftime('%Y-%m-%d')
        }
        
        collection_found = False
        all_collection_records = []
        
        try:
            print(f"[Overdue Records] Fetching from collection_metrics API: {collection_api_url}")
            print(f"[Overdue Records] Date range: {date_from} to {date_to}")
            collection_response = requests.get(collection_api_url, params=collection_params, headers=headers, timeout=10)
            print(f"[Overdue Records] Response status: {collection_response.status_code}")
            
            if collection_response and collection_response.status_code == 200:
                collection_data = collection_response.json()
                print(f"[Overdue Records] Response type: {type(collection_data)}")
                
                # Extract records from response (same logic as prepayment)
                if isinstance(collection_data, list):
                    all_collection_records = collection_data
                    collection_found = True
                    print(f"[Overdue Records] ✓ Found {len(all_collection_records)} records (list response)")
                elif isinstance(collection_data, dict):
                    for key in ['data', 'result', 'records', 'items', 'collection_records', 'collections']:
                        if key in collection_data:
                            potential_records = collection_data[key]
                            if isinstance(potential_records, list) and len(potential_records) > 0:
                                all_collection_records = potential_records
                                collection_found = True
                                print(f"[Overdue Records] ✓ Found {len(all_collection_records)} records in key '{key}'")
                                break
                    
                    if not collection_found and len(collection_data) > 0:
                        print(f"[Overdue Records] Response dict keys: {list(collection_data.keys())}")
                        for key, value in collection_data.items():
                            if isinstance(value, list) and len(value) > 0:
                                if isinstance(value[0], dict):
                                    all_collection_records = value
                                    collection_found = True
                                    print(f"[Overdue Records] ✓ Found {len(all_collection_records)} records in key '{key}'")
                                    break
        except requests.exceptions.Timeout:
            print(f"[Overdue Records] API request timed out after 10 seconds")
        except Exception as e:
            print(f"[Overdue Records] Error fetching from collection_metrics API: {str(e)}")
            import traceback
            print(f"[Overdue Records] Traceback: {traceback.format_exc()}")
        
        if not collection_found:
            print(f"[Overdue Records] ⚠ No collection records found from collection_metrics API")
        
        # Filter records from collection_metrics API where overdue_amount is not zero
        if collection_found and all_collection_records:
            print(f"[Overdue Records] Filtering {len(all_collection_records)} collection records for overdue...")
            
            # Debug: Log available columns from collection_metrics for first record
            if len(records) == 0 and all_collection_records and len(all_collection_records) > 0:
                sample = all_collection_records[0]
                print(f"[Overdue Records] ===== COLLECTION_METRICS RECORD COLUMNS =====")
                print(f"[Overdue Records] All columns: {list(sample.keys()) if isinstance(sample, dict) else 'Not a dict'}")
                overdue_keys = [k for k in sample.keys() if isinstance(sample, dict) and 'overdue' in k.lower()]
                print(f"[Overdue Records] Overdue-related columns: {overdue_keys}")
                if overdue_keys:
                    for key in overdue_keys:
                        print(f"[Overdue Records]   '{key}': {sample[key]}")
                print(f"[Overdue Records] ================================================")
            
            for r in all_collection_records:
                if not isinstance(r, dict):
                    continue
                
                # Check for overdue_amount field
                overdue_amount = 0
                row_keys_lower = {k.lower(): k for k in r.keys()}
                
                # Check overdue_amount field variations
                for field_name in ['overdue_amount', 'overdueAmount', 'overdue_collection', 'overdueCollection', 'overdue', 'overDue', 'Overdue_Amount', 'OVERDUE_AMOUNT']:
                    if field_name in r:
                        try:
                            val = r[field_name]
                            overdue_amount = float(val if val is not None and val != '' else 0)
                            if overdue_amount > 0:
                                break
                        except (ValueError, TypeError):
                            pass
                
                # Try case-insensitive for overdue_amount
                if overdue_amount == 0 and 'overdue_amount' in row_keys_lower:
                    try:
                        val = r[row_keys_lower['overdue_amount']]
                        overdue_amount = float(val if val is not None and val != '' else 0)
                    except (ValueError, TypeError):
                        pass
                
                # Apply date filtering (relaxed - include if date can't be determined)
                date_match = True
                if date_from and date_to:
                    date_received = None
                    date_fields = ['date_of_recived', 'date_of_received', 'dateOfReceived', 'received_date', 'receivedDate', 
                                  'collection_date', 'collectionDate', 'date_received', 'dateReceived']
                    
                    for field in date_fields:
                        if field in r:
                            date_received = r[field]
                            break
                    
                    if date_received is None:
                        for field_lower in ['date_of_recived', 'date_of_received', 'dateofreceived', 'date_of_receive', 'dateofreceive',
                                          'received_date', 'receiveddate', 'collection_date', 'collectiondate',
                                          'date_received', 'datereceived']:
                            if field_lower in row_keys_lower:
                                date_received = r[row_keys_lower[field_lower]]
                                break
                    
                    if date_received:
                        try:
                            record_date = None
                            if isinstance(date_received, str):
                                for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%d-%m-%Y', '%d/%m/%Y']:
                                    try:
                                        record_date = datetime.strptime(date_received.split('T')[0], fmt).date()
                                        break
                                    except:
                                        continue
                            elif isinstance(date_received, datetime):
                                record_date = date_received.date()
                            
                            if record_date:
                                date_match = date_from <= record_date <= date_to
                            else:
                                date_match = True  # Include if can't parse
                        except Exception as e:
                            date_match = True  # Include if error parsing
                    else:
                        date_match = True  # Include if no date field
                
                # Include record if overdue_amount > 0 AND date matches
                if overdue_amount > 0 and date_match:
                    records.append(r)
                    if len(records) <= 5:
                        print(f"[Overdue Records] ✓ Added record #{len(records)}: overdue_amount={overdue_amount}")
            
            print(f"[Overdue Records] ✓ Filtered {len(records)} overdue records from {len(all_collection_records)} collection records")
        
        # Apply state and city filters
        if state_filters:
            records = [r for r in records if isinstance(r, dict) and r.get('state', '').strip() in state_filters]
        if city_filters:
            records = [r for r in records if isinstance(r, dict) and r.get('city', '').strip() in city_filters]
        
        print(f"[Overdue Records] Final result: {len(records)} records after filtering")
        
        return JsonResponse({
            'records': records,
            'count': len(records),
            'type': 'overdue'
        })
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[Overdue Records] Exception: {str(e)}")
        print(f"[Overdue Records] Traceback: {error_trace}")
        return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)
