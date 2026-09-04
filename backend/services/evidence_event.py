from uuid import uuid4

from backend.database import get_db_connection
from backend.identity import DEFAULT_STUDENT_ID, default_session_id, normalize_student_id
from backend.services.concept_catalog import ConceptCatalog
from backend.services.evidence_evaluator import EvidenceEvaluator
from backend.services.evidence_policy import EvidencePolicy
from backend.services.learning_history import LearningHistory


class EvidenceEvent:
    """Ledger imutável das avaliações pedagógicas confirmadas."""

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
        concept=None,
        concept_id=None,
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
        normalized_session_id = LearningHistory.normalize_session_id(session_id)
        normalized_turn_id = LearningHistory.normalize_turn_id(turn_id)
        requested = concept_id if concept_id is not None else concept
        definition = ConceptCatalog.resolve(normalized_area, requested)

        if not normalized_session_id and normalized_student_id == DEFAULT_STUDENT_ID:
            normalized_session_id = default_session_id(normalized_area)
        if not normalized_turn_id:
            raise ValueError("turn_id obrigatório para EvidenceEvent")
        if not normalized_session_id:
            raise ValueError("session_id obrigatória para EvidenceEvent")
        if not definition:
            raise ValueError("concept_id obrigatório para EvidenceEvent")
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

        values = {
            "stage_before": cls._normalize_text(stage_before, required=True),
            "stage_after": cls._normalize_text(stage_after, required=True),
            "tutor_message": cls._normalize_text(tutor_message, required=True),
            "student_answer": cls._normalize_text(student_answer, required=True),
            "evidence_text": cls._normalize_text(semantic_evidence.get("evidence")),
            "artifact_ref": cls._normalize_text(artifact_ref),
            "source": cls._normalize_text(source, required=True),
            "assistance": EvidencePolicy.normalize_assistance_level(assistance_level),
        }

        event_id = uuid4().hex
        connection = get_db_connection()
        try:
            connection.execute(
                """
                INSERT INTO evidence_events (
                    event_id, student_id, session_id, turn_id, area, concept_id,
                    stage_before, stage_after, outcome, confidence, evidence_text,
                    tutor_message, student_answer, assistance_level, artifact_ref,
                    rubric_id, rubric_version, policy_id, policy_version, source,
                    applied, mastery_before, mastery_after
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    event_id, normalized_student_id, normalized_session_id,
                    normalized_turn_id, normalized_area, definition["concept_id"],
                    values["stage_before"], values["stage_after"], outcome, confidence,
                    values["evidence_text"], values["tutor_message"], values["student_answer"],
                    values["assistance"], values["artifact_ref"],
                    EvidencePolicy.RUBRIC_ID, EvidencePolicy.RUBRIC_VERSION,
                    EvidencePolicy.POLICY_ID, EvidencePolicy.POLICY_VERSION,
                    values["source"], 1 if applied else 0,
                    cls._normalize_mastery(mastery_before),
                    cls._normalize_mastery(mastery_after),
                ),
            )
            connection.commit()
        finally:
            connection.close()
        return cls.find(event_id, student_id=normalized_student_id)

    @staticmethod
    def _select_sql(where_clause):
        return f"""
            SELECT
                events.*,
                definition.canonical_name AS concept
            FROM evidence_events AS events
            JOIN concept_definitions AS definition
              ON definition.area = events.area
             AND definition.concept_id = events.concept_id
            {where_clause}
        """

    @classmethod
    def find(cls, event_id, student_id=DEFAULT_STUDENT_ID):
        normalized_event_id = cls._normalize_text(event_id)
        normalized_student_id = normalize_student_id(student_id)
        if not normalized_event_id:
            return None
        connection = get_db_connection()
        try:
            row = connection.execute(
                cls._select_sql("WHERE events.student_id = ? AND events.event_id = ?"),
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
                cls._select_sql("WHERE events.student_id = ? AND events.turn_id = ?"),
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
        definition = ConceptCatalog.resolve(normalized_area, concept)
        if not definition:
            return []
        try:
            normalized_limit = int(limit)
        except (TypeError, ValueError):
            normalized_limit = 50
        normalized_limit = max(1, min(200, normalized_limit))

        connection = get_db_connection()
        try:
            rows = connection.execute(
                cls._select_sql(
                    "WHERE events.student_id = ? AND events.area = ? "
                    "AND events.concept_id = ? ORDER BY events.id ASC LIMIT ?"
                ),
                (
                    normalized_student_id,
                    normalized_area,
                    definition["concept_id"],
                    normalized_limit,
                ),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()
