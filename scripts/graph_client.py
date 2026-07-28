"""Thin Graph HTTP helper with auth header, retries and 429 throttling support."""

import time

import requests

from auth import GRAPH, get_token


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {get_token()}"
    return s


def graph_request(session, method, url, max_retries=6, **kwargs):
    """Request with Retry-After handling for 429/503 throttling."""
    if url.startswith("/"):
        url = GRAPH + url
    for attempt in range(max_retries):
        r = session.request(method, url, **kwargs)
        if r.status_code in (429, 503):
            wait = int(r.headers.get("Retry-After", "5"))
            print(f"  throttled ({r.status_code}), waiting {wait}s ...")
            time.sleep(wait)
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
