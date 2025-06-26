import requests
import json

API_BASE = "http://localhost:8009"

def test_endpoint(path):
    try:
        url = f"{API_BASE}{path}"
        print(f"Testing: {url}")
        response = requests.get(url, timeout=5)
        print(f"Status: {response.status_code}")
        if response.headers.get('content-type', '').startswith('application/json'):
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        else:
            print(f"Response: {response.text}")
        print("-" * 50)
        return True
    except Exception as e:
        print(f"Error: {e}")
        print("-" * 50)
        return False

if __name__ == "__main__":
    endpoints = ["/health", "/status", "/redis-test"]
    for endpoint in endpoints:
        test_endpoint(endpoint)
