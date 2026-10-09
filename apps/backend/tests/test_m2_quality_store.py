"""Unit contracts for durable QA boundaries."""
import pytest

from ago.quality import Verdict
from ago.quality_store import QualityStore
from ago.security import Principal


class FakeCursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeTx:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeConnection:
    def __init__(self):
        self.queries = []

    def transaction(self):
        return FakeTx()

    def execute(self, sql, params):
        self.queries.append((sql, params))
        if "FROM ago_users u" in sql:
            return FakeCursor({"ok": True})
        if "FROM ago_governed_tasks" in sql:
            return FakeCursor({"assignee_id": "11111111-1111-1111-1111-111111111111", "status": "completed"})
        if "FROM ago_employees" in sql:
            return FakeCursor({"ok": True})
        if "FROM ago_task_reviews" in sql:
            return FakeCursor({"ok": True})
        return FakeCursor(None)


def test_qa_review_requires_separate_author_and_reviewer():
    db = FakeConnection()
    principal = Principal(
        "22222222-2222-2222-2222-222222222222",
        "33333333-3333-3333-3333-333333333333",
        ("reviewer",),
    )
    review = QualityStore(db).review(
        task_id="44444444-4444-4444-4444-444444444444",
        principal=principal, verdict=Verdict.PASS, evidence="Test artifacts inspected",
    )
    assert review.reviewer_id != review.author_id
    assert any("INSERT INTO ago_task_reviews" in sql for sql, _ in db.queries)


def test_qa_no_blank_evidence():
    db = FakeConnection()
    principal = Principal(
        "22222222-2222-2222-2222-222222222222",
        "33333333-3333-3333-3333-333333333333",
        ("reviewer",),
    )
    with pytest.raises(ValueError):
        QualityStore(db).review(
            task_id="44444444-4444-4444-4444-444444444444",
            principal=principal, verdict=Verdict.FAIL, evidence="",
        )
    assert not any("INSERT INTO ago_task_reviews" in sql for sql, _ in db.queries)
