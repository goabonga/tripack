# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""End-to-end tests for the FastAPI + Tripack integration example.

Each test builds a fresh :class:`TripackAPI` so the in-memory
:class:`EventLog` does not bleed between tests. The
``container_factory`` reuses the same ``build_container`` the
production code uses (loading :file:`container.json`) so the
test exercises the real wiring path end-to-end.
"""

from __future__ import annotations

# Re-importing ``api`` for its route registrations would build the
# module-level ``app`` against the production container; constructing
# a fresh app per test gives each one a clean container.
import fastapi_basic.api  # noqa: F401  - imported for route registration side effects
from fastapi.testclient import TestClient
from fastapi_basic.api import build_container

from tripack_container.fastapi import TripackAPI


def _fresh_app() -> TripackAPI:
    """Spin up a brand-new app + container for one test.

    Importing ``fastapi_basic.api`` at the top of this module
    triggers the route decorators on the module-level ``app``;
    here we rebuild the same routes on a fresh :class:`TripackAPI`
    by piggy-backing on FastAPI's route registry copy mechanism:
    add the existing routes to a new app's router.
    """
    new_app = TripackAPI(container_factory=build_container)
    new_app.router.routes.extend(fastapi_basic.api.app.router.routes[4:])
    # ``routes[:4]`` are FastAPI's built-in OpenAPI / docs routes
    # added at construction; copying past index 4 grabs only the
    # user-defined endpoints.
    return new_app


def test_now_endpoint_returns_a_clock_reading() -> None:
    """``/now`` resolves the SINGLETON ``Clock`` and returns its reading."""
    app = _fresh_app()
    with TestClient(app) as client:
        response = client.get("/now")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["now"], float)


def test_request_id_endpoint_returns_per_request_value() -> None:
    """SCOPED ``RequestId`` differs across two HTTP requests."""
    app = _fresh_app()
    with TestClient(app) as client:
        first = client.get("/request-id").json()["request_id"]
        second = client.get("/request-id").json()["request_id"]
    assert first != second


def test_event_log_accumulates_entries_across_requests() -> None:
    """SINGLETON ``EventLog`` persists entries across requests."""
    app = _fresh_app()
    with TestClient(app) as client:
        first = client.post("/events", params={"message": "hello"}).json()
        second = client.post("/events", params={"message": "world"}).json()
        listing = client.get("/events").json()
    assert first["count"] == 1
    assert second["count"] == 2
    assert first["request_id"] != second["request_id"]
    events = listing["events"]
    assert [e["message"] for e in events] == ["hello", "world"]


def test_two_apps_have_isolated_event_logs() -> None:
    """Each ``TripackAPI`` builds its own container - state is per-instance."""
    app_a = _fresh_app()
    app_b = _fresh_app()
    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
        client_a.post("/events", params={"message": "only-on-a"})
        b_events = client_b.get("/events").json()["events"]
    assert b_events == []


def test_audit_chains_interface_to_interface() -> None:
    """``AuditTrail`` is bound under its Protocol; itself depends on Clock + EventLog.

    The handler asks for ``AuditTrail`` and ``EventLog`` only;
    the ``DefaultAuditTrail`` constructor auto-injects the
    ``Clock`` + ``EventLog`` interfaces from the container. The
    handler then sees the audit entry land in the same log.
    """
    app = _fresh_app()
    with TestClient(app) as client:
        response = client.post("/audit/login")
        listing = client.get("/events").json()["events"]
    assert response.json()["audited"] == "login"
    assert response.json()["entries"] == 1
    assert listing[0]["message"].startswith("audit:login")


def test_notify_optional_returns_false_when_unbound() -> None:
    """``Notifier`` has no binding in ``container.json``; ``T | None`` returns None."""
    app = _fresh_app()
    with TestClient(app) as client:
        response = client.get("/notify/hello").json()
    assert response == {"delivered": False, "message": "hello"}
