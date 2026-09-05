from backend.services.turn_teaching_contract import TurnTeachingContract
from backend.services.tutor_response_validator import TutorResponseValidator
import pytest


def ordered_contract(
    action="explicar",
    review=False,
    evidence_outcome=None,
    difficulty_count=0,
):
    return TurnTeachingContract.build(
        {
            "area": "ads",
            "current_concept_id": "ads.algorithms.ordered_steps",
            "current_concept": "sequência ordenada de passos",
            "difficulty_count": difficulty_count,
        },
        action,
        review_mode=review,
        evidence_outcome=evidence_outcome,
    )


def test_forbidden_novelty_is_replaced_before_delivery():
    result = TutorResponseValidator.validate_or_fallback(
        "Agora use uma variável em Python. Tarefa: escreva o código.",
        ordered_contract(),
    )
    assert result["fallback_used"] is True
    assert "variável" not in result["response"].lower()
    assert "python" not in result["response"].lower()


def test_deterministic_ordered_steps_response_satisfies_contract():
    contract = ordered_contract()
    result = TutorResponseValidator.validate(contract.safe_response, contract)
    assert result["valid"] is True
    assert result["assistance_level"] == "guided"


def test_exactly_one_task_is_required():
    result = TutorResponseValidator.validate(
        "Tarefa: faça A.\n\nTarefa: faça B.", ordered_contract("testar")
    )
    assert result["valid"] is False
    assert "task_count" in result["errors"]


def test_assistance_above_ceiling_is_rejected():
    result = TutorResponseValidator.validate(
        "A resposta é esta. Tarefa: repita a resposta.",
        ordered_contract("testar"),
    )
    assert "assistance_above_ceiling" in result["errors"]


def test_review_must_retrieve_before_teaching():
    result = TutorResponseValidator.validate(
        "Primeiro vou explicar detalhadamente o conteúdo estudado. "
        "Tarefa: recorde o que aprendeu.",
        ordered_contract("revisar", review=True),
    )
    assert "review_teaches_before_retrieval" in result["errors"]


def test_review_action_enables_review_contract_without_session_flag():
    contract = ordered_contract("revisar", review=False)

    assert contract.review_mode is True
    assert contract.safe_response.startswith("Tarefa: de memória")
    assert TutorResponseValidator.validate(contract.safe_response, contract)["valid"]


def test_validated_chunks_reconstruct_exact_response():
    response = "x" * 401
    chunks = TutorResponseValidator.chunks(response, size=180)
    assert "".join(chunks) == response
    assert [len(chunk) for chunk in chunks] == [180, 180, 41]


def test_confirmed_evidence_requires_explicit_feedback_before_next_task():
    contract = ordered_contract(
        "consolidar",
        evidence_outcome="demonstrated",
    )
    without_feedback = TutorResponseValidator.validate(
        "Tarefa: descreva três passos em ordem.",
        contract,
    )
    result = TutorResponseValidator.validate_or_fallback(
        "Tarefa: descreva três passos em ordem.",
        contract,
    )

    assert "feedback_missing" in without_feedback["errors"]
    assert result["fallback_used"] is False
    assert result["feedback_prepended"] is True
    assert result["response"].startswith("Correto.\n\nTarefa:")


def test_feedback_repair_preserves_valid_tutor_content():
    contract = ordered_contract(
        "consolidar",
        evidence_outcome="demonstrated",
    )
    original = "Tarefa: descreva como organizar uma mochila em três passos."

    result = TutorResponseValidator.validate_or_fallback(original, contract)

    assert result["response"] == f"Correto.\n\n{original}"
    assert result["fallback_used"] is False


def test_conflicting_feedback_is_not_silently_prefixed():
    contract = ordered_contract(
        "consolidar",
        evidence_outcome="demonstrated",
    )

    result = TutorResponseValidator.validate_or_fallback(
        "Ainda não está correto.\n\nTarefa: descreva três passos.",
        contract,
    )

    assert result["fallback_used"] is True
    assert result["response"].startswith("Correto.")
    assert "Ainda não está correto" not in result["response"]


def test_every_ordered_steps_fallback_validates_for_its_action():
    for action in (
        "explicar", "testar", "corrigir", "consolidar", "revisar",
    ):
        contract = ordered_contract(action, review=(action == "revisar"))
        result = TutorResponseValidator.validate(contract.safe_response, contract)
        assert result["valid"] is True, (action, result["errors"])


def test_correction_fallback_is_recorded_as_direct_assistance():
    contract = ordered_contract("corrigir", difficulty_count=2)
    result = TutorResponseValidator.validate(contract.safe_response, contract)

    assert result["assistance_level"] == "direct"


def test_first_correction_uses_guidance_without_revealing_full_order():
    contract = ordered_contract("corrigir", difficulty_count=1)
    result = TutorResponseValidator.validate(contract.safe_response, contract)

    assert contract.assistance_ceiling == "guided"
    assert result["valid"] is True
    assert result["assistance_level"] == "guided"
    assert "a ordem é abrir" not in contract.safe_response.lower()


@pytest.mark.parametrize(
    ("outcome", "feedback"),
    tuple(TurnTeachingContract.FEEDBACK_BY_OUTCOME.items()),
)
def test_every_feedback_outcome_is_enforced(outcome, feedback):
    contract = ordered_contract("consolidar", evidence_outcome=outcome)
    result = TutorResponseValidator.validate_or_fallback(
        "Tarefa: descreva três passos em ordem.",
        contract,
    )

    assert result["response"].startswith(feedback + "\n\n")
