# AIT Tracker — Go-Live Steps (set up the first real PM tracker)

Run these on the WORK computer. Access to /sites/AITTracker is already confirmed.
Target site: https://lionbridge.sharepoint.com/sites/AITTracker

-------------------------------------------------------------------------------
STEP 0 — Unzip & open a terminal
-------------------------------------------------------------------------------
Unzip anywhere, e.g.  C:\AIT_Tracker
Open PowerShell in that folder (Shift+Right-click > "Open PowerShell window here").

-------------------------------------------------------------------------------
STEP 1 — Create the config file (.env)
-------------------------------------------------------------------------------
1. Rename  env.TEMPLATE  to  .env
   (in PowerShell:  Rename-Item env.TEMPLATE .env )
2. Open .env in Notepad and replace  PASTE-SECRET-HERE  with the app client
   secret value (copy it from your saved copy). Everything else is filled in.
3. Save. NEVER share or email this file.

(If you already created a working .env on this machine earlier, just keep it.)

-------------------------------------------------------------------------------
STEP 2 — Install Python dependencies
-------------------------------------------------------------------------------
If this machine has internet (even via proxy):
    pip install -r requirements.txt

If pip is blocked, install offline from the bundled wheels (needs Python 3.13):
    pip install --no-index --find-links wheels -r requirements.txt

-------------------------------------------------------------------------------
STEP 3 — Confirm access (safe; creates then deletes a probe list)
-------------------------------------------------------------------------------
    cd scripts
    python check_access.py

Expect it to end with:  ALL CHECKS PASSED
If not, the message tells you exactly which step failed.

-------------------------------------------------------------------------------
STEP 4 — Create the tracker lists  (~30 seconds, no data yet)
-------------------------------------------------------------------------------
TIP: provision the cross-project HUB first (one time), so each tracker you
create auto-registers itself for the scaled automation flows:

    python provision.py --schema ..\schema\ait_master_hub.json

Then the project tracker (records you as PM in the registry):

    python provision.py --schema ..\schema\transcription_tracker.json --register-pm "Your Name"

Creates: Tracking, Partners, QA Issues, Issue Log on the site (with indexes and
clean status dropdowns). Re-runnable - safe to run twice. If the hub exists, it
also writes a row into AIT Projects so the master flows pick this tracker up
automatically (see docs\POWER_AUTOMATE_FLOWS.md). If the hub isn't there yet it
just skips that step - no error.

-------------------------------------------------------------------------------
STEP 5 — Load the data
-------------------------------------------------------------------------------
Point --source at the project workbook on THIS machine. Dry-run first:

    python migrate.py --schema ..\schema\transcription_tracker.json --source "C:\path\to\your\tracker.xlsx" --dry-run

Check the item counts and normalization report it prints. Then the real run:

    python migrate.py --schema ..\schema\transcription_tracker.json --source "C:\path\to\your\tracker.xlsx"

(The full 8,305-row tracker uploads in batches and takes a few minutes.
 For a lighter first test, use any single project's smaller workbook.)

-------------------------------------------------------------------------------
STEP 6 — Verify it all landed
-------------------------------------------------------------------------------
    python verify.py --schema ..\schema\transcription_tracker.json

You want OK on each list (list count vs the extract).

-------------------------------------------------------------------------------
STEP 7 — Hand it to the test PMs
-------------------------------------------------------------------------------
1. Open https://lionbridge.sharepoint.com/sites/AITTracker
   -> Site Contents -> Tracking. Confirm rows and status pills look right.
2. Give PMs edit access: Settings (gear) -> Site permissions ->
   add the test PMs to the MEMBERS group (Edit). Read-only -> Visitors.
3. Send them the Tracking list link and ask them to really push on it:
     - add a row with + New
     - change a Status (note it stays a clean dropdown)
     - bulk-edit a few rows in "Edit in grid view"
     - make a personal view ("My items")
     - two people edit at the same time
4. The PM how-to is in  docs\AIT_Tracker_PM_Guide.docx

FEEDBACK TO COLLECT: columns/names right? missing dropdown values?
does the daily flow beat the Excel file? -> this tunes the schema before
rolling wider.

-------------------------------------------------------------------------------
AFTER THE FIRST TEST (optional next steps)
-------------------------------------------------------------------------------
- Hub lists (cross-project registry powering the GPM/Quality dashboards):
    python provision.py --schema ..\schema\ait_master_hub.json
- PM self-service: double-click Start_Tracker_Wizard.bat, then use the
  real "Create tracker" button (NOT the orange DEMO one) so PMs spin up
  their own trackers from any Excel file. The wizard also auto-registers each
  tracker in the hub (there's a PM-name field on the create screen).
- Scaled automation that covers EVERY tracker at once (overdue digest,
  quality rollup): build specs in  docs\POWER_AUTOMATE_FLOWS.md

-------------------------------------------------------------------------------
SECURITY
-------------------------------------------------------------------------------
Keep .env (the secret) only on this managed work computer. Don't email/commit it.
For the eventual hosted wizard, the secret goes in the host's environment
variables, not in any file on a laptop.
