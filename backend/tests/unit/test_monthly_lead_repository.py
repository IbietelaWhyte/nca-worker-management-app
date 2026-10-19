"""Repository-level guards for monthly leads that no service test can see."""

from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import app.repository.monthly_leads.queries as q
from app.repository.monthly_leads.repository import MonthlyLeadRepository


def test_worker_embed_names_its_column():
    # monthly_leads has two FKs to workers (worker_id and created_by), so a bare workers(*) is
    # refused by PostgREST with PGRST201 and every read of the month fails.
    assert "workers!worker_id(*)" in q.SELECT_WITH_WORKER


def test_get_for_month_flattens_the_embed_onto_worker():
    client = MagicMock()
    worker_id = uuid4()
    row = {
        "id": str(uuid4()),
        "department_id": str(uuid4()),
        "worker_id": str(worker_id),
        "month": "2026-11-01",
        "created_by": None,
        "created_at": "2026-10-19T12:00:00+00:00",
        "workers": {
            "id": str(worker_id),
            "first_name": "Ada",
            "last_name": "Obi",
            "email": "ada@example.com",
            "phone": None,
            "is_active": True,
            "created_at": "2026-01-01T00:00:00+00:00",
        },
    }
    chain = client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value
    chain.execute.return_value = MagicMock(data=[row])

    leads = MonthlyLeadRepository(client).get_for_month(uuid4(), date(2026, 11, 1))

    assert leads[0].worker is not None
    assert leads[0].worker.first_name == "Ada"
    client.table.return_value.select.assert_called_once_with(q.SELECT_WITH_WORKER)
