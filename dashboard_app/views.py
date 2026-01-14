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
from datetime import datetime, timedelta
import json
import requests
from collections import defaultdict
import pytz
import os


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
    def aggregate_collection_metrics(rows):
        """Aggregate collection metrics from multiple rows into a single dict"""
        if not rows or len(rows) == 0:
            return {}
        
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
        
        # Field name mappings - map various API field names to our standard names
        field_mappings = {
            # Amount fields
            'total_collection_amount': ['total_collection_amount', 'totalCollectionAmount', 'total_amount', 'collection_amount', 'total'],
            'fresh_collection_amount': ['fresh_collection_amount', 'freshCollectionAmount', 'fresh_amount', 'fresh'],
            'reloan_collection_amount': ['reloan_collection_amount', 'reloanCollectionAmount', 'reloan_amount', 'reloan'],
            'prepayment_amount': ['prepayment_amount', 'prepaymentAmount', 'prepayment'],
            'due_date_amount': ['due_date_amount', 'dueDateAmount', 'on_time_collection', 'onTimeCollection', 'on_time_amount', 'onTimeAmount', 'ontime_amount', 'ontimeAmount', 'onTime_amount', 'on_time_collection_amount', 'onTimeCollectionAmount', 'due_date_collection', 'dueDateCollection', 'on_time_amount_collection', 'onTimeAmountCollection'],
            'overdue_amount': ['overdue_amount', 'overdueAmount', 'overdue_collection', 'overdueCollection', 'overdue_collection_amount', 'overdueCollectionAmount'],
            # Count fields
            'total_collection_count': ['total_collection_count', 'totalCollectionCount', 'total_count', 'totalCount', 'total'],
            'fresh_collection_count': ['fresh_collection_count', 'freshCollectionCount', 'fresh_count', 'freshCount', 'fresh'],
            'reloan_collection_count': ['reloan_collection_count', 'reloanCollectionCount', 'reloan_count', 'reloanCount', 'reloan'],
            'prepayment_count': ['prepayment_count', 'prepaymentCount', 'prepayment'],
            'due_date_count': ['due_date_count', 'dueDateCount', 'on_time_count', 'onTimeCount', 'onTime', 'ontime', 'ontime_count', 'onTime_count', 'on_time_collection_count', 'onTimeCollectionCount', 'due_date_collection_count', 'dueDateCollectionCount'],
            'overdue_count': ['overdue_count', 'overdueCount', 'overdue']
        }
        
        for row in rows:
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
                if standard_field not in field_mappings:
                    continue
                variations = field_mappings[standard_field]
                found = False
                for variation in variations:
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
                                break  # Found it, move to next field
                            except (ValueError, TypeError):
                                pass
                    # Try case-insensitive match
                    elif variation.lower() in row_keys_lower:
                        actual_key = row_keys_lower[variation.lower()]
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
        
        # Reduced timeout for faster page load (10 seconds instead of 30)
        collection_response = requests.get(collection_api_url, params=collection_params, headers=collection_headers, timeout=10)
        
        if collection_response.status_code == 200:
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
                            collection_metrics = aggregate_collection_metrics(data_value)
                        elif isinstance(data_value, dict):
                            collection_metrics = data_value
                        else:
                            collection_metrics = {}
                    elif 'result' in collection_data and not collection_metrics:
                        result_value = collection_data['result']
                        if isinstance(result_value, list) and len(result_value) > 0:
                            # Aggregate all rows instead of just taking the first
                            print(f"[Collection Metrics] Found {len(result_value)} rows in 'result', aggregating all...")
                            collection_metrics = aggregate_collection_metrics(result_value)
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
                elif isinstance(collection_data, list) and len(collection_data) > 0:
                    # Aggregate all rows instead of just taking the first
                    print(f"[Collection Metrics] Found {len(collection_data)} rows in list, aggregating all...")
                    collection_metrics = aggregate_collection_metrics(collection_data)
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
        print(f"[API Endpoint] ===== STARTING COLLECTION METRICS API CALL =====")
        print(f"[API Endpoint] Using date range from filters: {date_from} to {date_to}")
        collection_metrics = {}
        
        # Helper function to aggregate multiple rows of collection metrics
        def aggregate_collection_metrics(rows):
            """Aggregate collection metrics from multiple rows into a single dict"""
            if not rows or len(rows) == 0:
                return {}
            
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
            
            # Field name mappings - map various API field names to our standard names
            field_mappings = {
                # Amount fields
                'total_collection_amount': ['total_collection_amount', 'totalCollectionAmount', 'total_amount', 'collection_amount', 'total'],
                'fresh_collection_amount': ['fresh_collection_amount', 'freshCollectionAmount', 'fresh_amount', 'fresh'],
                'reloan_collection_amount': ['reloan_collection_amount', 'reloanCollectionAmount', 'reloan_amount', 'reloan'],
                'prepayment_amount': ['prepayment_amount', 'prepaymentAmount', 'prepayment'],
                'due_date_amount': ['due_date_amount', 'dueDateAmount', 'on_time_collection', 'onTimeCollection', 'on_time_amount', 'onTimeAmount', 'ontime_amount', 'ontimeAmount', 'onTime_amount', 'on_time_collection_amount', 'onTimeCollectionAmount', 'due_date_collection', 'dueDateCollection', 'on_time_amount_collection', 'onTimeAmountCollection'],
                'overdue_amount': ['overdue_amount', 'overdueAmount', 'overdue_collection', 'overdueCollection', 'overdue_collection_amount', 'overdueCollectionAmount'],
                # Count fields
                'total_collection_count': ['total_collection_count', 'totalCollectionCount', 'total_count', 'totalCount', 'total'],
                'fresh_collection_count': ['fresh_collection_count', 'freshCollectionCount', 'fresh_count', 'freshCount', 'fresh'],
                'reloan_collection_count': ['reloan_collection_count', 'reloanCollectionCount', 'reloan_count', 'reloanCount', 'reloan'],
                'prepayment_count': ['prepayment_count', 'prepaymentCount', 'prepayment'],
                'due_date_count': ['due_date_count', 'dueDateCount', 'on_time_count', 'onTimeCount', 'onTime'],
                'overdue_count': ['overdue_count', 'overdueCount', 'overdue']
            }
            
            for row in rows:
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
                    if standard_field not in field_mappings:
                        continue
                    variations = field_mappings[standard_field]
                    found = False
                    for variation in variations:
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
                                    break  # Found it, move to next field
                                except (ValueError, TypeError):
                                    pass
                        # Try case-insensitive match
                        elif variation.lower() in row_keys_lower:
                            actual_key = row_keys_lower[variation.lower()]
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
            
            collection_response = requests.get(collection_api_url, params=collection_params, headers=collection_headers, timeout=30)
            print(f"[API Endpoint] Collection Metrics API Response Status: {collection_response.status_code}")
            print(f"[API Endpoint] Collection Metrics API Response URL: {collection_response.url}")
            
            if collection_response.status_code == 200:
                try:
                    collection_data = collection_response.json()
                    print(f"[API Endpoint] Collection Metrics API Response: {json.dumps(collection_data, indent=2)}")
                    
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
                                collection_metrics = aggregate_collection_metrics(data_value)
                                print(f"[API Endpoint] Collection Metrics aggregated from all rows: {collection_metrics}")
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
                                collection_metrics = aggregate_collection_metrics(result_value)
                                print(f"[API Endpoint] Collection Metrics aggregated from 'result': {collection_metrics}")
                            else:
                                collection_metrics = result_value if isinstance(result_value, dict) else {}
                                print(f"[API Endpoint] Collection Metrics found in 'result' key: {collection_metrics}")
                        elif 'metrics' in collection_data and not collection_metrics:
                            metrics_value = collection_data['metrics']
                            if isinstance(metrics_value, list) and len(metrics_value) > 0:
                                # Aggregate all rows instead of just taking the first
                                print(f"[API Endpoint] Collection Metrics found {len(metrics_value)} rows in 'metrics', aggregating all...")
                                collection_metrics = aggregate_collection_metrics(metrics_value)
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
                        collection_metrics = aggregate_collection_metrics(collection_data)
                        print(f"[API Endpoint] Collection Metrics aggregated from all rows: {collection_metrics}")
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
    """Collection Summary page view - Under Development"""
    return render(request, 'dashboard/pages/collection_summary.html')


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
    """AUM Report page view - Under Development"""
    return render(request, 'dashboard/pages/aum_report.html')
