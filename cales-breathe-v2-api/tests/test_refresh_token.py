"""Access + refresh cookie 流程與輪替。"""

import pytest
import jwt

from app import auth_session


def test_login_sets_two_cookies(client):
    r = client.post(
        "/register",
        json={
            "client_name": "RT User",
            "contact_mail": "rt_user@example.com",
            "password": "secret123",
        },
    )
    assert r.status_code == 200
    cookies = r.cookies
    assert auth_session.access_cookie_name() in cookies
    assert auth_session.refresh_cookie_name() in cookies


def test_refresh_rotates_and_old_cookie_invalid(client, monkeypatch):
    monkeypatch.setenv("ACCESS_TOKEN_TTL_MINUTES", "1")
    monkeypatch.setenv("REFRESH_TOKEN_TTL_DAYS", "7")
    r0 = client.post(
        "/register",
        json={
            "client_name": "Rot",
            "contact_mail": "rot@example.com",
            "password": "pw123456",
        },
    )
    assert r0.status_code == 200
    old_refresh = r0.cookies.get(auth_session.refresh_cookie_name())
    assert old_refresh

    r1 = client.post("/auth/refresh", cookies={auth_session.refresh_cookie_name(): old_refresh})
    assert r1.status_code == 200
    new_refresh = r1.cookies.get(auth_session.refresh_cookie_name())
    assert new_refresh and new_refresh != old_refresh

    r_bad = client.post("/auth/refresh", cookies={auth_session.refresh_cookie_name(): old_refresh})
    assert r_bad.status_code == 401

    r2 = client.post("/auth/refresh", cookies={auth_session.refresh_cookie_name(): new_refresh})
    assert r2.status_code == 200


def test_logout_revokes_refresh(client):
    r = client.post(
        "/register",
        json={
            "client_name": "Out",
            "contact_mail": "out@example.com",
            "password": "pw123456",
        },
    )
    jar = r.cookies
    lo = client.post("/auth/logout", cookies=jar)
    assert lo.status_code == 200
    ref = jar.get(auth_session.refresh_cookie_name())
    rr = client.post("/auth/refresh", cookies={auth_session.refresh_cookie_name(): ref})
    assert rr.status_code == 401


def test_access_jwt_requires_purpose_claim(client):
    r = client.post(
        "/register",
        json={
            "client_name": "Leg",
            "contact_mail": "leg@example.com",
            "password": "pw123456",
        },
    )
    uid = r.json()["user"]["id"]
    bad = jwt.encode(
        {"sub": str(uid), "iat": 1, "exp": 9999999999},
        "pytest-jwt-secret-key-for-testing!!",
        algorithm="HS256",
    )
    me = client.get("/me", cookies={auth_session.access_cookie_name(): bad})
    assert me.status_code == 401
