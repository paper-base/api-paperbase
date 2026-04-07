"""Obtain dashboard JWT via the real token endpoint (includes active_store_public_id)."""

from __future__ import annotations

from rest_framework.test import APIClient


def login_dashboard_jwt(
    client: APIClient,
    email: str,
    password: str = "pass1234",
) -> dict:
    resp = client.post(
        "/api/v1/auth/token/",
        {"email": email, "password": password},
        format="json",
    )
    assert resp.status_code == 200, getattr(resp, "data", None)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
    return resp.data
