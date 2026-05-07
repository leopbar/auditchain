import requests
import json
import time

BASE_URL = "http://localhost:8000"

def run_integration_tests():
    """Performs a sequence of integration tests to validate the authentication system."""
    session = requests.Session()
    
    print("--- AuditChain Authentication Integration Test ---\n")

    # 1. Access without auth
    print("1. GET /api/companies/ (No Auth)")
    try:
        r = session.get(f"{BASE_URL}/api/companies/")
        print(f"Status: {r.status_code}")
        print(f"Body: {r.json() if r.status_code != 500 else r.text}")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 50)

    # 2. Login
    print("2. POST /auth/login (admin@auditchain.com)")
    login_data = {"email": "admin@auditchain.com", "password": "AuditChainSecure2026!"}
    try:
        r = session.post(f"{BASE_URL}/auth/login", json=login_data)
        print(f"Status: {r.status_code}")
        print(f"Cookies Captured: {list(session.cookies.get_dict().keys())}")
        if r.status_code == 200:
            print(f"User Data: {r.json()['full_name']} ({r.json()['role']})")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 50)

    if r.status_code != 200:
        print("CRITICAL: Login failed. Aborting further tests.")
        return

    # 3. Access with auth
    print("3. GET /api/companies/ (With Auth)")
    try:
        r = session.get(f"{BASE_URL}/api/companies/")
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Companies Found: {data.get('total', 0)}")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 50)

    # 4. Check /me
    print("4. GET /auth/me")
    try:
        r = session.get(f"{BASE_URL}/auth/me")
        print(f"Status: {r.status_code}")
        print(f"Identity: {r.json().get('email')}")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 50)

    # 5. Admin access
    print("5. GET /api/admin/users")
    try:
        r = session.get(f"{BASE_URL}/api/admin/users")
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            print(f"Total Users: {len(r.json())}")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 50)

    # 6. Logout
    print("6. POST /auth/logout")
    try:
        r = session.post(f"{BASE_URL}/auth/logout")
        print(f"Status: {r.status_code}")
        print(f"Body: {r.json()}")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 50)

    # 7. Post-logout access
    print("7. GET /api/companies/ (After Logout)")
    try:
        r = session.get(f"{BASE_URL}/api/companies/")
        print(f"Status: {r.status_code}")
        print(f"Body: {r.json()}")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 50)

if __name__ == "__main__":
    # Wait a moment for server to be ready
    time.sleep(2)
    run_integration_tests()
