import backend.services.concept_activation as activation_module
from backend.services.concept_activation import ConceptActivation


def test_new_concept_starts_clean(monkeypatch):
    progress = {
        "concept_id": "ads.functions",
        "concept": "funções",
        "mastery": 0.0,
        "difficulty_count": 0,
        "last_evidence": None,
        "updated_at": None,
    }
    captured = {}

    monkeypatch.setattr(
        activation_module.ConceptProgress,
        "get",
        lambda area, concept, **kwargs: progress,
    )

    def fake_update(area, **changes):
        captured.update(changes)
        return changes

    monkeypatch.setattr(
        activation_module.LearnerState,
        "update",
        fake_update,
    )

    ConceptActivation.activate("ads", "funções")

    assert captured["current_concept_id"] == "ads.functions"
    assert captured["stage"] == "compreender"
    assert captured["mastery"] == 0.0
    assert captured["difficulty_count"] == 0


def test_known_concept_restores_progress(monkeypatch):
    progress = {
        "concept_id": "ads.variables",
        "concept": "variáveis",
        "mastery": 0.65,
        "difficulty_count": 2,
        "last_evidence": "Entendeu parcialmente.",
        "updated_at": "2026-09-03 12:00:00",
    }
    captured = {}

    monkeypatch.setattr(
        activation_module.ConceptProgress,
        "get",
        lambda area, concept, **kwargs: progress,
    )

    def fake_update(area, **changes):
        captured.update(changes)
        return changes

    monkeypatch.setattr(
        activation_module.LearnerState,
        "update",
        fake_update,
    )

    ConceptActivation.activate("ads", "variáveis")

    assert captured["mastery"] == 0.65
    assert captured["difficulty_count"] == 2
    assert captured["last_evidence"] == "Entendeu parcialmente."


def test_invalid_concept_preserves_current_state(monkeypatch):
    current = {
        "current_concept_id": "ads.variables",
        "current_concept": "variáveis",
        "mastery": 0.5,
    }

    monkeypatch.setattr(
        activation_module.ConceptProgress,
        "get",
        lambda area, concept, **kwargs: None,
    )
    monkeypatch.setattr(
        activation_module.LearnerState,
        "get",
        lambda area, **kwargs: current,
    )

    assert ConceptActivation.activate("ads", "") == current
