"""Demo mode: simulates list creation + migration locally and renders a
SharePoint-style browsing UI, writing nothing to SharePoint. Same ground the
old demo_check.py script covered by hand."""

from conftest import include_all


def _saved_draft_id(client, a, sample_workbook):
    with open(sample_workbook, "rb") as f:
        r = client.post("/analyze", data={"workbook": (f, "sample_tracker.xlsx")})
    draft_id = r.headers["Location"].split("/")[-1]
    draft = a.get_draft(draft_id)
    form = {"project": "Demo Project", **include_all(draft["schema"])}
    client.post(f"/save/{draft_id}", data=form)
    return draft_id


def test_demo_create_then_browse(client, a, sample_workbook):
    draft_id = _saved_draft_id(client, a, sample_workbook)

    r = client.post(f"/demo/{draft_id}")
    assert r.status_code == 302
    assert r.headers["Location"].endswith(f"/demo/{draft_id}/progress")

    r = client.get(f"/demo/{draft_id}/progress")
    assert r.status_code == 200
    assert b"DONE" in r.data

    r = client.get(f"/demo/{draft_id}/site/0")
    assert r.status_code == 200
    assert b"Item 1" in r.data  # a row from the extracted workbook data


def test_demo_add_item_persists(client, a, sample_workbook):
    draft_id = _saved_draft_id(client, a, sample_workbook)
    client.post(f"/demo/{draft_id}")

    r = client.post(f"/demo/{draft_id}/site/0/new", data={"Title": "Hand-typed row"})
    assert r.status_code == 302

    draft = a.get_draft(draft_id)
    titles = [item.get("Title") for item in draft["demo_lists"][0]["items"]]
    assert "Hand-typed row" in titles

    r = client.get(f"/demo/{draft_id}/site/0")
    assert b"Hand-typed row" in r.data


def test_demo_routes_require_an_existing_draft(client):
    for path in ("/demo/doesnotexist/progress", "/demo/doesnotexist/site"):
        r = client.get(path)
        assert r.status_code == 302
    r = client.post("/demo/doesnotexist")
    assert r.status_code == 302


def test_demo_progress_requires_demo_create_first(client, a, sample_workbook):
    with open(sample_workbook, "rb") as f:
        r = client.post("/analyze", data={"workbook": (f, "sample_tracker.xlsx")})
    draft_id = r.headers["Location"].split("/")[-1]
    # never called /demo/<id> to populate demo_log
    r = client.get(f"/demo/{draft_id}/progress")
    assert r.status_code == 302
