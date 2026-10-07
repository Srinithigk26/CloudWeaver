import os
import uuid
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def test_auth_cost_history_and_google():
    session = requests.Session()
    email = f"TEST_{uuid.uuid4().hex[:10]}@example.com"
    register = session.post(f"{BASE_URL}/api/auth/register", json={
        "name": "TEST Cloud User", "email": email, "password": "TestPass!2026", "region": "India"
    })
    assert register.status_code == 200, register.text
    assert register.json()["email"] == email.lower()
    assert session.cookies.get("access_token")

    me = session.get(f"{BASE_URL}/api/auth/me")
    assert me.status_code == 200 and me.json()["email"] == email.lower()

    workload = {"name": "TEST API", "vcpu": 8, "ram": 32, "storage": 500, "hours": 720, "region": "India"}
    analysis = session.post(f"{BASE_URL}/api/cost/analyze", json=workload)
    assert analysis.status_code == 200, analysis.text
    data = analysis.json()
    assert data["recommended"] == "Azure"
    assert next(x["monthly"] for x in data["providers"] if x["provider"] == "Azure") == 20582.8
    assert data["monthly_savings"] == 1477.2
    assert data["annual_savings"] == 17726.4

    history = session.get(f"{BASE_URL}/api/workloads")
    assert history.status_code == 200
    assert any(x["workload"]["name"] == "TEST API" for x in history.json())

    google = session.post(f"{BASE_URL}/api/auth/google")
    assert google.status_code == 501

    logout = session.post(f"{BASE_URL}/api/auth/logout")
    assert logout.status_code == 200
    assert session.get(f"{BASE_URL}/api/auth/me").status_code == 401


def test_admin_login_and_unauthorized_guard():
    session = requests.Session()
    login = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@cloudweaver.app", "password": "CloudWeaver!2026"
    })
    assert login.status_code == 200, login.text
    assert login.json()["role"] == "admin"
    assert session.cookies.get("access_token")
    assert requests.post(f"{BASE_URL}/api/cost/analyze", json={}).status_code == 401