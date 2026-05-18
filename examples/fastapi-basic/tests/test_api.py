# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""End-to-end tests for the FastAPI + Tripack integration example."""

from __future__ import annotations

from fastapi.testclient import TestClient
from fastapi_basic.api import create_app


def test_now_endpoint_returns_a_clock_reading() -> None:
    """The ``/now`` route resolves the SINGLETON Clock and returns its reading."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/now")
    assert response.status_code == 200
    body = response.json()
    assert "now" in body
    assert isinstance(body["now"], float)


def test_request_id_endpoint_returns_per_request_value() -> None:
    """SCOPED RequestId differs across two HTTP requests on the same app."""
    app = create_app()
    with TestClient(app) as client:
        first = client.get("/request-id").json()["request_id"]
        second = client.get("/request-id").json()["request_id"]
    assert first != second  # SCOPED: per-request scope -> distinct ids


def test_event_log_accumulates_entries_across_requests() -> None:
    """SINGLETON EventLog persists entries across multiple HTTP requests."""
    app = create_app()
    with TestClient(app) as client:
        first = client.post("/events", params={"message": "hello"}).json()
        second = client.post("/events", params={"message": "world"}).json()
        listing = client.get("/events").json()
    assert first["count"] == 1
    assert second["count"] == 2
    assert first["request_id"] != second["request_id"]
    events = listing["events"]
    assert [e["message"] for e in events] == ["hello", "world"]


def test_fresh_app_has_empty_event_log() -> None:
    """Each ``create_app`` builds its own container - state is per-instance."""
    app_a = create_app()
    app_b = create_app()
    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
        client_a.post("/events", params={"message": "only-on-a"})
        b_events = client_b.get("/events").json()["events"]
    assert b_events == []
