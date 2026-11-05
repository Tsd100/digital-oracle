# DO Signal Matrix and NAS Docker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cross-subject signal matrix dashboard and a persistent Docker Compose runtime suitable for later fnOS deployment.

**Architecture:** Extend the existing management read model with event history, render the dashboard with accessible HTML/CSS matrix components and a lazy report drawer, then externalize storage paths and run the Flask app behind Gunicorn. Keep the existing SQLite schema and report APIs to avoid a data migration.

**Tech Stack:** Python 3.11, Flask, SQLite, vanilla JavaScript/CSS, Gunicorn, Docker Compose, pytest, Playwright.

---

### Task 1: Management history contract

**Files:** `tests/test_timeline_web.py`, `web/management.py`, `web/templates/index.html`

- [ ] Add failing assertions for per-subject history records and matrix/drawer landmarks.
- [ ] Run the focused test and confirm the missing contract fails.
- [ ] Add bounded history records to the management summary and the new HTML landmarks.
- [ ] Run focused tests until green.

### Task 2: Signal matrices and report drawer

**Files:** `web/static/js/management.js`, `web/static/css/management.css`, `tests/test_management_visual.mjs`

- [ ] Update browser checks to require the three-horizon matrix, history matrix, direction cells, and drawer interaction.
- [ ] Render both matrices, preserve isolated gaps, and add a lazy report drawer.
- [ ] Add responsive matrix scrolling without page overflow.
- [ ] Run desktop/mobile browser checks.

### Task 3: Container-safe configuration

**Files:** `tests/test_docker_assets.py`, `digital_oracle/timeline/store.py`, `web/db.py`, `web/app.py`, `web/wsgi.py`

- [ ] Add failing tests for environment-controlled storage and `/healthz`.
- [ ] Externalize database/report/archive paths and add database health checks.
- [ ] Expose a WSGI application for Gunicorn.
- [ ] Run focused Python tests.

### Task 4: Offline web assets and Compose package

**Files:** `web/templates/ask.html`, `web/static/js/markdown-lite.js`, `Dockerfile`, `compose.yaml`, `.dockerignore`, `requirements-web.txt`, `tests/test_docker_assets.py`

- [ ] Add failing assertions that no CDN is referenced and all Docker assets exist with persistence, healthcheck, non-root user, and restart policy.
- [ ] Add a safe local Markdown subset renderer and remove the CDN dependency.
- [ ] Add pinned web dependencies, Dockerfile, Compose, and build exclusions.
- [ ] Run static Docker contract tests and `docker compose config`.

### Task 5: Full verification and handoff

**Files:** `tests/test_management_visual.mjs`, `tests/test_timeline_visual.mjs`

- [ ] Run the complete Python suite and JavaScript syntax checks.
- [ ] Run desktop/mobile browser checks and inspect screenshots.
- [ ] Attempt a local Docker build; if the engine is unavailable, report that exact limitation and retain the verified Compose package.
- [ ] Stage only this feature, scan for secrets/runtime data, commit, and push.
