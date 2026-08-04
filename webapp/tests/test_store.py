"""Unit tests for the SQLite draft/job store, independent of Flask."""

import uuid

import store


def test_unknown_draft_and_job_return_none():
    assert store.get_draft(uuid.uuid4().hex) is None
    assert store.get_job(uuid.uuid4().hex) is None


def test_draft_roundtrip():
    draft_id = uuid.uuid4().hex
    payload = {"schema": {"project": "X", "lists": []}, "source": None, "owner": "alice"}
    store.set_draft(draft_id, payload)
    assert store.get_draft(draft_id) == payload


def test_job_roundtrip_and_overwrite():
    job_id = uuid.uuid4().hex
    store.set_job(job_id, {"log": ["a"], "done": False, "ok": False})
    store.set_job(job_id, {"log": ["a", "b"], "done": True, "ok": True})
    assert store.get_job(job_id) == {"log": ["a", "b"], "done": True, "ok": True}
