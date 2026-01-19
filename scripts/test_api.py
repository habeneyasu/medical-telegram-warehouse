#!/usr/bin/env python3
"""
Simple API test script to verify all endpoints are working.

Usage:
    python3 scripts/test_api.py [base_url]
    
Example:
    python3 scripts/test_api.py http://localhost:8000
"""

import sys
import json
from pathlib import Path
from typing import Optional

import requests

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"


def test_endpoint(name: str, method: str, url: str, params: Optional[dict] = None, expected_status: int = 200):
    """Test an API endpoint."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"URL: {url}")
    if params:
        print(f"Params: {params}")
    print(f"{'='*60}")
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, params=params, timeout=10)
        else:
            response = requests.request(method, url, json=params, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == expected_status:
            print("✓ PASSED")
            try:
                data = response.json()
                print(f"Response keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
                # Print a sample of the response
                if isinstance(data, dict) and len(data) > 0:
                    sample_key = list(data.keys())[0]
                    print(f"Sample data ({sample_key}): {str(data[sample_key])[:100]}...")
            except:
                print(f"Response: {response.text[:200]}...")
        else:
            print("✗ FAILED")
            print(f"Expected: {expected_status}, Got: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ ERROR: {e}")
        return False
    
    return True


def main():
    """Run all API tests."""
    print(f"\n{'='*60}")
    print("Medical Telegram Warehouse API Test Suite")
    print(f"Base URL: {BASE_URL}")
    print(f"{'='*60}\n")
    
    results = []
    
    # Test 1: Health Check
    results.append((
        "Health Check",
        test_endpoint(
            "Health Check",
            "GET",
            f"{BASE_URL}/health"
        )
    ))
    
    # Test 2: Root Endpoint
    results.append((
        "Root Endpoint",
        test_endpoint(
            "Root Endpoint",
            "GET",
            f"{BASE_URL}/"
        )
    ))
    
    # Test 3: Top Products
    results.append((
        "Top Products",
        test_endpoint(
            "Top Products (limit=10)",
            "GET",
            f"{BASE_URL}/api/reports/top-products",
            params={"limit": 10}
        )
    ))
    
    # Test 4: Channel Activity (use first available channel)
    # First, try to get a channel name from top products or use a known one
    known_channels = ["CheMed", "Lobelia pharmacy and cosmetics", "Tikvah | Pharma"]
    test_channel = known_channels[0]
    results.append((
        "Channel Activity",
        test_endpoint(
            f"Channel Activity ({test_channel})",
            "GET",
            f"{BASE_URL}/api/channels/{test_channel}/activity",
            params={"days": 30}
        )
    ))
    
    # Test 5: Message Search
    results.append((
        "Message Search",
        test_endpoint(
            "Message Search (query='paracetamol')",
            "GET",
            f"{BASE_URL}/api/search/messages",
            params={"query": "paracetamol", "limit": 10}
        )
    ))
    
    # Test 6: Visual Content Stats
    results.append((
        "Visual Content Stats",
        test_endpoint(
            "Visual Content Statistics",
            "GET",
            f"{BASE_URL}/api/reports/visual-content"
        )
    ))
    
    # Summary
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
