"""Microsoft Graph authentication for the Tracker app registration.

Two modes, picked automatically:
  - CLIENT_SECRET set in .env  -> app-only client-credentials flow
    (requires IT to grant an Application permission, ideally Sites.Selected).
  - CLIENT_SECRET empty        -> interactive device-code sign-in as you
    (uses the app's public-client redirect; needs delegated Sites.ReadWrite.All).
"""

import os
import sys
import atexit
from pathlib import Path

import msal
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

GRAPH = "https://graph.microsoft.com/v1.0"
TENANT_ID = os.getenv("TENANT_ID", "")
CLIENT_ID = os.getenv("CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
CACHE_FILE = Path(__file__).resolve().parent.parent / ".msal_token_cache.bin"


def get_token() -> str:
    if not TENANT_ID or not CLIENT_ID:
        sys.exit("TENANT_ID / CLIENT_ID missing - copy .env.example to .env and fill it in.")

    if CLIENT_SECRET:
        app = msal.ConfidentialClientApplication(
            CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    else:
        cache = msal.SerializableTokenCache()
        if CACHE_FILE.exists():
            cache.deserialize(CACHE_FILE.read_text())
        atexit.register(
            lambda: CACHE_FILE.write_text(cache.serialize()) if cache.has_state_changed else None
        )
        app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=cache)
        scopes = ["Sites.ReadWrite.All"]
        result = None
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(scopes, account=accounts[0])
        if not result:
            flow = app.initiate_device_flow(scopes=scopes)
            if "user_code" not in flow:
                sys.exit(f"Device flow failed: {flow}")
            print(flow["message"])  # "go to https://microsoft.com/devicelogin and enter CODE"
            result = app.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        sys.exit(f"Auth failed: {result.get('error')}: {result.get('error_description')}")
    return result["access_token"]


def get_site_id(session) -> str:
    """Resolve the Graph site id from SITE_HOSTNAME + SITE_PATH in .env."""
    hostname = os.getenv("SITE_HOSTNAME", "")
    site_path = os.getenv("SITE_PATH", "")
    if not hostname or not site_path:
        sys.exit("SITE_HOSTNAME / SITE_PATH missing in .env (e.g. lionbridge.sharepoint.com + /sites/Tracker).")
    r = session.get(f"{GRAPH}/sites/{hostname}:{site_path}")
    r.raise_for_status()
    return r.json()["id"]
