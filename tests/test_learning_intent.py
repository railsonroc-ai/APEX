from backend.services.concept_tracker import ConceptTracker
from backend.services.learning_intent import LearningIntent


def test_restart_from_zero_is_an_explicit_intent():
    intent = LearningIntent.detect(
        "Quero recomeçar lógica de programação do zero.", area="ads"
    )
    assert intent == {
        "kind": "restart",
        "concept_id": "ads.algorithms",
        "restart": True,
        "explicit": True,
    }


def test_regular_study_request_resolves_catalog_concept():
    intent = LearningIntent.detect("Quero aprender listas", area="ads")
    assert intent["kind"] == "study"
    assert intent["concept_id"] == "ads.lists"
    assert intent["restart"] is False


def test_negated_study_request_does_not_switch_concept():
    intent = LearningIntent.detect("Não quero aprender listas", area="ads")
    assert intent["explicit"] is False
    assert intent["concept_id"] is None


def test_history_before_latest_restart_is_discarded():
    history = [
        {"role": "user", "content": "conteúdo antigo"},
        {"role": "assistant", "content": "explicação antiga"},
        {"role": "user", "content": "Quero recomeçar lógica do zero"},
        {"role": "assistant", "content": "novo início"},
    ]
    assert LearningIntent.history_since_latest_restart(history) == [
        {"role": "assistant", "content": "novo início"},
    ]


def test_concept_tracker_prefers_deterministic_local_identity():
    assert ConceptTracker.identify_locally(
        "Quero aprender lógica de programação", area="ads"
    ) == "ads.algorithms"


def test_continue_is_an_explicit_curriculum_advance_command():
    intent = LearningIntent.detect("Continuar", area="ads")

    assert intent == {
        "kind": "advance",
        "concept_id": None,
        "restart": False,
        "explicit": False,
    }
