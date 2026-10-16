import os
import pytest


def test_auth_registration_and_login(client):
    """Verify secure registration and subsequent JWT token authentication."""
    reg_res = client.post("/api/auth/register", json={
        "username": "new_analyst",
        "password": "StrongPassword123!",
        "full_name": "New Analyst",
        "email": "analyst@mospi.gov.in"
    })
    assert reg_res.status_code == 201, reg_res.text
    data = reg_res.json()
    assert data["username"] == "new_analyst"
    assert "access_token" in data
    assert data["role"] == "viewer"

    # Login with valid credentials
    login_res = client.post("/api/auth/login", json={
        "username": "new_analyst",
        "password": "StrongPassword123!"
    })
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()

    # Login with incorrect password should fail
    bad_login = client.post("/api/auth/login", json={
        "username": "new_analyst",
        "password": "WrongPassword!"
    })
    assert bad_login.status_code == 401


def test_rbac_admin_boundaries(client, viewer_token, admin_token):
    """Verify that viewers cannot perform admin-only mutations."""
    # Viewer attempting to update department skill weight should be rejected (403)
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    fail_res = client.post("/api/succession/department-weights", json={
        "weight_id": 1,
        "multiplier": 2.2,
        "rationale": "Unauthorized attempt"
    }, headers=viewer_headers)
    assert fail_res.status_code == 403, f"Expected 403, got {fail_res.status_code}"

    # Admin attempting the same operation should succeed (200)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    success_res = client.post("/api/succession/department-weights", json={
        "weight_id": 1,
        "multiplier": 2.2,
        "rationale": "Authorized policy adjustment"
    }, headers=admin_headers)
    assert success_res.status_code == 200, success_res.text
    assert success_res.json()["multiplier"] == 2.2


def test_role_elevation_with_master_key(client, viewer_token):
    """Verify viewer elevation to administrator via verified master passkey."""
    headers = {"Authorization": f"Bearer {viewer_token}"}

    # Invalid password attempt
    bad_elevate = client.post("/api/auth/elevate", json={
        "admin_password": "WrongMasterPassword"
    }, headers=headers)
    assert bad_elevate.status_code == 403

    # Valid master passkey elevation
    admin_pwd = os.getenv("ADMIN_PASSWORD", "ChangeMe-Now-123!")
    good_elevate = client.post("/api/auth/elevate", json={
        "admin_password": admin_pwd
    }, headers=headers)
    assert good_elevate.status_code == 200
    data = good_elevate.json()
    assert data["role"] == "admin"
    assert "access_token" in data


def test_officer_cockpit_my_pathway(client, officer_user):
    """Verify that an officer can access their personalized self-service pathway cockpit."""
    headers = {"Authorization": f"Bearer {officer_user['token']}"}
    res = client.get("/api/pathway/my-pathway", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "officer" in data
    if data["officer"]:
        assert data["officer"]["name"] == "Priya Sharma"
