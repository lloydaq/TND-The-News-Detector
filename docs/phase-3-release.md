# Phase 3 — v1.0.0 Release Preparation

**Status:** in progress (initialized 2026-10-19)

## Why this phase exists

The repository had no phase or roadmap file. The README roadmap had two open
items: connecting the frontend to the live backend (now done and verified) and
improving deployment and configuration. "Phase N" elsewhere in the code refers
to earlier implementation history; for example, `schemas.py` accepts "Phase 3
names", meaning the superseded claim statuses `UNVERIFIED` and `MIXED_EVIDENCE`.
That is unrelated to this document.

This phase is release preparation, not feature work. Its job is to ship the
current, verified behaviour as v1.0.0.

## Objective

Release v1.0.0 with verified behaviour, accurate documentation, a clean
repository, and repeatable tests.

## Tasks

| # | Task | Status |
|---|---|---|
| 1 | Backend test suite green (`python -m pytest -q -rs`) | Done: 159 passed |
| 2 | Compile check (`python -m compileall -q app tests`) and `git diff --check` | Done |
| 3 | Browser regression suite: mocked API, Chromium, Firefox, WebKit, mobile | Done: 132 passed |
| 4 | Live integration: real backend, Ollama, GNews, GDELT | Done: 3 passed |
| 5 | Security properties covered by tests (SSRF, limits, malformed model output, error leakage, safe rendering) | Done |
| 6 | README accurate for setup, configuration, API, testing, and how to read results | Done |
| 7 | Review untracked files; decide commit or ignore for each | Recommendations made; awaiting owner decision |
| 8 | Release commit and `v1.0.0` tag | Awaiting owner approval |

## Acceptance criteria

* The backend suite and the default Playwright suite pass with no failures or skips.
* The live suite passes against a running backend, or any failure is traced
  to an external provider and is reported honestly in the UI.
* No secrets in tracked files; `.env` ignored.
* The README describes only verified behaviour.
* `git status` after the release commit shows nothing untracked that should be
  tracked.
* The tag is created only after the owner approves.

## Out of scope

* New product features, UI redesign, or changes to the risk-scoring model.
* Deployment infrastructure (hosting, reverse proxy, distributed rate
  limiting). This remains the open roadmap item "Improve deployment and
  configuration".
* Health checks that probe Ollama or the providers.
* Expanding evidence coverage beyond GNews and GDELT.

## Verification steps

```powershell
# Backend (from backend/, venv active)
python -m pytest -q -rs
python -m compileall -q app tests

# Browser (from the repository root)
npm run test:e2e
npm run test:e2e:live     # backend running

# Repository
git diff --check
git status --short
```
