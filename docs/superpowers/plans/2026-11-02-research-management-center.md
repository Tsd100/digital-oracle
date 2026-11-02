# DO Research Management Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace the root question console with a research management center while preserving the existing console at `/ask` and aggregating timeline state through one API.

**Architecture:** Add a focused server-side summary builder over `TimelineStore` and chat history, expose it at `/api/management/summary`, and render a new management template with dedicated CSS and JavaScript. Keep timeline storage and chat storage unchanged, so the change is reversible and does not migrate user data.

**Tech Stack:** Python 3, Flask, SQLite, vanilla JavaScript, CSS, pytest, Playwright.

---

### Task 1: Route and API contracts

**Files:**
- Modify: `tests/test_timeline_web.py`
- Modify: `web/app.py`
- Create: `web/management.py`

- [x] Write failing tests asserting `/` contains management landmarks, `/ask` contains the original question form, and `/api/management/summary` returns subject summaries and health data.
- [x] Run `python -m pytest tests/test_timeline_web.py -q` and confirm the new assertions fail because the routes and endpoint do not exist.
- [x] Implement a pure `build_management_summary()` function and add the `/ask` and summary routes.
- [x] Run the focused test file and confirm it passes.

### Task 2: Management interface

**Files:**
- Modify: `web/templates/index.html`
- Create: `web/templates/ask.html`
- Create: `web/static/css/management.css`
- Create: `web/static/js/management.js`
- Modify: `web/static/js/app.js`

- [x] Add failing HTML landmark assertions for the overview, subject grid, change feed, health panel, and navigation.
- [x] Move the existing question console markup to `ask.html` and replace `index.html` with the management shell.
- [x] Render subject cards, structured horizon chips, recent changes, system health, and data quality from the summary API.
- [x] Add responsive styles and persistent light/dark theme behavior.
- [x] Add a management navigation link to the question console.

### Task 3: Browser verification and regression

**Files:**
- Create: `tests/test_management_visual.mjs`

- [x] Add Playwright checks for desktop and mobile layouts, API rendering, navigation targets, theme switching, horizontal overflow, and console errors.
- [x] Run `node tests/test_management_visual.mjs` against port 5001.
- [x] Run `python -m pytest -q` and `node --check` for both JavaScript entry points.
- [x] Inspect a full-page screenshot of the management center and correct any visual hierarchy problems.
- [x] Commit only the management-center files after checking the staged diff for credentials and unrelated runtime data.
