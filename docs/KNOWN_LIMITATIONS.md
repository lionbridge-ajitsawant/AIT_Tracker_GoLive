# Known limitations — ready-to-file tickets

Three small, accepted-for-now gaps carried over from `DEV_HANDOFF.md`
(P4 — Engineering hygiene). None block go-live; each is scoped enough to be
its own ticket. Paste each section into GitHub Issues / Jira / Linear /
whatever tracker is in use — title is the `##` heading, body is the rest.

---

## Hub registry lookup doesn't paginate past 500 rows

**Where:** `scripts/provision.py:78-86`, inside `register_project()`

**Description:**
When provisioning a tracker, `register_project()` checks whether the project
already has a row in the `AIT Projects` hub list (to update it instead of
duplicating it) by fetching the first 500 items:

```python
r = graph_request(
    session, "GET",
    f"/sites/{site_id}/lists/{hub['id']}/items?$expand=fields(select=Title)&$top=500",
)
```

Unlike `find_list()` elsewhere in the same file, this call never follows
`@odata.nextLink`. Once the hub list passes 500 registered projects, lookups
for projects past that point will silently miss the existing row and create
a duplicate instead of updating it.

**Impact:** Low today (nowhere near 500 tracked projects), but silent —
nothing errors, it just starts duplicating hub rows once the threshold is
crossed.

**Fix:** Page through `@odata.nextLink` the same way `find_list()` already
does, or switch to a Graph `$filter` query on `Title` instead of pulling
every row client-side.

---

## No server-side validation of renamed SharePoint column names

**Where:** `webapp/app.py:269`, inside `save()`

**Description:** When a PM renames a column in the review step, the wizard
sanitizes it with a blunt regex:

```python
new_name = re.sub(r"[^A-Za-z0-9]", "", form.get(f"col-{li}-{ci}-name") or old_name) or old_name
```

This strips non-alphanumerics but doesn't check the result against
SharePoint's actual internal-name rules (e.g. can't start with certain
reserved prefixes, length limits, reserved words like `Attachments`,
`ContentType`, etc.). A PM could still submit a name that passes this filter
but gets rejected — or silently mangled — by the Graph API at provisioning
time, several steps after the point where they could easily fix it.

**Impact:** Low frequency (most renames are short business words), but when
it happens the failure surfaces late (at `/run`, not at `/save`) with a raw
Graph error in the job log instead of an inline form validation message.

**Fix:** Validate against SharePoint's internal-name constraints in `save()`
before writing the schema, and surface a specific error on the review page
instead of letting a bad name reach `provision.py`.

---

## Migration uploader has no retry/resume for partial failures

**Where:** `scripts/migrate.py:161-195`, `upload()`

**Description:** `upload()` batches 20 items per Graph `$batch` request and
reports per-item failures (`done`/`failed` counts, logs the first 5 failure
bodies), but if a run is interrupted partway (network blip, throttling that
exhausts retries, process killed) there's no resume: re-running `migrate.py`
against the same source re-uploads every item from the start, including the
ones that already succeeded, creating duplicates in the SharePoint list.
`scripts/verify.py` will catch the resulting count mismatch after the fact,
but there's no way to reconcile automatically — cleanup is manual (delete
the duplicates and re-run, or accept the drift).

**Impact:** Low frequency (batches are usually small enough to complete in
one run), but the failure mode is silent duplication, not a clean error, and
the wizard's UI (`webapp/app.py` `run_job()`) has no "resume this migration"
affordance — a PM would just click "Create tracker" again.

**Fix:** Track which source rows already uploaded successfully (e.g. a
`_migrated` marker written back to a local manifest keyed by title/row, or a
dedup check against existing list items by title before each batch) so a
re-run only sends what's missing.
