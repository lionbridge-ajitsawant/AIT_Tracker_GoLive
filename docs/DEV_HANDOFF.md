# AIT Tracker Solution — Developer Handoff & Deployment Guide

Audience: the Lionbridge dev team taking ownership of this solution, and the PM
team who will run the first deployment.

---

## 1. What this is

Replaces the shared-Excel tracker process with **SharePoint Lists** as the data
layer. Lists are provisioned and populated via **Microsoft Graph** using the
Entra app registration **"AIT Tracker Sharepoint Access"**
(client id `473b608d-4f6d-4e72-b888-a9dc9bd0e566`).

Three ways to use it, all driven by the same engine:

| Entry point | Who | What it does |
|---|---|---|
| `Start_Tracker_Wizard.bat` → Flask web UI (`webapp/`) | PMs | Upload any Excel tracker or pick a template → review columns → create lists + migrate data, self-service |
| CLI scripts (`scripts/`) | Dev / power users | `analyze.py` → `provision.py` → `migrate.py` → `verify.py`, scriptable and bulk-capable |
| Schema templates (`schema/*.json`) | Both | Standard list/column definitions so every project uses identical naming |

Full design rationale, architecture diagram, and requirements traceability are
in `README.md`. Detailed how-tos already exist and stay valid:

- `docs/IT_ACCESS_REQUEST.md` — the Sites.Selected permission request for IT
- `docs/HOSTING_SETUP.md` — hosting the wizard centrally (Azure App Service)
- `docs/POWER_AUTOMATE_FLOWS.md` — specs for the cross-project automation flows
- `docs/AIT_Tracker_PM_Guide.docx` — end-user guide for PMs
- `build/AIT_Tracker_GoLive/GO_LIVE_STEPS.md` — step-by-step first deployment

## 2. Current state (July 2026)

- All scripts and the wizard are working and validated end-to-end in dry-run
  mode against the real transcription tracker (8,305 rows extracted, cleaned,
  and normalized; see `out/`). Offline smoke tests pass (`webapp/smoke_test.py`,
  `webapp/demo_check.py`).
- **App-only auth is fully approved and working.** `Sites.Selected`
  (Application) has admin consent plus the per-site `manage` grant on
  `https://lionbridge.sharepoint.com/sites/AITTracker`; `check_access.py`
  passed all checks on 2026-06-17. Note: `Sites.Selected` needs BOTH admin
  consent AND a separate per-site grant
  (`Grant-PnPAzureADAppSitePermission`, requires a SharePoint admin) — consent
  alone yields 403. Delegated `Sites.ReadWrite.All` (device-code fallback) is
  admin-locked in this tenant, so app-only with the client secret is the path.
- The wizard runs locally only. Central hosting is designed
  (`docs/HOSTING_SETUP.md`) but not yet deployed.
- Power Automate flows and Power BI dashboards are specified
  (`docs/POWER_AUTOMATE_FLOWS.md`, README) but not yet built.

## 3. Repo layout & source of truth

```
scripts/            CLI engine (auth, Graph client, analyze/provision/migrate/verify)
webapp/             Flask wizard (app.py + templates) and offline smoke tests
schema/             list/column templates; schema/generated/ = wizard output
samples/            source workbooks used for design and testing
docs/               guides + the python-docx/pptx generators for the .docx/.pptx deliverables
out/                dry-run extracts (generated, disposable)
build/              packaged distribution folders (Demo, GoLive) + zips at root
```

**The root `scripts/`, `webapp/`, `schema/` are the source of truth.**
`build/AIT_Tracker_GoLive/` and `build/AIT_Tracker_Demo/` are self-contained
snapshots (with bundled wheels for offline install). The GoLive folder has been
synced with the latest code; **the two `.zip` files at the root are stale — re-zip
the build folders before distributing them again.**

## 4. Before anything else (day-one checklist)

1. **Rotate the client secret.** A live secret is present in the local `.env`
   of the original workstation and has been shared during the pilot. Create a
   new secret in the Entra portal for the app registration and revoke the old
   one before wider rollout.
2. **Put the code in source control.** The project is not yet a git repo. A
   `.gitignore` is included — it excludes `.env`, token caches, uploads,
   generated output, and the zips. Verify `.env` is untracked after `git init`.
3. **Recreate `.env` from `.env.example`** on whichever machine/host runs the
   tools. Never commit or email it.

## 5. Next steps for the dev team (prioritized)

### P1 — Auth ownership
- Access is already granted (see section 2). What transfers to the dev team:
  ownership of the app registration in Entra, secret rotation (section 4), and
  granting `Sites.Selected` `manage` on any **additional** tracker sites via
  `Grant-PnPAzureADAppSitePermission` (the request template is in
  `docs/IT_ACCESS_REQUEST.md`).
- After any change, run `python scripts/check_access.py` — it validates
  token → site → read → create in order and tells you exactly what is missing.

### P2 — Host the wizard centrally
`docs/HOSTING_SETUP.md` has the Azure App Service walkthrough. Engineering work
needed beyond that doc:

- **Replace the dev server** (`app.run`) with a production WSGI server
  (waitress on Windows, gunicorn on Linux).
- **Add sign-in** to the wizard itself (Entra ID / App Service Easy Auth) —
  today it has no authentication because it only runs on localhost.
- **Persist state.** `DRAFTS` and `JOBS` in `webapp/app.py` are in-memory
  dicts: fine for one local user, lost on restart, and not multi-worker safe.
  Move to a small store (SQLite/Redis/table storage) or pin to one worker.
- **Job execution.** Long migrations run in a background thread of the web
  process; on a host, move them to a worker/queue or accept single-worker.
- **Token lifetime.** `make_session()` acquires one token (~1 h). Very long
  migrations could outlive it — refresh the token per batch or on 401.

### P3 — Build the Power Platform layer
- Power Automate flows from `docs/POWER_AUTOMATE_FLOWS.md` (overdue digest,
  quality rollup, risk alerts) — they read the `AIT Projects` hub list, so they
  automatically cover every tracker that registers itself.
- Power BI dashboards over `AIT Projects` + `QA Records` (KPI mapping is in the
  README traceability table).

### P4 — Engineering hygiene
- Convert `webapp/smoke_test.py` and `webapp/demo_check.py` into pytest tests
  and wire up CI. They already cover the full offline path (analyze → review →
  save → dry-run preview).
- `webapp/drive_flow.py` / `drive_demo.py` are screenshot/demo drivers, not
  tests — keep or delete as you see fit.
- Known small limitations, acceptable today, worth a ticket each:
  - `provision.register_project` reads the first 500 hub rows only when
    checking for an existing project entry (no paging).
  - Choice-column dropdown values are seeded from observed data; PMs prune
    them in the wizard's review step, but there is no server-side validation
    that a renamed column is a valid SharePoint internal name beyond the
    alphanumeric filter.
  - The migration uploader batches 20 items per `$batch` request and reports
    per-item failures, but has no retry-and-resume for a partially failed run
    (re-running duplicates items; `verify.py` detects count mismatches).

## 6. Deployment steps for the PM team

The complete, tested runbook is **`build/AIT_Tracker_GoLive/GO_LIVE_STEPS.md`**.
Summary of the flow:

1. **Prepare** — unzip the GoLive package on the work machine, rename
   `env.TEMPLATE` to `.env`, paste the (new, rotated) client secret,
   `pip install -r requirements.txt` (offline wheels bundled).
2. **Check access** — `python scripts/check_access.py` → expect
   `ALL CHECKS PASSED`.
3. **Provision the hub once** —
   `python provision.py --schema ..\schema\ait_master_hub.json`
   (creates AIT Projects, Resources Master, QA Records, Risk Log).
4. **Provision the project tracker** —
   `python provision.py --schema ..\schema\transcription_tracker.json --register-pm "Name"`.
   Idempotent; safe to re-run.
5. **Migrate the data** — dry-run first, inspect counts and the normalization
   report, then run live:
   `python migrate.py --schema ... --source "C:\path\tracker.xlsx" [--dry-run]`
6. **Verify** — `python verify.py --schema ...` → `OK` per list.
7. **Pilot** — grant test PMs Edit via the site Members group, send the list
   link and `docs/AIT_Tracker_PM_Guide.docx`, and collect feedback on column
   names and dropdown values before rolling wider.
8. **Self-service** — once the pilot passes, PMs create their own trackers via
   `Start_Tracker_Wizard.bat` (or the hosted wizard URL when P2 lands).

## 7. Support notes

- Re-running `provision.py` never destroys data: existing lists are kept and
  only missing columns are added.
- `migrate.py --dry-run` writes cleaned extracts to `out/` — always inspect
  before a live run.
- Demo mode in the wizard (orange button) simulates everything locally and
  writes nothing to SharePoint — safe for presentations.
- If Lists ever become limiting (column-level security, complex dependency
  rules), the upgrade path is Dataverse + model-driven Power Apps; the schemas
  in `schema/` map across nearly 1:1.
