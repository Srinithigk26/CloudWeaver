import os
import uuid
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

WORKLOAD = {"name": "TEST WL", "vcpu": 4, "ram": 16, "storage": 200, "hours": 720, "region": "India"}


@pytest.fixture
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@cloudweaver.app", "password": "CloudWeaver!2026"
    })
    assert r.status_code == 200, r.text
    return s


@pytest.fixture
def user_b_session():
    s = requests.Session()
    email = f"TEST_{uuid.uuid4().hex[:10]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/register", json={
        "name": "TEST User B", "email": email, "password": "TestPass!2026", "region": "India"
    })
    assert r.status_code == 200, r.text
    return s


def _create_workload(session, name):
    payload = {**WORKLOAD, "name": name}
    r = session.post(f"{BASE_URL}/api/cost/analyze", json=payload)
    assert r.status_code == 200, r.text
    # fetch latest workload id
    hist = session.get(f"{BASE_URL}/api/workloads").json()
    for item in hist:
        if item["workload"]["name"] == name:
            return item["id"]
    raise AssertionError("Workload not found in history after create")


def test_patch_workload_renames(admin_session):
    wid = _create_workload(admin_session, f"TEST A {uuid.uuid4().hex[:6]}")
    r = admin_session.patch(f"{BASE_URL}/api/workloads/{wid}", json={"name": "Renamed API"})
    assert r.status_code == 200, r.text
    body = r.json()
    # Returned workload should reflect the new name
    assert body.get("workload", {}).get("name") == "Renamed API" or body.get("name") == "Renamed API", body
    # GET must reflect
    hist = admin_session.get(f"{BASE_URL}/api/workloads").json()
    names = [x["workload"]["name"] for x in hist]
    assert "Renamed API" in names


def test_delete_workload_removes(admin_session):
    wid = _create_workload(admin_session, f"TEST D {uuid.uuid4().hex[:6]}")
    r = admin_session.delete(f"{BASE_URL}/api/workloads/{wid}")
    assert r.status_code == 200, r.text
    hist = admin_session.get(f"{BASE_URL}/api/workloads").json()
    assert all(x["id"] != wid for x in hist)


def test_patch_bogus_id_returns_404(admin_session):
    # a valid-looking ObjectId that doesn't exist
    r = admin_session.patch(f"{BASE_URL}/api/workloads/507f1f77bcf86cd799439011", json={"name": "ValidName"})
    assert r.status_code == 404, r.text


def test_delete_bogus_id_returns_404(admin_session):
    r = admin_session.delete(f"{BASE_URL}/api/workloads/507f1f77bcf86cd799439011")
    assert r.status_code == 404, r.text


def test_patch_requires_auth():
    r = requests.patch(f"{BASE_URL}/api/workloads/507f1f77bcf86cd799439011", json={"name": "x"})
    assert r.status_code == 401


def test_delete_requires_auth():
    r = requests.delete(f"{BASE_URL}/api/workloads/507f1f77bcf86cd799439011")
    assert r.status_code == 401


def test_cross_user_cannot_modify(admin_session, user_b_session):
    wid = _create_workload(admin_session, f"TEST X {uuid.uuid4().hex[:6]}")
    # user B tries to rename
    r = user_b_session.patch(f"{BASE_URL}/api/workloads/{wid}", json={"name": "Hacked"})
    assert r.status_code == 404, r.text
    # user B tries to delete
    r = user_b_session.delete(f"{BASE_URL}/api/workloads/{wid}")
    assert r.status_code == 404, r.text
    # Admin's workload still exists
    hist = admin_session.get(f"{BASE_URL}/api/workloads").json()
    assert any(x["id"] == wid for x in hist)
    # Cleanup
    admin_session.delete(f"{BASE_URL}/api/workloads/{wid}")


def test_patch_name_validation(admin_session):
    wid = _create_workload(admin_session, f"TEST V {uuid.uuid4().hex[:6]}")
    # too short
    r = admin_session.patch(f"{BASE_URL}/api/workloads/{wid}", json={"name": "a"})
    assert r.status_code in (400, 422), r.text
    # too long
    r = admin_session.patch(f"{BASE_URL}/api/workloads/{wid}", json={"name": "x" * 200})
    assert r.status_code in (400, 422), r.text
    admin_session.delete(f"{BASE_URL}/api/workloads/{wid}")
