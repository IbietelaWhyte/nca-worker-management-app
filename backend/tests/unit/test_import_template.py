import csv
from pathlib import Path

import pytest

from app.core.phone import normalize_phone
from app.schemas.workers.models import WorkerImportRow
from app.service.workers.service import REQUIRED_IMPORT_COLUMNS

# The template users download from the import dialog. It lives in the frontend's static assets, but
# the parser that has to accept it lives here, so the drift guard belongs with the parser.
TEMPLATE = Path(__file__).resolve().parents[3] / "frontend" / "public" / "worker-import-sample.csv"


@pytest.fixture
def rows() -> list[dict[str, str]]:
    with TEMPLATE.open(encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_template_exists():
    assert TEMPLATE.is_file(), f"missing import template at {TEMPLATE}"


def test_template_header_matches_required_columns(rows):
    # If someone adds a required column without updating the sample, every user who downloads the
    # template, fills it in and uploads it gets a rejection. Fail here instead.
    assert rows, "template has no example rows"
    assert set(rows[0]) == set(REQUIRED_IMPORT_COLUMNS)


def test_template_rows_pass_validation(rows):
    # The template doubles as the format documentation, so its examples must be genuinely valid.
    for row in rows:
        WorkerImportRow(**row)


def test_template_phone_numbers_are_already_e164(rows):
    for row in rows:
        assert row["phone"] == normalize_phone(row["phone"])
