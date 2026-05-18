# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Tripack + FastAPI integration example.

A minimal web service that demonstrates the canonical FastAPI
+ Tripack wiring shape:

- ``lifespan`` builds the :class:`Container` once at startup
  and tears it down on shutdown;
- a per-request middleware opens a ``Scope`` so SCOPED
  bindings (here, ``RequestId``) cache per request;
- a generic ``from_container(token)`` factory adapts the
  container to FastAPI's ``Depends`` so route handlers
  receive their dependencies through the normal ``Depends``
  machinery.

Routes:

- ``GET  /now``        - returns a SINGLETON :class:`Clock` reading.
- ``GET  /request-id`` - returns the SCOPED request id.
- ``POST /events``     - appends an entry to the SINGLETON event log.
- ``GET  /events``     - returns the full event log.
"""
