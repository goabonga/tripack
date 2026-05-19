# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Tripack + FastAPI integration example.

Demonstrates the recommended FastAPI + Tripack wiring shape:

- :class:`TripackAPI` (from ``tripack_container.fastapi``)
  owns the container lifecycle and rewrites
  ``Annotated[T, Inject]`` parameters to FastAPI ``Depends``;
- the container is built declaratively from
  :file:`container.json` via :func:`load_json` - no Python
  wiring code;
- handlers reference interfaces only
  (:mod:`fastapi_basic.contracts`), never the concrete
  implementations in :mod:`fastapi_basic.services`.

Routes:

- ``GET  /now``            - SINGLETON :class:`Clock` injection.
- ``GET  /request-id``     - SCOPED :class:`RequestId` per request.
- ``POST /events``         - mixed SINGLETON + SCOPED + SINGLETON injection.
- ``GET  /events``         - SINGLETON :class:`EventLog` shared across requests.
- ``POST /audit/{action}`` - chained-interface injection through
  :class:`AuditTrail` with ``auto_inject``.
- ``GET  /notify/{msg}``   - optional ``T | None`` injection of
  :class:`Notifier`, which has no binding by default.
"""
