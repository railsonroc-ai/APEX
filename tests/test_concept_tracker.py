from backend.services.concept_tracker import ConceptTracker


def test_preserves_current_concept():
    state = {"current_concept": "variáveis"}
    result = ConceptTracker.resolve_candidate(state, "estruturas de decisão")
    assert result == "variáveis"


def test_accepts_candidate_when_no_current_concept():
    state = {"current_concept": None}
    result = ConceptTracker.resolve_candidate(state, "  estruturas   de decisão  ")
    assert result == "estruturas de decisão"


def test_control_message_does_not_create_tracking_request():
    state = {"current_concept": None}
    result = ConceptTracker.build_tracking_request("Pode me testar?", state, "ads")
    assert result is None


def test_valid_message_creates_tracking_request():
    state = {"current_concept": None}
    result = ConceptTracker.build_tracking_request("Quero aprender variáveis", state, "ads")
    assert result == {
        "area": "ads",
        "student_message": "Quero aprender variáveis",
    }


def test_existing_concept_does_not_create_tracking_request():
    state = {"current_concept": "variáveis"}
    result = ConceptTracker.build_tracking_request("Quero aprender listas", state, "ads")
    assert result is None
