from backend.services.concept_activation import ConceptActivation
from backend.services.process_learning_turn import ProcessLearningTurn


def test_identified_concept_reaches_activation_during_switch(
    monkeypatch,
):
    state = {
        "current_concept": "variáveis",
        "stage": "testar",
        "mastery": 0.6,
        "difficulty": 0,
        "evidence_count": 3,
    }

    captured = {}

    def fake_activate(area, concept):
        captured["area"] = area
        captured["concept"] = concept

        return {
            **state,
            "current_concept": concept,
            "stage": "compreender",
            "mastery": 0.0,
        }

    monkeypatch.setattr(
        ConceptActivation,
        "activate",
        fake_activate,
    )

    result = (
        ProcessLearningTurn
        .activate_identified_concept(
            "ads",
            state,
            "funções",
        )
    )

    assert captured == {
        "area": "ads",
        "concept": "funções",
    }

    assert (
        result["current_concept"]
        == "funções"
    )
