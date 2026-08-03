# AIT Tracker Wizard — Hosting Setup (one URL for the whole PM team)

Goal: replace "double-click a .bat on each laptop" with a single URL behind
Microsoft 365 sign-in. PMs open it in a browser — no Python, no install, no
launcher — pick a template, and create their tracker.

Target platform: **Azure App Service (Linux, Python)**. This is an IT/admin
task, done once. ~1–2 hours.

---

## The most important concept: TWO app registrations, different jobs

Do not confuse these — keeping them separate is what makes the security clean:

| | **AIT Tracker Sharepoint Access** (you already have) | **The SSO app** (created during hosting) |
|---|---|---|
| Job | Backend identity that **creates lists in SharePoint** via Graph | Front-door **"who are you"** login for PMs |
| Auth | App-only, **client secret** | Sign-in only (no secret used by your code) |
| Permission | `Sites.Selected` + per-site `manage` grant | Just sign-in / read profile |
| Where it lives | the wizard's `CLIENT_SECRET` env var | App Service "Authentication" feature |

The PM signs in against the **SSO app** (proves they're a Lionbridge PM). Once
past the door, the wizard uses the **backend app's secret** to do the SharePoint
work. PMs never see or hold the secret.

> Security consequence: anyone who can reach the URL **and** sign in can create
> lists on the granted sites. So the front door must require auth AND be limited
> to the PM group (Step 5). Keep the per-site grants scoped to tracker sites only.

---

## Prerequisites
- Azure subscription + permission to create an App Service (you or IT).
- The go-live code (this repo / the bundle) — `webapp/`, `scripts/`, `schema/`,
  `requirements.txt`.
- The backend app's client secret value (the one in your local `.env`).
- A security group containing the PMs (or create one), e.g. `AIT-PMs`.
- Recommended plan: **Basic B1** (~$13/mo) — supports Always On and built-in auth.
  (Free/Shared tiers don't.)

---

## Step 1 — Prep (no code changes needed; just know these)
- In the cloud there is **no `.env`** — config comes from **App Settings**
  (environment variables). The code already reads env vars, so nothing to change.
- Drafts and running-job progress live in a **SQLite file** (`webapp/store.py`),
  not in process memory, so any worker/thread can serve any request — a PM's
  progress page can be polled by a different worker than the one running their
  job. Point it at persistent storage outside the deployed code folder with the
  `WIZARD_DB_PATH` app setting (Step 3), so redeploys never touch it.
- The wizard runs provisioning/migration on a **background thread**; the page
  polls for progress. `--workers` can be >1 now (state is shared via SQLite,
  not per-process memory) — just keep it to **one App Service instance** (see
  *Scale*, below): SQLite is a single file, so it doesn't hand off cleanly
  across multiple scaled-out instances.
- The site URL is entered per-create in the wizard form, so `SITE_HOSTNAME/PATH`
  are optional in the cloud.

**Startup command** (set in Step 2 / portal → Configuration → General settings):
```
gunicorn --chdir webapp --workers 2 --threads 8 --timeout 600 --bind=0.0.0.0:8000 app:app
```
(App Service's Python image provides gunicorn; `--chdir webapp` points it at
`app.py`.)

---

## Step 2 — Deploy the code

**Option A — VS Code (simplest):** install the *Azure App Service* extension →
sign in → right-click the `lionbridge_tracker_solution` folder → **Deploy to Web
App** → create a new Linux Python 3.11+ app → confirm. Set the startup command
when prompted (or in Step 3).

**Option B — Azure CLI:**
```bash
cd lionbridge_tracker_solution
az webapp up --name ait-tracker-wizard --runtime "PYTHON:3.11" --sku B1 --os-type Linux
az webapp config set --name ait-tracker-wizard --resource-group <rg> \
  --startup-file "gunicorn --chdir webapp --workers 1 --threads 8 --timeout 600 --bind=0.0.0.0:8000 app:app"
```

Either way Azure runs Oryx, which installs `requirements.txt` automatically.

---

## Step 3 — App Settings (the config + secret)

Portal → your App Service → **Settings → Environment variables → App settings**.
Add:

| Name | Value |
|---|---|
| `TENANT_ID` | `42dc8b0f-4759-4afe-9348-41952eeaf98b` |
| `CLIENT_ID` | `473b608d-4f6d-4e72-b888-a9dc9bd0e566` |
| `CLIENT_SECRET` | the backend app secret value |
| `WEBSITES_PORT` | `8000` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |
| `WIZARD_DB_PATH` | `/home/data/state.db` |

**Better for the secret: Azure Key Vault.** Put the secret in a Key Vault and set
`CLIENT_SECRET` to a Key Vault reference:
`@Microsoft.KeyVault(SecretUri=https://<vault>.vault.azure.net/secrets/tracker-secret/)`
then give the App Service a **managed identity** with *Get* on that vault. The
secret then never appears in App Settings in clear text, and rotating it is a
one-place change.

Also enable **Settings → Configuration → Always On = On** (keeps the app and its
background threads alive).

---

## Step 4 — Turn on Microsoft 365 single sign-on

Portal → your App Service → **Settings → Authentication → Add identity provider**:
- Provider: **Microsoft**
- App registration: **Create new app registration** (this is the SSO app from the
  table above — separate from the backend app)
- Supported account types: **Current tenant — single tenant**
- Restrict access: **Require authentication**
- Unauthenticated requests: **HTTP 302 redirect to log in** (browser app)
- Token store: **On** → Add.

Now hitting the URL forces a Lionbridge sign-in before the wizard loads. The
wizard already reads the `X-MS-CLIENT-PRINCIPAL-NAME` header Easy Auth injects:
it shows "Signed in as ..." in the header with a sign-out link, pre-fills the
PM name on the create screen, and scopes each draft/job to the PM who created
it (another signed-in PM opening the link gets bounced home). None of that
needs extra setup — it activates automatically once this step is done.

---

## Step 5 — Limit it to the PM team (do not skip)

By default any org user can sign in. Restrict to PMs:
Entra admin center → **Enterprise applications** → the SSO app just created →
- **Properties → Assignment required? = Yes**
- **Users and groups → Add** → your `AIT-PMs` security group.

Only assigned PMs can now reach the wizard. (This is the gate that matters,
because the wizard can create SharePoint lists.)

---

## Step 6 — Test
1. Open `https://ait-tracker-wizard.azurewebsites.net` in a private window.
2. You should be redirected to Microsoft sign-in; sign in as a PM.
3. Pick a template → review → **Create tracker** → it provisions to the live
   site with no device-code prompt (the backend secret is used silently).
4. Try as a non-PM account → should be denied at sign-in.

Share that URL with the PM team. Add it as a tile on the AIT SharePoint site or a
Teams tab.

---

## Notes & options
- **Scale:** keep it single-instance. Draft/job state now survives worker
  restarts and is shared across the instance's own workers/threads via SQLite
  (`WIZARD_DB_PATH`), which is what let `--workers` go above 1 — but SQLite is
  still one file, so it doesn't hand off cleanly if you scale out to *multiple*
  instances. A handful of PMs is well within one B1 instance; if you outgrow
  that, move `webapp/store.py` to Azure SQL/Postgres before scaling out.
- **Token lifetime:** the Graph app-only token used for provisioning/migration
  now refreshes itself automatically (MSAL's cache is reused across calls
  instead of being rebuilt empty each time) — no action needed even for very
  long migrations.
- **Uploads:** the wizard writes uploaded workbooks under `/home` (persistent on
  App Service). They're transient working files; clear occasionally if you like.
- **Custom domain:** map `trackers.lionbridge.com` (or similar) in *Custom domains*
  if you want a friendlier URL than `*.azurewebsites.net`.
- **Updates:** to push new code later, redeploy (Option A/B). App Settings and the
  auth config persist across deploys.
- **Rollback:** App Service keeps deployment history; you can swap back, or use a
  staging slot for zero-downtime updates.

---

## What changes for PMs vs the local launcher
| | Local `.bat` | Hosted |
|---|---|---|
| Install | Python + first-run pip | nothing |
| Launch | double-click the launcher | open a URL |
| Sign-in | device code first time | normal M365 SSO |
| Secret | in each machine's `.env` | one place (Key Vault) |
| Updates | recopy the bundle | redeploy once |

The local bundle stays useful for you/admins and for offline demos; hosting is
how the **whole PM team** gets it with zero friction.
