from uuid import uuid4

from backend.database import get_db_connection
from backend.identity import DEFAULT_STUDENT_ID, default_session_id, normalize_student_id
from backend.services.concept_catalog import ConceptCatalog
from backend.services.evidence_event import EvidenceEvent
from backend.services.learning_attempt import LearningAttempt
from backend.services.learning_history import LearningHistory
from backend.services.rubric_policy import RubricPolicy


class RubricAssessment:
    """Ledger imutável dos critérios que sustentam uma avaliação semântica."""

    @classmethod
    def record(
        cls,
        *,
        turn_id,
        attempt_id,
        evidence_event_id,
        area,
        concept_id,
        semantic_evidence,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
    ):
        normalized_student_id = normalize_student_id(student_id)
        normalized_area = LearningHistory.normalize_area(area)
        normalized_turn_id = LearningHistory.normalize_turn_id(turn_id)
        normalized_session_id = LearningHistory.normalize_session_id(session_id)

        if not normalized_session_id and normalized_student_id == DEFAULT_STUDENT_ID:
            normalized_session_id = default_session_id(normalized_area)
        if not normalized_turn_id:
            raise ValueError("turn_id obrigatório para RubricAssessment")
        if not normalized_session_id:
            raise ValueError("session_id obrigatória para RubricAssessment")
        if not isinstance(semantic_evidence, dict):
            raise ValueError("semantic_evidence obrigatória para RubricAssessment")

        definition = ConceptCatalog.resolve(normalized_area, concept_id)
        if definition is None:
            raise ValueError("concept_id inválido para RubricAssessment")

        attempt = LearningAttempt.for_turn(
            normalized_turn_id,
            student_id=normalized_student_id,
        )
        if attempt is None or attempt.get("attempt_id") != attempt_id:
            raise ValueError("tentativa confirmada não corresponde ao assessment")

        evidence = EvidenceEvent.for_turn(
            normalized_turn_id,
            student_id=normalized_student_id,
        )
        if evidence is None or evidence.get("event_id") != evidence_event_id:
            raise ValueError("evidência confirmada não corresponde ao assessment")

        if attempt.get("session_id") != normalized_session_id:
            raise ValueError("sessão da tentativa não corresponde ao assessment")
        if evidence.get("session_id") != normalized_session_id:
            raise ValueError("sessão da evidência não corresponde ao assessment")
        if attempt.get("concept_id") != definition["concept_id"]:
            raise ValueError("conceito da tentativa não corresponde ao assessment")
        if evidence.get("concept_id") != definition["concept_id"]:
            raise ValueError("conceito da evidência não corresponde ao assessment")

        normalized = RubricPolicy.normalize_payload(semantic_evidence)
        if normalized is None:
            raise ValueError("payload de rubrica inválido")

        try:
            confidence = float(semantic_evidence.get("confidence"))
        except (TypeError, ValueError) as exc:
            raise ValueError("confidence inválida para RubricAssessment") from exc
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence inválida para RubricAssessment")

        criteria = normalized["criteria"]
        assessment_id = uuid4().hex

        connection = get_db_connection()
        try:
            connection.execute(
                """
                INSERT INTO rubric_assessments (
                    assessment_id,
                    student_id,
                    session_id,
                    turn_id,
                    attempt_id,
                    evidence_event_id,
                    area,
                    concept_id,
                    task_response,
                    conceptual_correctness,
                    understanding_application,
                    criteria_complete,
                    outcome,
                    outcome_source,
                    confidence,
                    rubric_id,
                    rubric_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    normalized_student_id,
                    normalized_session_id,
                    normalized_turn_id,
                    attempt_id,
                    evidence_event_id,
                    normalized_area,
                    definition["concept_id"],
                    criteria[RubricPolicy.TASK_RESPONSE],
                    criteria[RubricPolicy.CONCEPTUAL_CORRECTNESS],
                    criteria[RubricPolicy.UNDERSTANDING_APPLICATION],
                    int(normalized["rubric_complete"]),
                    normalized["outcome"],
                    normalized["outcome_source"],
                    confidence,
                    RubricPolicy.RUBRIC_ID,
                    RubricPolicy.RUBRIC_VERSION,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        return cls.for_turn(
            normalized_turn_id,
            student_id=normalized_student_id,
        )

    @staticmethod
    def _row_to_dict(row):
        return dict(row) if row is not None else None

    @classmethod
    def for_turn(cls, turn_id, student_id=DEFAULT_STUDENT_ID):
        normalized_turn_id = LearningHistory.normalize_turn_id(turn_id)
        normalized_student_id = normalize_student_id(student_id)
        if not normalized_turn_id:
            return None

        connection = get_db_connection()
        try:
            row = connection.execute(
                """
                SELECT
                    assessment.*,
                    definition.canonical_name AS concept
                FROM rubric_assessments AS assessment
                JOIN concept_definitions AS definition
                  ON definition.area = assessment.area
                 AND definition.concept_id = assessment.concept_id
                WHERE assessment.student_id = ?
                  AND assessment.turn_id = ?
                """,
                (normalized_student_id, normalized_turn_id),
            ).fetchone()
            return cls._row_to_dict(row)
        finally:
            connection.close()
