# AIT Tracker — Master Flow Specs (build once, cover every tracker)

These flows are **registry-driven**: each one loops over the `AIT Projects` hub
list and acts on every tracker listed there. Because provisioning now
**auto-registers** each new tracker into `AIT Projects`, a flow built once
automatically covers tracker #1 and tracker #50 with zero per-list setup.

Two things make this work and must hold:
1. **Standard column names** across trackers (the wizard/templates enforce this):
   every project tracker has a list named **`Tracking`** with columns
   `DueDate`, `QCStatus`, `Owner`, `Language`, etc. (no spaces → the SharePoint
   *internal* name equals the name shown, so the OData filters below are literal).
2. **The hub is provisioned and trackers are registered.** Provision the hub once:
   `python provision.py --schema ..\schema\ait_master_hub.json`
   After that, every `provision.py` / wizard run writes/updates a row in
   `AIT Projects` (Title, TrackerSiteURL, PMOwner, ServiceType, ProjectStatus).

Licensing: all actions below use **standard connectors** (SharePoint, Outlook,
Teams, Forms) — included in M365, **no premium Power Automate license**.

Hub site (current): `https://lionbridge.sharepoint.com/sites/AITTracker`

---

## Flow 1 — Daily Overdue / At-Risk Digest

**Purpose:** every morning, tell each PM which of their items are past due and not
yet delivered — across all trackers, in one flow.

**Trigger**
- **Recurrence** — Frequency: Day, Interval: 1, e.g. 08:00 local. (Add a
  Mon–Fri condition if you don't want weekend mails.)

**Steps**
1. **Compose – Today** = `formatDateTime(utcNow(),'yyyy-MM-ddT00:00:00Z')`
2. **SharePoint → Get items** — *Projects*
   - Site Address: the hub site (`…/sites/AITTracker`)
   - List Name: **AIT Projects**
   - Filter Query: `ProjectStatus eq 'Active'`
3. **Apply to each** — over `value` from step 2. For each project:
   1. **Compose – SiteUrl** = `item()?['TrackerSiteURL']`
   2. **SharePoint → Get items** — *Overdue items in this tracker*
      - Site Address: **Enter custom value** → `@{outputs('Compose_-_SiteUrl')}`
      - List Name: **Enter custom value** → `Tracking`
      - Filter Query:
        `DueDate lt '@{outputs('Compose_-_Today')}' and QCStatus ne 'Delivered' and QCStatus ne 'Ready for Delivery'`
      - Top Count: 500
   3. **Condition** — `length(body('Get_items_overdue')?['value'])` is greater than 0
      - **If yes:**
        a. **Create HTML table** — From: the overdue items' `value`; Columns
           (custom): Title, Owner, DueDate, QCStatus, Language.
        b. **Send an email (V2)** — To: `item()?['PMOwner']` (or a fixed PM
           distribution list while testing); Subject:
           `Overdue — @{item()?['Title']} (@{length(...)} items)`; Body: the HTML table.
           *(Swap for **Post message in a chat or channel** to push to Teams instead.)*

**Scales because:** step 2 reads the registry; new trackers self-register, so they
appear in the loop automatically. Nothing is hard-coded to a list ID.

**Gotchas**
- Use **"Enter custom value"** for Site Address and List Name in step 3.2 — that's
  what lets one action hit every tracker's site.
- `QCStatus` values come from the schema; adjust the "done" states in the filter
  if you tune them.
- If a tracker has no `Tracking` list yet (hub-only project), the inner Get items
  errors — set that action's **Configure run after** / or filter the registry to
  rows whose `ServiceType` ≠ blank.

---

## Flow 2 — Quality Rollup → AIT Projects `QualityRAG`

**Purpose:** roll each project's QA reviews up into a single Green/Amber/Red on the
`AIT Projects` register, which the Power BI board reads. One flow, all projects.

**Source of truth:** the **`QA Records`** hub list (one row per review, with
`Project`, `QAScore`, `ReviewDate`).

**Trigger**
- **Recurrence** — Day, 1 (e.g. 06:00), or hourly if you want it fresher.

**Steps**
1. **Compose – WindowStart** = `addDays(utcNow(),-30,'yyyy-MM-ddT00:00:00Z')`
   (rolling 30-day quality; change the window as you like.)
2. **SharePoint → Get items** — *Active projects*
   - List Name: **AIT Projects**; Filter: `ProjectStatus eq 'Active'`
3. **Apply to each** — over the projects:
   1. **SharePoint → Get items** — *Recent QA for this project*
      - List Name: **QA Records**
      - Filter Query:
        `Project eq '@{item()?['Title']}' and ReviewDate ge '@{outputs('Compose_-_WindowStart')}'`
      - Top Count: 5000
   2. **Condition** — items count > 0
      - **If yes:**
        a. **Compose – AvgScore** =
           `div(add(0,...),length(...))` — simplest reliable way:
           - **Select** action: From = QA items' `value`, Map a single unnamed
             field = `item()?['QAScore']` → gives an array of scores.
           - **Compose – Avg** =
             `div(float(string(add(... )) ), length(body('Select')))`
             *(or use the community pattern: Initialize `var_sum`=0 then Apply to
             each add `QAScore`, then `div(var_sum, length(value))` — clearer to maintain.)*
        b. **Compose – RAG** (nested if; thresholds configurable):
           `if(greaterOrEquals(outputs('Compose_-_Avg'),93),'Green',if(greaterOrEquals(outputs('Compose_-_Avg'),90),'Amber','Red'))`
        c. **SharePoint → Update item** — *AIT Projects*
           - Id: `item()?['ID']`
           - `QualityRAG`: `@{outputs('Compose_-_RAG')}`
      - **If no (no QA in window):** optionally set `QualityRAG` = blank or leave as-is.
4. *(Optional)* after the loop, **Condition**: if any project flipped to **Red**,
   **Post to Teams** a "quality alert" so the QM sees it same day.

**Thresholds:** Green ≥ 93, Amber 90–92.9, Red < 90 — edit in the Compose–RAG
expression to match your SLA.

**Scales because:** loops the registry; `QA Records` is already one shared list, so
adding projects needs no flow changes.

---

## Bonus — Flow 3 (sketch): New-Tracker Onboarding

**Trigger:** SharePoint **When an item is created** on `AIT Projects` (fires the
moment provisioning registers a new tracker).
**Actions:** post "New tracker live: @{triggerBody()?['Title']} — @{…TrackerSiteURL}"
to the AIT leadership Teams channel; optionally create a Planner task to set up its
Power BI page. One flow, fires for every future tracker automatically.

---

## How to build & test
1. Power Automate (make.powerautomate.com) → **+ Create** → Scheduled cloud flow.
2. Add the actions above; use **Enter custom value** wherever a site/list must be
   dynamic (that's the scaling trick).
3. **Test → Manually** → Run. Check the run history; expand each action to see the
   filter results.
4. Start with email to **yourself** and one active project before turning on the
   loop for all and switching to Teams.

## Dependency checklist
- [ ] Hub provisioned: `provision.py --schema ..\schema\ait_master_hub.json`
- [ ] At least one project tracker provisioned (auto-registers itself)
- [ ] `QA Records` getting rows (manual entry, or a QA-sync flow) for Flow 2
- [ ] PMOwner populated on registry rows (pass `--register-pm "Name"` or the
      wizard's PM field) so Flow 1 can address mail
