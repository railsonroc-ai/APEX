import sqlite3

import pytest

import backend.database as database_module
import backend.services.process_learning_turn as turn_module
from backend.services.assistance_event import AssistanceEvent
from backend.services.assistance_policy import AssistancePolicy
from backend.services.evidence_event import EvidenceEvent
from backend.services.learning_history import LearningHistory
from backend.services.process_learning_turn import ProcessLearningTurn


def prepare_database(monkeypatch, tmp_path, name="assistance.db"):
    path = tmp_path / name
    monkeypatch.setattr(database_module, "DATABASE_PATH", path)
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    return path


def record_turn(turn_id, assistant_message, *, concept="variáveis"):
    LearningHistory.record(
        turn_id=turn_id,
        area="ads",
        user_message="Mensagem do aluno",
        assistant_message=assistant_message,
        concept=concept,
    )


def test_assistance_event_is_server_derived_and_immutable(monkeypatch, tmp_path):
    path = prepare_database(monkeypatch, tmp_path)
    record_turn("assist-1", "Agora responda sem dica.")

    event = AssistanceEvent.record(
        turn_id="assist-1",
        area="ads",
        concept="variáveis",
        teaching_action="testar",
    )

    assert event["concept_id"] == "ads.variables"
    assert event["teaching_action"] == "testar"
    assert event["assistance_level"] == "independent"
    assert event["policy_id"] == AssistancePolicy.POLICY_ID
    assert event["policy_version"] == AssistancePolicy.POLICY_VERSION

    connection = sqlite3.connect(str(path))
    try:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE assistance_events SET assistance_level='direct' WHERE assistance_id=?",
                (event["assistance_id"],),
            )
        connection.rollback()

        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "DELETE FROM assistance_events WHERE assistance_id=?",
                (event["assistance_id"],),
            )
    finally:
        connection.close()


def test_evidence_resolves_assistance_from_exact_previous_tutor_turn(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)
    tutor_message = "Explique com suas palavras o que é uma variável."
    record_turn("assist-source", tutor_message)
    AssistanceEvent.record(
        turn_id="assist-source",
        area="ads",
        concept="variáveis",
        teaching_action="explicar",
    )

    level = AssistanceEvent.resolve_for_evidence(
        area="ads",
        evidence_context={
            "concept_id": "ads.variables",
            "tutor_message": tutor_message,
        },
    )
    wrong_message = AssistanceEvent.resolve_for_evidence(
        area="ads",
        evidence_context={
            "concept_id": "ads.variables",
            "tutor_message": "Outra mensagem",
        },
    )

    assert level == "guided"
    assert wrong_message == "untracked"


def test_legacy_turn_without_assistance_ledger_remains_untracked(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)
    tutor_message = "Responda a pergunta antiga."
    record_turn("legacy-turn", tutor_message)

    assert AssistanceEvent.resolve_for_evidence(
        area="ads",
        evidence_context={
            "concept_id": "ads.variables",
            "tutor_message": tutor_message,
        },
    ) == "untracked"


def test_process_uses_previous_server_assistance_for_evidence(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)

    first = ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Quero estudar variáveis.",
        identified_concept="variáveis",
        semantic_evidence=None,
        turn_id="turn-assist-first",
        assistant_message="Explique com suas palavras o que é uma variável.",
    )
    assert first["teaching_action"] == "explicar"
    source = AssistanceEvent.for_turn("turn-assist-first")
    assert source["assistance_level"] == "guided"

    ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Uma variável associa um nome a um valor.",
        identified_concept=None,
        semantic_evidence={
            "outcome": "demonstrated",
            "confidence": 0.95,
            "evidence": "Definição correta.",
        },
        turn_id="turn-assist-answer",
        assistant_message="Agora aplique isso em um pequeno exemplo.",
        evidence_context={
            "concept_id": "ads.variables",
            "concept": "variáveis",
            "stage": "compreender",
            "tutor_message": "Explique com suas palavras o que é uma variável.",
            "student_answer": "Uma variável associa um nome a um valor.",
        },
    )

    evidence = EvidenceEvent.for_turn("turn-assist-answer")
    assert evidence["assistance_level"] == "guided"


def test_assistance_ledger_failure_rolls_back_confirmed_turn(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)

    def fail(*args, **kwargs):
        raise RuntimeError("falha simulada no assistance ledger")

    monkeypatch.setattr(turn_module.AssistanceEvent, "record", fail)

    with pytest.raises(RuntimeError, match="assistance ledger"):
        ProcessLearningTurn.commit_turn(
            area="ads",
            user_message="Quero estudar variáveis.",
            identified_concept="variáveis",
            semantic_evidence=None,
            turn_id="assist-rollback",
            assistant_message="Explique variáveis.",
        )

    assert LearningHistory.find("assist-rollback") is None


def test_mismatched_teaching_action_rolls_back_instead_of_spoofing_level(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="teaching_action"):
        ProcessLearningTurn.commit_turn(
            area="ads",
            user_message="Quero estudar variáveis.",
            identified_concept="variáveis",
            semantic_evidence=None,
            turn_id="assist-spoof",
            assistant_message="Explique variáveis.",
            teaching_action="testar",
        )

    assert LearningHistory.find("assist-spoof") is None


def test_source_turn_id_disambiguates_repeated_tutor_messages(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)
    tutor_message = "Responda sem olhar a resposta."

    for turn_id, action in (("repeat-1", "explicar"), ("repeat-2", "testar")):
        record_turn(turn_id, tutor_message)
        AssistanceEvent.record(
            turn_id=turn_id,
            area="ads",
            concept="variáveis",
            teaching_action=action,
        )

    level = AssistanceEvent.resolve_for_evidence(
        area="ads",
        evidence_context={
            "concept_id": "ads.variables",
            "source_turn_id": "repeat-1",
            "tutor_message": tutor_message,
        },
    )

    assert level == "guided"


def test_long_tutor_message_uses_confirmed_turn_identity(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)
    full_message = "x" * 4500
    record_turn("long-assist", full_message)
    AssistanceEvent.record(
        turn_id="long-assist",
        area="ads",
        concept="variáveis",
        teaching_action="testar",
    )

    level = AssistanceEvent.resolve_for_evidence(
        area="ads",
        evidence_context={
            "concept_id": "ads.variables",
            "source_turn_id": "long-assist",
            "tutor_message": full_message[:4000],
        },
    )

    assert level == "independent"
