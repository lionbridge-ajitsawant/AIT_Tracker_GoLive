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

# One MSAL app instance per process, reused across every get_token() call. MSAL
# keeps an in-memory token cache on the instance and (since MSAL 1.23) checks it
# before calling out to Entra, so repeated calls are cheap and automatically
# return a fresh token once the cached one is near/past its ~1h expiry - no
# separate refresh-on-401 logic needed. A fresh instance per call (the old
# behaviour) defeated this: an empty cache every time meant callers that baked
# a token in once (e.g. a long migration's session) just kept using a token
# that eventually expired underneath them.
_confidential_app = None
_public_app = None
_public_cache = None


def _get_confidential_app():
    global _confidential_app
    if _confidential_app is None:
        _confidential_app = msal.ConfidentialClientApplication(
            CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
        )
    return _confidential_app


def _get_public_app():
    global _public_app, _public_cache
    if _public_app is None:
        _public_cache = msal.SerializableTokenCache()
        if CACHE_FILE.exists():
            _public_cache.deserialize(CACHE_FILE.read_text())
        atexit.register(
            lambda: CACHE_FILE.write_text(_public_cache.serialize())
            if _public_cache.has_state_changed else None
        )
        _public_app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=_public_cache)
    return _public_app


def get_token() -> str:
    if not TENANT_ID or not CLIENT_ID:
        sys.exit("TENANT_ID / CLIENT_ID missing - copy .env.example to .env and fill it in.")

    if CLIENT_SECRET:
        app = _get_confidential_app()
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    else:
        app = _get_public_app()
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
