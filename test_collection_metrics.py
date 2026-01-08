#!/usr/bin/env python3
"""
Test script to diagnose Collection Metrics API issues
"""
import requests
import json
from datetime import datetime, date

# Test the Collection Metrics API directly
def test_collection_metrics_api():
    # Use today's date
    today = date.today()
    start_date = today.strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    
    api_url = 'https://backend.blinkrloan.com/insights/v2/collection_metrics'
    params = {
        'startDate': start_date,
        'endDate': end_date
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    # NOTE: You need to provide a valid token here
    # Get it from your Django session or login API
    token = input("Enter your blinkr_token (or press Enter to test without token): ").strip()
    
    if token:
        headers['Authorization'] = f'Bearer {token}'
        print(f"✓ Using token: {token[:30]}...{token[-10:]}")
    else:
        print("⚠ Testing without token (will likely fail)")
    
    print(f"\n{'='*60}")
    print(f"Testing Collection Metrics API")
    print(f"{'='*60}")
    print(f"URL: {api_url}")
    print(f"Params: {params}")
    print(f"Headers: {json.dumps({k: (v[:50] + '...' if len(v) > 50 else v) for k, v in headers.items()}, indent=2)}")
    print(f"{'='*60}\n")
    
    try:
        response = requests.get(api_url, params=params, headers=headers, timeout=30)
        
        print(f"Response Status: {response.status_code}")
        print(f"Response URL: {response.url}")
        print(f"\nResponse Headers:")
        for k, v in response.headers.items():
            print(f"  {k}: {v}")
        
        print(f"\n{'='*60}")
        print(f"Response Body:")
        print(f"{'='*60}")
        
        try:
            response_json = response.json()
            print(json.dumps(response_json, indent=2))
            
            # Analyze the response structure
            print(f"\n{'='*60}")
            print(f"Response Analysis:")
            print(f"{'='*60}")
            
            if isinstance(response_json, dict):
                print(f"✓ Response is a dictionary")
                print(f"  Keys: {list(response_json.keys())}")
                
                # Check for errors
                if 'message' in response_json:
                    print(f"\n✗ ERROR MESSAGE: {response_json['message']}")
                if 'error' in response_json:
                    print(f"\n✗ ERROR: {response_json['error']}")
                
                # Check for data in different keys
                if 'data' in response_json:
                    print(f"\n✓ Found 'data' key")
                    print(f"  Data type: {type(response_json['data'])}")
                    if isinstance(response_json['data'], dict):
                        print(f"  Data keys: {list(response_json['data'].keys())}")
                        for k, v in response_json['data'].items():
                            print(f"    {k}: {v} (type: {type(v).__name__})")
                
                if 'result' in response_json:
                    print(f"\n✓ Found 'result' key")
                    print(f"  Result type: {type(response_json['result'])}")
                    if isinstance(response_json['result'], dict):
                        print(f"  Result keys: {list(response_json['result'].keys())}")
                
                if 'metrics' in response_json:
                    print(f"\n✓ Found 'metrics' key")
                    print(f"  Metrics type: {type(response_json['metrics'])}")
                    if isinstance(response_json['metrics'], dict):
                        print(f"  Metrics keys: {list(response_json['metrics'].keys())}")
                
                # Check if it's the metrics directly
                possible_metric_keys = [
                    'total_collection_amount', 'totalCollectionAmount',
                    'on_time_collection', 'onTimeCollection',
                    'overdue_collection', 'overdueCollection'
                ]
                found_keys = [k for k in possible_metric_keys if k in response_json]
                if found_keys:
                    print(f"\n✓ Found metric keys directly in response: {found_keys}")
                    for k in found_keys:
                        print(f"    {k}: {response_json[k]}")
                else:
                    print(f"\n⚠ No direct metric keys found in response")
                    
            elif isinstance(response_json, list):
                print(f"✓ Response is a list with {len(response_json)} items")
                if len(response_json) > 0:
                    print(f"  First item type: {type(response_json[0])}")
                    if isinstance(response_json[0], dict):
                        print(f"  First item keys: {list(response_json[0].keys())}")
            else:
                print(f"⚠ Unexpected response type: {type(response_json)}")
                
        except json.JSONDecodeError:
            print(f"✗ Response is not valid JSON")
            print(f"Response text (first 1000 chars):")
            print(response.text[:1000])
            
    except requests.exceptions.Timeout:
        print(f"✗ Request timed out after 30 seconds")
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_collection_metrics_api()

