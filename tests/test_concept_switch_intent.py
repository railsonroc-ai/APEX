from backend.services.concept_tracker import ConceptTracker


def test_explicit_study_request_can_switch_active_concept():
    state = {
        "current_concept": "variáveis",
        "stage": "testar",
    }

    result = ConceptTracker.build_tracking_request(
        "Quero aprender funções",
        state,
        "ads",
    )

    assert result == {
        "area": "ads",
        "student_message": "Quero aprender funções",
    }


def test_regular_answer_does_not_trigger_concept_switch():
    state = {
        "current_concept": "variáveis",
        "stage": "testar",
    }

    result = ConceptTracker.build_tracking_request(
        "Uma variável guarda um valor.",
        state,
        "ads",
    )

    assert result is None
