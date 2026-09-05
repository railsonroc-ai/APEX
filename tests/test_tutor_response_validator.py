from backend.services.turn_teaching_contract import TurnTeachingContract
from backend.services.tutor_response_validator import TutorResponseValidator


def ordered_contract(action="explicar", review=False):
    return TurnTeachingContract.build(
        {
            "area": "ads",
            "current_concept_id": "ads.algorithms.ordered_steps",
            "current_concept": "sequência ordenada de passos",
        },
        action,
        review_mode=review,
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


def test_validated_chunks_reconstruct_exact_response():
    response = "x" * 401
    chunks = TutorResponseValidator.chunks(response, size=180)
    assert "".join(chunks) == response
    assert [len(chunk) for chunk in chunks] == [180, 180, 41]
