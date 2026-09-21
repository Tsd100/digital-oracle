# DO Automatic Trend Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every future DO report publish a validated three-horizon trend snapshot, deterministic change summary, and updated visual timeline through one idempotent pipeline.

**Architecture:** Add a versioned JSON contract parser, a rule-only trend engine, and a transactional publisher on top of the existing SQLite timeline store. Codex, CLI, and Web call the same publisher; the timeline API returns current state and events for a three-track browser view while legacy reports remain readable.

**Tech Stack:** Python 3, dataclasses, SQLite, Flask, vanilla JavaScript/SVG, pytest, Playwright.

---

## File map

- Create `digital_oracle/timeline/contract.py`: extract and validate the `do-trend` JSON block.
- Create `digital_oracle/timeline/trends.py`: deterministic direction, confidence, streak, probability, and level comparisons.
- Create `digital_oracle/timeline/publish.py`: idempotent transactional publication and Chinese summary rendering.
- Modify `digital_oracle/timeline/store.py`: schema migration, structured snapshot/event queries, and automation health data.
- Modify `digital_oracle/timeline/__init__.py`: export the public publish interface.
- Modify `digital_oracle/timeline/cli.py`: add `publish` and structured trend display commands.
- Modify `web/app.py`: publish Web reports through the shared service and expose trend payloads.
- Modify `web/templates/timeline.html`: current-state cards, track controls, event stream, and automation state.
- Modify `web/static/js/timeline.js`: render structured trend data while retaining legacy-report access.
- Modify `web/static/css/timeline.css`: style the three tracks and status components.
- Modify `SKILL.md`: require a structured block and final publish command for future Codex reports.
- Create `tests/test_timeline_contract.py`, `tests/test_timeline_trends.py`, and `tests/test_timeline_publish.py`.
- Modify `tests/test_timeline_web.py` and `tests/test_timeline_visual.mjs` for API and browser coverage.

### Task 1: Versioned trend contract

**Files:**
- Create: `digital_oracle/timeline/contract.py`
- Create: `tests/test_timeline_contract.py`

- [ ] **Step 1: Write contract extraction and validation tests**

Cover a complete gold report, a missing horizon, an invalid direction, confidence outside 0–100, malformed JSON, and absent `do-trend` block. The complete fixture must assert normalized `subject_id`, instrument, unit, and all three horizon records.

```python
def test_extracts_versioned_trend_block():
    report = '''# 黄金分析
```do-trend
{"schema_version":"1.0","analysis_id":"gold-1","analysis_at":"2026-09-21T14:30:00+08:00","data_as_of":"2026-09-21T14:00:00+08:00","subjects":[{"subject_id":"gold","subject_name":"黄金","instrument":"XAUUSD","quote_currency":"USD","quote_unit":"oz","horizons":{"short":{"direction":"bearish","confidence":72,"summary":"短线承压"}}}]}
```
'''
    data = extract_trend_block(report)
    assert data.subjects[0].horizons["short"].direction == "bearish"
```

- [ ] **Step 2: Run the tests and verify failure**

Run: `python -m pytest tests/test_timeline_contract.py -q`

Expected: collection fails because `digital_oracle.timeline.contract` does not exist.

- [ ] **Step 3: Implement immutable contract types and validation**

Define `ContractError`, `TrendContract`, `SubjectSnapshot`, `HorizonSnapshot`, `ScenarioProbability`, and `PriceLevel`. Parse exactly one fenced `do-trend` JSON block, accept schema `1.0`, require identity/time/subject fields, validate enums and numeric ranges, and preserve omitted horizons as absent rather than neutral.

- [ ] **Step 4: Run contract tests**

Run: `python -m pytest tests/test_timeline_contract.py -q`

Expected: all contract tests pass.

- [ ] **Step 5: Commit**

```text
git add digital_oracle/timeline/contract.py tests/test_timeline_contract.py
git commit -m "feat: validate structured DO trend reports"
```

### Task 2: Deterministic trend engine

**Files:**
- Create: `digital_oracle/timeline/trends.py`
- Create: `tests/test_timeline_trends.py`

- [ ] **Step 1: Write table-driven direction tests**

Assert `neutral→bullish=shifted`, `bullish→strong_bullish=strengthened`, `strong_bullish→bullish=weakened`, `bullish→bearish=reversed`, equal directions `continued`, and no prior snapshot `initiated`.

```python
@pytest.mark.parametrize(("old", "new", "event"), [
    ("neutral", "bullish", "shifted"),
    ("bullish", "strong_bullish", "strengthened"),
    ("strong_bullish", "bullish", "weakened"),
    ("bullish", "bearish", "reversed"),
])
def test_direction_events(old, new, event):
    assert compare_direction(old, new) == event
```

- [ ] **Step 2: Write confidence, scenario, level, and streak tests**

Verify the 5 and 15 point confidence boundaries, probability comparison only for identical scenario identity and term, unit-sensitive level comparison, missing-horizon behavior, streak increments, and reversal reset.

- [ ] **Step 3: Run tests and verify failure**

Run: `python -m pytest tests/test_timeline_trends.py -q`

Expected: collection fails because `digital_oracle.timeline.trends` does not exist.

- [ ] **Step 4: Implement pure comparison functions**

Use `DIRECTION_SCORE`, `compare_direction`, `compare_confidence`, `compare_probabilities`, `compare_levels`, and `build_event`. Keep the module free of SQLite and report-text parsing so every rule is independently testable.

- [ ] **Step 5: Run trend tests and commit**

Run: `python -m pytest tests/test_timeline_trends.py -q`

Expected: all trend-engine tests pass.

```text
git add digital_oracle/timeline/trends.py tests/test_timeline_trends.py
git commit -m "feat: add deterministic DO trend engine"
```

### Task 3: Transactional and idempotent publisher

**Files:**
- Create: `digital_oracle/timeline/publish.py`
- Modify: `digital_oracle/timeline/store.py`
- Modify: `digital_oracle/timeline/__init__.py`
- Create: `tests/test_timeline_publish.py`

- [ ] **Step 1: Write publication tests**

Test first publication, duplicate publication, a changed report on the same day, three independent horizon events, missing horizon, second publication updating streak state, invalid contract, and rollback after an injected write failure.

```python
def test_duplicate_publish_is_idempotent(tmp_path, structured_report):
    store = TimelineStore(tmp_path / "timeline.db")
    first = publish_report(store, "codex:gold-1", structured_report, "codex")
    second = publish_report(store, "codex:gold-1", structured_report, "codex")
    assert first.publication_id == second.publication_id
    assert second.duplicate is True
    assert store.automation_health()["publications"] == 1
```

- [ ] **Step 2: Run publisher tests and verify failure**

Run: `python -m pytest tests/test_timeline_publish.py -q`

Expected: failure because the publisher and new schema do not exist.

- [ ] **Step 3: Add backward-compatible SQLite tables**

Extend `SCHEMA` with `publications`, `trend_snapshots`, `trend_events`, and `trend_state`. Use `CREATE TABLE IF NOT EXISTS`, foreign keys, unique publication fingerprints, and indexes for `(subject_id, horizon, analysis_at)` without changing legacy `reports` rows.

- [ ] **Step 4: Implement one-transaction publication**

Parse before opening the transaction; inside one connection, insert the legacy report/source, publication, snapshots, events, and state. Return `PublishResult` with `publication_id`, `duplicate`, `updated_tracks`, `errors`, `events`, and `summary`. On any database exception, roll back all new structured rows.

- [ ] **Step 5: Implement fixed Chinese summary templates**

Render one line per updated horizon plus confidence, probability, price-level, streak, and divergence messages. Do not call an LLM or infer facts from prose.

- [ ] **Step 6: Run focused and legacy tests**

Run: `python -m pytest tests/test_timeline_publish.py tests/test_timeline.py -q`

Expected: all tests pass and legacy report import remains compatible.

- [ ] **Step 7: Commit**

```text
git add digital_oracle/timeline/store.py digital_oracle/timeline/publish.py digital_oracle/timeline/__init__.py tests/test_timeline_publish.py
git commit -m "feat: publish DO trend snapshots transactionally"
```

### Task 4: CLI, Web, and Codex entry points

**Files:**
- Modify: `digital_oracle/timeline/cli.py`
- Modify: `web/app.py`
- Modify: `SKILL.md`
- Modify: `tests/test_timeline_web.py`
- Create: `tests/test_timeline_cli.py`

- [ ] **Step 1: Write CLI and Web integration tests**

CLI test publishes a temporary Markdown file twice and checks the second JSON result reports `duplicate: true`. Web workflow test stubs report generation with a structured report and asserts the shared publisher is called and its summary is included in the `done` event.

- [ ] **Step 2: Run integration tests and verify failure**

Run: `python -m pytest tests/test_timeline_cli.py tests/test_timeline_web.py -q`

Expected: new publish command and Web result fields are absent.

- [ ] **Step 3: Add CLI `publish` command**

Accept `report`, `--source-key`, `--source-kind`, and `--db`; read UTF-8 Markdown, call `publish_report`, and print a JSON object suitable for both human inspection and automation.

- [ ] **Step 4: Replace direct Web `TimelineStore.add` call**

Call the shared publisher. Keep the readable report saved even if the trend block is invalid, and return `trend_publication` with status, summary, updated track count, and field-level errors in the completion event.

- [ ] **Step 5: Update the DO Skill contract**

Replace the optional import wording with a required future-report `do-trend` block and final `python -m digital_oracle.timeline.cli publish <report>` step. State that missing horizons are omitted and that the final response includes the returned change summary.

- [ ] **Step 6: Run tests and commit**

Run: `python -m pytest tests/test_timeline_cli.py tests/test_timeline_web.py -q`

Expected: all entry-point tests pass.

```text
git add digital_oracle/timeline/cli.py web/app.py SKILL.md tests/test_timeline_cli.py tests/test_timeline_web.py
git commit -m "feat: connect DO entry points to trend publishing"
```

### Task 5: Structured trend API and three-track UI

**Files:**
- Modify: `digital_oracle/timeline/store.py`
- Modify: `web/app.py`
- Modify: `web/templates/timeline.html`
- Modify: `web/static/js/timeline.js`
- Modify: `web/static/css/timeline.css`
- Modify: `tests/test_timeline_web.py`
- Modify: `tests/test_timeline_visual.mjs`

- [ ] **Step 1: Write API response tests**

Publish two structured gold reports and assert `/api/timeline?subject=黄金` returns `current_state`, ordered `trend_points`, `trend_events`, `automation_health`, and legacy `reports`. Verify absent horizons are not synthesized.

- [ ] **Step 2: Run API tests and verify failure**

Run: `python -m pytest tests/test_timeline_web.py -q`

Expected: structured fields are missing.

- [ ] **Step 3: Add focused store queries and API payload**

Add store methods for current state, trend points, events, and automation health. Return these fields from the existing timeline endpoint without removing legacy response keys.

- [ ] **Step 4: Build the first-screen state cards and track chart**

Render short, swing, and medium cards with direction, confidence, last event, streak, duration, reason, and data time. Draw three SVG tracks on the fixed -2 to +2 axis; allow each track to be toggled and each point to open its source report.

- [ ] **Step 5: Add event feed, divergence, probabilities, levels, and health**

Use the structured event payload. Display explicit “本次未分析” and field-level failures. Retain the legacy report list below the structured view.

- [ ] **Step 6: Extend browser checks**

Assert the page shows three horizon cards, a reversal marker, an automation status, and an interactive report dialog at desktop and narrow viewport sizes.

- [ ] **Step 7: Run Web and browser tests**

Run: `python -m pytest tests/test_timeline_web.py -q`

Run: `node tests/test_timeline_visual.mjs`

Expected: API and browser checks pass with no console errors.

- [ ] **Step 8: Commit**

```text
git add digital_oracle/timeline/store.py web/app.py web/templates/timeline.html web/static/js/timeline.js web/static/css/timeline.css tests/test_timeline_web.py tests/test_timeline_visual.mjs
git commit -m "feat: visualize three-horizon DO trends"
```

### Task 6: Full regression and live workflow verification

**Files:**
- Modify only files required to fix verified defects found by this task.

- [ ] **Step 1: Run the complete Python suite**

Run: `python -m pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run browser verification**

Start the Flask app without the debug reloader, open `/timeline?subject=黄金`, and run `node tests/test_timeline_visual.mjs`.

Expected: the three-track UI loads, has no browser console errors, and report nodes open the source dialog.

- [ ] **Step 3: Verify all three publication paths**

Publish a temporary structured report with the CLI, call the Web workflow test path, and execute the exact Codex command documented in `SKILL.md`. Repeat one publication and verify the database count remains unchanged.

- [ ] **Step 4: Inspect staged content**

Run: `git diff --check` and `git status --short`.

Expected: no whitespace errors; commits contain no database WAL files, secrets, tokens, local runtime reports, or unrelated pre-existing modifications.

- [ ] **Step 5: Commit any verified fixes**

```text
git add <only files changed for verified defects>
git commit -m "fix: complete automatic DO trend verification"
```

