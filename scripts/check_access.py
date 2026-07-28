"""Verify the Tracker app's access after IT approval.

Checks, in order:
  1. token        - app-only token issued (client credentials), or device-code fallback
  2. site         - SITE_HOSTNAME/SITE_PATH from .env resolves
  3. read lists   - the granted role allows reading the site's lists
  4. create list  - creates a probe list, then deletes it (proves 'manage')

Usage:  python check_access.py
"""

import os
import sys

from auth import GRAPH, get_site_id
from graph_client import graph_request, make_session


def main() -> None:
    mode = "app-only (client secret)" if os.getenv("CLIENT_SECRET") else "delegated (device code)"
    print(f"auth mode: {mode}")

    print("1. acquiring token ...", end=" ")
    session = make_session()
    print("OK")

    print("2. resolving site ...", end=" ")
    site_id = get_site_id(session)
    print(f"OK ({site_id.split(',')[0]})")

    print("3. reading lists ...", end=" ")
    r = graph_request(session, "GET", f"/sites/{site_id}/lists?$select=id,displayName&$top=5")
    if not r.ok:
        sys.exit(f"FAILED ({r.status_code}): {r.text[:300]}\n"
                 "-> the app/user has no read access on this site yet.")
    print(f"OK ({len(r.json().get('value', []))} lists visible)")

    print("4. creating probe list ...", end=" ")
    r = graph_request(session, "POST", f"/sites/{site_id}/lists", json={
        "displayName": "ZZZ Access Probe (safe to delete)",
        "list": {"template": "genericList"},
    })
    if not r.ok:
        sys.exit(f"FAILED ({r.status_code}): {r.text[:300]}\n"
                 "-> read works but list creation doesn't: the site grant is likely "
                 "'write' or below. Ask the admin to grant role 'manage' "
                 "(see docs/IT_ACCESS_REQUEST.md, Part C).")
    probe_id = r.json()["id"]
    print("OK")

    print("   cleaning up probe list ...", end=" ")
    r = graph_request(session, "DELETE", f"/sites/{site_id}/lists/{probe_id}")
    print("OK" if r.ok else f"could not delete (status {r.status_code}) - remove "
          "'ZZZ Access Probe' manually in Site contents")

    print("\nALL CHECKS PASSED - run provision.py / the wizard against this site.")


if __name__ == "__main__":
    main()
