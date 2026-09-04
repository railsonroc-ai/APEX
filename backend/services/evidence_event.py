from uuid import uuid4

from backend.database import get_db_connection
from backend.identity import (
    DEFAULT_STUDENT_ID,
    default_session_id,
    normalize_student_id,
)
from backend.services.evidence_evaluator import EvidenceEvaluator
from backend.services.evidence_policy import EvidencePolicy
from backend.services.learning_history import LearningHistory


class EvidenceEvent:
    """Ledger imutável das avaliações pedagógicas confirmadas.

    Um evento só é gravado dentro do commit autoritativo de um turno. O
    banco bloqueia UPDATE e DELETE para que a trilha de evidência permaneça
    auditável. Uma avaliação parseada, porém abaixo do limiar de confiança,
    também pode ser registrada com ``applied = 0``.
    """

    MAX_TEXT_CHARS = 4000

    @staticmethod
    def _normalize_text(value, required=False):
        if value is None:
            if required:
                raise ValueError("texto obrigatório")
            return None

        normalized = str(value).strip()

        if not normalized:
            if required:
                raise ValueError("texto obrigatório")
            return None

        if len(normalized) > EvidenceEvent.MAX_TEXT_CHARS:
            raise ValueError("texto de evidência muito longo")

        return normalized

    @staticmethod
    def _normalize_mastery(value):
        try:
            normalized = float(value)
        except (TypeError, ValueError):
            normalized = 0.0

        return min(1.0, max(0.0, normalized))

    @classmethod
    def record(
        cls,
        *,
        turn_id,
        area,
        concept,
        stage_before,
        stage_after,
        semantic_evidence,
        tutor_message,
        student_answer,
        mastery_before,
        mastery_after,
        applied,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
        assistance_level=EvidencePolicy.ASSISTANCE_UNTRACKED,
        artifact_ref=None,
        source=EvidencePolicy.SOURCE_SEMANTIC_LLM,
    ):
        normalized_student_id = normalize_student_id(student_id)
        normalized_area = LearningHistory.normalize_area(area)
        normalized_session_id = LearningHistory.normalize_session_id(
            session_id
        )
        normalized_turn_id = LearningHistory.normalize_turn_id(turn_id)
        normalized_concept = LearningHistory.normalize_concept(concept)

        if (
            not normalized_session_id
            and normalized_student_id == DEFAULT_STUDENT_ID
        ):
            normalized_session_id = default_session_id(normalized_area)

        if not normalized_turn_id:
            raise ValueError("turn_id obrigatório para EvidenceEvent")
        if not normalized_session_id:
            raise ValueError("session_id obrigatória para EvidenceEvent")
        if not normalized_concept:
            raise ValueError("concept obrigatório para EvidenceEvent")
        if not isinstance(semantic_evidence, dict):
            raise ValueError("semantic_evidence obrigatória")

        outcome = semantic_evidence.get("outcome")
        if outcome not in EvidenceEvaluator.VALID_OUTCOMES:
            raise ValueError("outcome de evidência inválido")

        try:
            confidence = float(semantic_evidence.get("confidence"))
        except (TypeError, ValueError) as exc:
            raise ValueError("confidence de evidência inválida") from exc

        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence de evidência inválida")

        normalized_stage_before = cls._normalize_text(
            stage_before,
            required=True,
        )
        normalized_stage_after = cls._normalize_text(
            stage_after,
            required=True,
        )
        normalized_tutor_message = cls._normalize_text(
            tutor_message,
            required=True,
        )
        normalized_student_answer = cls._normalize_text(
            student_answer,
            required=True,
        )
        normalized_evidence_text = cls._normalize_text(
            semantic_evidence.get("evidence")
        )
        normalized_artifact_ref = cls._normalize_text(artifact_ref)
        normalized_source = cls._normalize_text(source, required=True)
        normalized_assistance = EvidencePolicy.normalize_assistance_level(
            assistance_level
        )

        event_id = uuid4().hex
        connection = get_db_connection()

        try:
            connection.execute(
                """
                INSERT INTO evidence_events (
                    event_id,
                    student_id,
                    session_id,
                    turn_id,
                    area,
                    concept,
                    stage_before,
                    stage_after,
                    outcome,
                    confidence,
                    evidence_text,
                    tutor_message,
                    student_answer,
                    assistance_level,
                    artifact_ref,
                    rubric_id,
                    rubric_version,
                    policy_id,
                    policy_version,
                    source,
                    applied,
                    mastery_before,
                    mastery_after
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    event_id,
                    normalized_student_id,
                    normalized_session_id,
                    normalized_turn_id,
                    normalized_area,
                    normalized_concept,
                    normalized_stage_before,
                    normalized_stage_after,
                    outcome,
                    confidence,
                    normalized_evidence_text,
                    normalized_tutor_message,
                    normalized_student_answer,
                    normalized_assistance,
                    normalized_artifact_ref,
                    EvidencePolicy.RUBRIC_ID,
                    EvidencePolicy.RUBRIC_VERSION,
                    EvidencePolicy.POLICY_ID,
                    EvidencePolicy.POLICY_VERSION,
                    normalized_source,
                    1 if applied else 0,
                    cls._normalize_mastery(mastery_before),
                    cls._normalize_mastery(mastery_after),
                ),
            )
            connection.commit()
        finally:
            connection.close()

        return cls.find(event_id, student_id=normalized_student_id)

    @classmethod
    def find(cls, event_id, student_id=DEFAULT_STUDENT_ID):
        normalized_event_id = cls._normalize_text(event_id)
        normalized_student_id = normalize_student_id(student_id)

        if not normalized_event_id:
            return None

        connection = get_db_connection()
        try:
            row = connection.execute(
                """
                SELECT *
                FROM evidence_events
                WHERE student_id = ?
                  AND event_id = ?
                """,
                (normalized_student_id, normalized_event_id),
            ).fetchone()
            return dict(row) if row is not None else None
        finally:
            connection.close()

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
                SELECT *
                FROM evidence_events
                WHERE student_id = ?
                  AND turn_id = ?
                """,
                (normalized_student_id, normalized_turn_id),
            ).fetchone()
            return dict(row) if row is not None else None
        finally:
            connection.close()

    @classmethod
    def list_for_concept(
        cls,
        area,
        concept,
        student_id=DEFAULT_STUDENT_ID,
        limit=50,
    ):
        normalized_student_id = normalize_student_id(student_id)
        normalized_area = LearningHistory.normalize_area(area)
        normalized_concept = LearningHistory.normalize_concept(concept)

        if not normalized_concept:
            return []

        try:
            normalized_limit = int(limit)
        except (TypeError, ValueError):
            normalized_limit = 50

        normalized_limit = max(1, min(200, normalized_limit))

        connection = get_db_connection()
        try:
            rows = connection.execute(
                """
                SELECT *
                FROM evidence_events
                WHERE student_id = ?
                  AND area = ?
                  AND concept = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (
                    normalized_student_id,
                    normalized_area,
                    normalized_concept,
                    normalized_limit,
                ),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()
