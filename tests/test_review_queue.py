from datetime import datetime, timezone

import backend.services.review_queue as review_queue_module
from backend.services.review_queue import ReviewQueue


def test_due_returns_only_due_reviews(monkeypatch):
    scheduled = [
        {"concept": "variáveis", "next_review_at": "2026-09-03T10:00:00+00:00"},
        {"concept": "funções", "next_review_at": "2026-09-05T10:00:00+00:00"},
    ]

    monkeypatch.setattr(
        review_queue_module.ConceptProgress,
        "list_scheduled",
        lambda area: scheduled,
    )

    now = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)

    result = ReviewQueue.due("ads", now=now)

    assert [item["concept"] for item in result] == ["variáveis"]


def test_next_due_returns_first_due_review(monkeypatch):
    due = [
        {"concept": "variáveis"},
        {"concept": "condicionais"},
    ]

    monkeypatch.setattr(
        ReviewQueue,
        "due",
        lambda area, now=None: due,
    )

    assert ReviewQueue.next_due("ads")["concept"] == "variáveis"


def test_next_due_returns_none_when_queue_is_empty(monkeypatch):
    monkeypatch.setattr(
        ReviewQueue,
        "due",
        lambda area, now=None: [],
    )

    assert ReviewQueue.next_due("ads") is None
