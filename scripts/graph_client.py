"""Thin Graph HTTP helper with auth header, retries and 429 throttling support."""

import time

import requests

from auth import GRAPH, get_token


class _BearerAuth(requests.auth.AuthBase):
    """Attaches a fresh Authorization header to every request instead of one
    baked in at session creation. get_token() is backed by MSAL's own token
    cache, so this is a cheap cache hit until the token nears its ~1h expiry -
    at which point MSAL transparently fetches a new one. Keeps long-running
    migrations from outliving a token that was only valid at session start."""

    def __call__(self, r):
        r.headers["Authorization"] = f"Bearer {get_token()}"
        return r


def make_session() -> requests.Session:
    get_token()  # fail fast here with a clear error if auth is misconfigured
    s = requests.Session()
    s.auth = _BearerAuth()
    return s


def graph_request(session, method, url, max_retries=6, **kwargs):
    """Request with Retry-After handling for 429/503 throttling, and one retry
    on 401 (the auth hook attaches a fresh token on the retry)."""
    if url.startswith("/"):
        url = GRAPH + url
    for attempt in range(max_retries):
        r = session.request(method, url, **kwargs)
        if r.status_code in (429, 503):
            wait = int(r.headers.get("Retry-After", "5"))
            print(f"  throttled ({r.status_code}), waiting {wait}s ...")
            time.sleep(wait)
            continue
        if r.status_code == 401 and attempt == 0:
            print("  401 from Graph - re-authenticating and retrying once ...")
            continue
        return r
    return r


def find_list(session, site_id, display_name):
    url = f"/sites/{site_id}/lists?$select=id,displayName&$top=200"
    while url:
        r = graph_request(session, "GET", url)
        r.raise_for_status()
        data = r.json()
        for lst in data.get("value", []):
            if lst["displayName"].lower() == display_name.lower():
                return lst
        url = data.get("@odata.nextLink")
    return None
