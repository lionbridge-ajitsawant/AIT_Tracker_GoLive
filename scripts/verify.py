"""Compare item counts in the provisioned SharePoint Lists against the
dry-run extracts in out/, so you can confirm a migration landed completely.

Usage:  python verify.py --schema ..\\schema\\transcription_tracker.json
"""

import argparse
import json
from pathlib import Path

from auth import get_site_id
from graph_client import find_list, graph_request, make_session

ROOT = Path(__file__).resolve().parent.parent


def count_items(session, site_id, list_id) -> int:
    total = 0
    url = f"/sites/{site_id}/lists/{list_id}/items?$select=id&$top=999"
    while url:
        r = graph_request(session, "GET", url)
        r.raise_for_status()
        data = r.json()
        total += len(data.get("value", []))
        url = data.get("@odata.nextLink")
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", required=True)
    args = ap.parse_args()
    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))

    session = make_session()
    site_id = get_site_id(session)
    for spec in schema["lists"]:
        name = spec["displayName"]
        lst = find_list(session, site_id, name)
        if lst is None:
            print(f"{name}: LIST NOT FOUND")
            continue
        n = count_items(session, site_id, lst["id"])
        extract = ROOT / "out" / f"{name.lower().replace(' ', '_')}_items.json"
        if extract.exists():
            expected = len(json.loads(extract.read_text(encoding="utf-8")))
            flag = "OK" if n >= expected else "MISSING ITEMS"
            print(f"{name}: {n} items in list, {expected} in extract -> {flag}")
        else:
            print(f"{name}: {n} items in list (no local extract to compare)")


if __name__ == "__main__":
    main()
