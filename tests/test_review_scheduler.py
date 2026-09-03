from datetime import datetime, timezone

from backend.services.review_scheduler import ReviewScheduler


def test_review_intervals_grow_with_success():
    assert ReviewScheduler.interval_days(0) == 1
    assert ReviewScheduler.interval_days(1) == 3
    assert ReviewScheduler.interval_days(2) == 7
    assert ReviewScheduler.interval_days(3) == 14
    assert ReviewScheduler.interval_days(4) == 30
    assert ReviewScheduler.interval_days(99) == 30


def test_difficulty_shortens_review_interval():
    assert ReviewScheduler.interval_days(2, 1) == 3
    assert ReviewScheduler.interval_days(4, 1) == 15
    assert ReviewScheduler.interval_days(4, 2) == 1


def test_invalid_counts_are_safe():
    assert ReviewScheduler.interval_days("x", -5) == 1
    assert ReviewScheduler.interval_days(-3, "x") == 1


def test_schedule_uses_deterministic_utc_time():
    now = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    progress = {"review_count": 1, "difficulty_count": 0}

    result = ReviewScheduler.schedule(progress, now=now)

    assert result == {
        "next_review_at": "2026-09-06T12:00:00+00:00",
    }

def test_review_is_due_when_time_arrives():
    now = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    progress = {"next_review_at": "2026-09-03T12:00:00+00:00"}

    assert ReviewScheduler.is_due(progress, now=now) is True


def test_review_is_not_due_before_time():
    now = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    progress = {"next_review_at": "2026-09-04T12:00:00+00:00"}

    assert ReviewScheduler.is_due(progress, now=now) is False


def test_review_without_valid_date_is_not_due():
    assert ReviewScheduler.is_due({}) is False
    assert ReviewScheduler.is_due({"next_review_at": "invalid"}) is False
