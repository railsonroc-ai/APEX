import json
from uuid import uuid4

from backend.database import get_db_connection
from backend.identity import DEFAULT_STUDENT_ID, default_session_id, normalize_student_id
from backend.services.concept_catalog import ConceptCatalog
from backend.services.learning_history import LearningHistory
from backend.services.mastery_policy import MasteryPolicy


class MasteryAssessment:
    """Ledger imutável da decisão de domínio produzida por MasteryPolicy."""

    @classmethod
    def record(
        cls,
        *,
        turn_id,
        evidence_event_id,
        area,
        concept,
        decision,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
    ):
        normalized_student_id = normalize_student_id(student_id)
        normalized_area = LearningHistory.normalize_area(area)
        normalized_turn_id = LearningHistory.normalize_turn_id(turn_id)
        normalized_session_id = LearningHistory.normalize_session_id(session_id)
        definition = ConceptCatalog.resolve(normalized_area, concept)

        if not normalized_session_id and normalized_student_id == DEFAULT_STUDENT_ID:
            normalized_session_id = default_session_id(normalized_area)
        if not normalized_turn_id:
            raise ValueError("turn_id obrigatório para MasteryAssessment")
        if not normalized_session_id:
            raise ValueError("session_id obrigatória para MasteryAssessment")
        if not definition:
            raise ValueError("concept_id obrigatório para MasteryAssessment")
        if not isinstance(decision, dict):
            raise ValueError("decisão de mastery obrigatória")
        if decision.get("policy_id") != MasteryPolicy.POLICY_ID:
            raise ValueError("policy_id de mastery inválido")
        if decision.get("policy_version") != MasteryPolicy.POLICY_VERSION:
            raise ValueError("policy_version de mastery inválida")
        if not isinstance(evidence_event_id, str) or not evidence_event_id.strip():
            raise ValueError("evidence_event_id obrigatório")

        assessment_id = uuid4().hex
        blockers = decision.get("blockers")
        if not isinstance(blockers, list):
            blockers = []

        connection = get_db_connection()
        try:
            connection.execute(
                """
                INSERT INTO mastery_assessments (
                    assessment_id,
                    student_id,
                    session_id,
                    turn_id,
                    evidence_event_id,
                    area,
                    concept_id,
                    score,
                    can_complete,
                    applied_evidence_count,
                    demonstrated_count,
                    demonstrated_stage_count,
                    retention_demonstrated_count,
                    low_assistance_demonstrated_count,
                    latest_outcome,
                    recommended_stage,
                    blockers_json,
                    policy_id,
                    policy_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    normalized_student_id,
                    normalized_session_id,
                    normalized_turn_id,
                    evidence_event_id.strip(),
                    normalized_area,
                    definition["concept_id"],
                    float(decision.get("score", 0.0)),
                    1 if decision.get("can_complete") else 0,
                    int(decision.get("applied_evidence_count", 0)),
                    int(decision.get("demonstrated_count", 0)),
                    int(decision.get("demonstrated_stage_count", 0)),
                    int(decision.get("retention_demonstrated_count", 0)),
                    int(decision.get("low_assistance_demonstrated_count", 0)),
                    decision.get("latest_outcome"),
                    decision.get("recommended_stage"),
                    json.dumps(blockers, ensure_ascii=False, separators=(",", ":")),
                    MasteryPolicy.POLICY_ID,
                    MasteryPolicy.POLICY_VERSION,
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
        if row is None:
            return None
        result = dict(row)
        try:
            result["blockers"] = json.loads(result.get("blockers_json") or "[]")
        except (TypeError, json.JSONDecodeError):
            result["blockers"] = []
        return result

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
                FROM mastery_assessments AS assessment
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

    @classmethod
    def list_for_concept(
        cls,
        area,
        concept,
        student_id=DEFAULT_STUDENT_ID,
        limit=50,
    ):
        normalized_area = LearningHistory.normalize_area(area)
        normalized_student_id = normalize_student_id(student_id)
        definition = ConceptCatalog.resolve(normalized_area, concept)
        if not definition:
            return []
        try:
            normalized_limit = max(1, min(200, int(limit)))
        except (TypeError, ValueError):
            normalized_limit = 50

        connection = get_db_connection()
        try:
            rows = connection.execute(
                """
                SELECT
                    assessment.*,
                    definition.canonical_name AS concept
                FROM mastery_assessments AS assessment
                JOIN concept_definitions AS definition
                  ON definition.area = assessment.area
                 AND definition.concept_id = assessment.concept_id
                WHERE assessment.student_id = ?
                  AND assessment.area = ?
                  AND assessment.concept_id = ?
                ORDER BY assessment.id ASC
                LIMIT ?
                """,
                (
                    normalized_student_id,
                    normalized_area,
                    definition["concept_id"],
                    normalized_limit,
                ),
            ).fetchall()
            return [cls._row_to_dict(row) for row in rows]
        finally:
            connection.close()
