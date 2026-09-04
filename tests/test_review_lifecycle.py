from datetime import datetime, timezone

import backend.services.review_lifecycle as lifecycle_module
from backend.services.review_lifecycle import ReviewLifecycle


def test_activate_due_enters_review_stage(monkeypatch):
    progress = {
        "concept_id": "ads.variables",
        "concept": "variáveis",
        "mastery": 0.85,
        "difficulty_count": 1,
        "last_evidence": "Dominou o conceito.",
    }
    captured = {}

    monkeypatch.setattr(
        lifecycle_module.ReviewQueue,
        "next_due",
        lambda area, now=None, **kwargs: progress,
    )

    def fake_update(area, **changes):
        captured.update(changes)
        return {"area": area, **changes}

    monkeypatch.setattr(
        lifecycle_module.LearnerState,
        "update",
        fake_update,
    )

    ReviewLifecycle.activate_due("ads")

    assert captured["current_concept_id"] == "ads.variables"
    assert captured["stage"] == "reencontrar"
    assert captured["mastery"] == 0.85
    assert captured["difficulty_count"] == 1


def test_successful_review_is_recorded_and_rescheduled(monkeypatch):
    now = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    progress = {
        "concept_id": "ads.variables",
        "concept": "variáveis",
        "review_count": 1,
        "difficulty_count": 0,
        "next_review_at": "2026-09-03T10:00:00+00:00",
    }
    captured = {}

    monkeypatch.setattr(
        lifecycle_module.ConceptProgress,
        "get",
        lambda area, concept, **kwargs: progress,
    )
    monkeypatch.setattr(
        lifecycle_module.ReviewScheduler,
        "is_due",
        lambda progress, now=None: True,
    )
    monkeypatch.setattr(
        lifecycle_module.ReviewScheduler,
        "schedule",
        lambda progress, now=None: {
            "next_review_at": "2026-09-10T12:00:00+00:00"
        },
    )

    def fake_progress_update(area, concept, **changes):
        captured["progress"] = changes
        return {"area": area, "concept": concept, **changes}

    def fake_state_update(area, **changes):
        captured["state"] = changes
        return {"area": area, **changes}

    monkeypatch.setattr(
        lifecycle_module.ConceptProgress,
        "update",
        fake_progress_update,
    )
    monkeypatch.setattr(
        lifecycle_module.LearnerState,
        "update",
        fake_state_update,
    )

    learner_state = {
        "current_concept_id": "ads.variables",
        "current_concept": "variáveis",
        "stage": "fixar",
        "mastery": 0.9,
        "difficulty_count": 0,
        "last_evidence": "Recordou corretamente.",
    }

    ReviewLifecycle.complete_due(
        "ads",
        "variáveis",
        learner_state,
        now=now,
    )

    assert captured["progress"]["review_count"] == 2
    assert captured["progress"]["last_reviewed_at"] == "2026-09-03T12:00:00+00:00"
    assert captured["progress"]["next_review_at"] == "2026-09-10T12:00:00+00:00"
    assert captured["state"] == {
        "stage": "concluido",
        "student_id": "student_default",
    }


def test_review_cannot_complete_for_another_concept(monkeypatch):
    progress = {
        "concept_id": "ads.variables",
        "concept": "variáveis",
        "review_count": 1,
        "next_review_at": "2026-09-03T10:00:00+00:00",
    }

    monkeypatch.setattr(
        lifecycle_module.ConceptProgress,
        "get",
        lambda area, concept, **kwargs: progress,
    )
    monkeypatch.setattr(
        lifecycle_module.ReviewScheduler,
        "is_due",
        lambda progress, now=None: True,
    )

    learner_state = {
        "current_concept_id": "ads.functions",
        "current_concept": "funções",
        "stage": "fixar",
        "mastery": 0.9,
    }

    result = ReviewLifecycle.complete_due(
        "ads",
        "variáveis",
        learner_state,
    )

    assert result is None
