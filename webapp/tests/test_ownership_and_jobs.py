"""Draft/job ownership (Easy Auth header) and the stale-job watchdog."""

import time

AUTH_HEADER = "X-MS-CLIENT-PRINCIPAL-NAME"


def test_owner_can_view_own_draft(client, a):
    r = client.post("/template", data={"template": _any_template(a)},
                     headers={AUTH_HEADER: "alice@example.com"})
    draft_id = r.headers["Location"].split("/")[-1]

    r = client.get(f"/review/{draft_id}", headers={AUTH_HEADER: "alice@example.com"})
    assert r.status_code == 200


def test_other_signed_in_user_is_denied(client, a):
    r = client.post("/template", data={"template": _any_template(a)},
                     headers={AUTH_HEADER: "alice@example.com"})
    draft_id = r.headers["Location"].split("/")[-1]

    r = client.get(f"/review/{draft_id}", headers={AUTH_HEADER: "bob@example.com"})
    assert r.status_code == 302
    assert r.headers["Location"] == "/"


def test_no_auth_header_is_unrestricted(client, a):
    """Local dev (python app.py, no Easy Auth in front) never sends this
    header - ownership must not lock the single local user out."""
    r = client.post("/template", data={"template": _any_template(a)},
                     headers={AUTH_HEADER: "alice@example.com"})
    draft_id = r.headers["Location"].split("/")[-1]

    r = client.get(f"/review/{draft_id}")  # no header at all
    assert r.status_code == 200


def test_signed_in_name_shown_in_page(client, a):
    r = client.get("/", headers={AUTH_HEADER: "alice@example.com"})
    assert b"Signed in as alice@example.com" in r.data


def test_unknown_job_returns_graceful_json(client):
    r = client.get("/progress/doesnotexist/log")
    assert r.status_code == 200
    body = r.get_json()
    assert body["done"] is True
    assert body["ok"] is False


def test_fresh_job_is_left_alone(client, a):
    a.set_job("fresh", {"log": ["starting"], "done": False, "ok": False, "updated_at": time.time()})
    body = client.get("/progress/fresh/log").get_json()
    assert body["done"] is False


def test_stale_job_is_marked_failed_once(client, a):
    stale_time = time.time() - (a.JOB_STALE_SECONDS + 60)
    a.set_job("stale", {"log": ["starting"], "done": False, "ok": False, "updated_at": stale_time})

    body = client.get("/progress/stale/log").get_json()
    assert body["done"] is True
    assert body["ok"] is False
    assert "no progress" in body["log"][-1].lower()

    # polling again must not append a second copy of the error line
    body2 = client.get("/progress/stale/log").get_json()
    assert body2["log"] == body["log"]


def test_finished_job_is_never_touched_by_watchdog(client, a):
    old_time = time.time() - 10_000
    a.set_job("done-long-ago", {"log": ["DONE."], "done": True, "ok": True, "updated_at": old_time})
    body = client.get("/progress/done-long-ago/log").get_json()
    assert body["log"] == ["DONE."]


def _any_template(a):
    return next(iter({p.stem for p in a.builtin_templates()}))
