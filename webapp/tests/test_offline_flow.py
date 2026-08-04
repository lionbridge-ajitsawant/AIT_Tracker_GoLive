"""The offline wizard path: upload/template -> review -> save -> dry-run
preview. None of this touches SharePoint - it's the same ground the old
smoke_test.py script covered by hand."""

from pathlib import Path

from conftest import include_all


def test_index_lists_templates(client, a):
    projects, _hub = a.template_catalog()
    r = client.get("/")
    assert r.status_code == 200
    for p in projects:
        assert p["name"].encode() in r.data


def test_use_template_creates_draft_and_redirects(client, a):
    name = next(iter({p.stem for p in a.builtin_templates()}))
    r = client.post("/template", data={"template": name})
    assert r.status_code == 302
    assert "/review/" in r.headers["Location"]


def test_use_template_rejects_unknown_name(client):
    r = client.post("/template", data={"template": "does-not-exist"})
    assert r.status_code == 302
    assert r.headers["Location"] == "/"


def test_analyze_infers_expected_column_types(client, a, sample_workbook):
    with open(sample_workbook, "rb") as f:
        r = client.post("/analyze", data={"workbook": (f, "sample_tracker.xlsx")})
    draft_id = r.headers["Location"].split("/")[-1]
    draft = a.get_draft(draft_id)

    lst = draft["schema"]["lists"][0]
    cols = {c["name"]: c for c in lst["columns"]}
    assert lst["source"]["titleCol"] == 0  # the unique "Title" column, excluded from columns
    assert "choice" in cols["Status"]
    assert sorted(cols["Status"]["choice"]["choices"]) == ["Closed", "In Progress", "Open"]
    assert "dateTime" in cols["DueDate"]


def test_review_renders_detected_columns(client, sample_workbook):
    with open(sample_workbook, "rb") as f:
        r = client.post("/analyze", data={"workbook": (f, "sample_tracker.xlsx")})
    draft_id = r.headers["Location"].split("/")[-1]
    r = client.get(f"/review/{draft_id}")
    assert r.status_code == 200
    assert b"Status" in r.data
    assert b"DueDate" in r.data


def test_analyze_rejects_non_xlsx(client):
    r = client.post("/analyze", data={"workbook": (b"not a workbook", "notes.txt")})
    assert r.status_code == 302
    assert r.headers["Location"] == "/"


def test_save_writes_schema_and_dry_run_preview(client, a, sample_workbook):
    with open(sample_workbook, "rb") as f:
        r = client.post("/analyze", data={"workbook": (f, "sample_tracker.xlsx")})
    draft_id = r.headers["Location"].split("/")[-1]
    draft = a.get_draft(draft_id)

    form = {"project": "Smoke Project", **include_all(draft["schema"])}
    r = client.post(f"/save/{draft_id}", data=form)
    assert r.status_code == 302
    assert r.headers["Location"].endswith(f"/launch/{draft_id}")

    saved = a.get_draft(draft_id)
    assert Path(saved["schema_path"]).exists()
    preview = saved["preview"]
    assert len(preview) == 1
    assert preview[0]["count"] == 8  # the 8 data rows sample_workbook contains

    r = client.get(f"/launch/{draft_id}")
    assert r.status_code == 200
    assert b"Smoke Project" in r.data


def test_missing_draft_redirects_home(client):
    for path in ("/review/doesnotexist", "/launch/doesnotexist"):
        r = client.get(path)
        assert r.status_code == 302
        assert r.headers["Location"] == "/"
    r = client.post("/save/doesnotexist", data={})
    assert r.status_code == 302
