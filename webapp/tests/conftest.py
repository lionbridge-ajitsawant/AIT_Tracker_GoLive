"""Shared fixtures for the wizard's offline test suite.

Everything here runs against a scratch SQLite file and never touches
Microsoft Graph - analyze/review/save/demo mode are pure local logic (the
same "offline path" the old ad hoc smoke_test.py/demo_check.py scripts
exercised), so no .env or credentials are needed to run this suite, in CI or
locally.
"""

import os
import sys
import tempfile
import uuid
from datetime import date
from pathlib import Path

import openpyxl
import pytest

WEBAPP_DIR = Path(__file__).resolve().parents[1]
ROOT = WEBAPP_DIR.parent
sys.path.insert(0, str(WEBAPP_DIR))
sys.path.insert(0, str(ROOT / "scripts"))

# Must be set before `import app`, since store.py reads it once at import time.
os.environ["WIZARD_DB_PATH"] = str(Path(tempfile.gettempdir()) / f"ait_wizard_test_{uuid.uuid4().hex}.db")

import app as wizard_app  # noqa: E402


@pytest.fixture
def client():
    wizard_app.app.config["TESTING"] = True
    with wizard_app.app.test_client() as c:
        yield c


@pytest.fixture
def a():
    """The app module, for calling its helpers (builtin_templates, etc.) directly."""
    return wizard_app


@pytest.fixture
def sample_workbook(tmp_path):
    """A minimal tracker workbook exercising all three column types analyze.py
    infers: a unique text column (-> title), a low-cardinality text column
    (-> choice), and a date column (-> dateTime)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Tracker"
    ws.append(["Title", "Status", "DueDate"])
    statuses = ["Open", "Closed", "Open", "In Progress", "Closed", "Open", "Closed", "Open"]
    for i, status in enumerate(statuses, start=1):
        ws.append([f"Item {i}", status, date(2026, 1, i)])
    path = tmp_path / "sample_tracker.xlsx"
    wb.save(path)
    return path


def include_all(schema):
    """Build the `list-N-include` / `col-N-M-include` form fields the review
    page's checkboxes (checked by default) send, for every list/column in a
    draft's schema - so a plain POST to /save keeps everything, matching what
    a PM sees who didn't uncheck anything."""
    form = {}
    for li, lst in enumerate(schema["lists"]):
        form[f"list-{li}-include"] = "on"
        for ci in range(len(lst["columns"])):
            form[f"col-{li}-{ci}-include"] = "on"
    return form
