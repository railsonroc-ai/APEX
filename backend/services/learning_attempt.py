from uuid import uuid4

from backend.database import get_db_connection
from backend.identity import DEFAULT_STUDENT_ID, default_session_id, normalize_student_id
from backend.services.attempt_policy import AttemptPolicy
from backend.services.concept_catalog import ConceptCatalog
from backend.services.evidence_policy import EvidencePolicy
from backend.services.learning_history import LearningHistory
from backend.services.learning_task import LearningTask


class LearningAttempt:
    """Ledger imutável da ação do aluno antes de qualquer julgamento semântico."""

    MAX_TEXT_CHARS = 4000

    @staticmethod
    def _normalize_optional_text(value):
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        if len(normalized) > LearningAttempt.MAX_TEXT_CHARS:
            raise ValueError("texto de tentativa muito longo")
        return normalized

    @classmethod
    def record(
        cls,
        *,
        turn_id,
        area,
        concept_id,
        stage,
        student_answer,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
        source_turn_id=None,
        task_id=None,
        assistance_level=EvidencePolicy.ASSISTANCE_UNTRACKED,
        artifact_ref=None,
    ):
        normalized_student_id = normalize_student_id(student_id)
        normalized_area = LearningHistory.normalize_area(area)
        normalized_turn_id = LearningHistory.normalize_turn_id(turn_id)
        normalized_session_id = LearningHistory.normalize_session_id(session_id)
        normalized_source_turn_id = LearningHistory.normalize_turn_id(source_turn_id)
        normalized_answer = LearningHistory.normalize_message(student_answer)
        normalized_task_id = task_id.strip() if isinstance(task_id, str) else None

        if not normalized_session_id and normalized_student_id == DEFAULT_STUDENT_ID:
            normalized_session_id = default_session_id(normalized_area)
        if not normalized_turn_id:
            raise ValueError("turn_id obrigatório para LearningAttempt")
        if not normalized_session_id:
            raise ValueError("session_id obrigatória para LearningAttempt")
        if not normalized_answer:
            raise ValueError("student_answer obrigatória para LearningAttempt")

        definition = ConceptCatalog.resolve(normalized_area, concept_id)
        if definition is None:
            raise ValueError("concept_id inválido para LearningAttempt")

        attempt_kind = AttemptPolicy.kind_for_stage(stage)
        if attempt_kind is None:
            raise ValueError("stage não representa tentativa avaliável")

        turn = LearningHistory.find(
            normalized_turn_id,
            student_id=normalized_student_id,
        )
        if turn is None:
            raise ValueError("turno confirmado não encontrado")
        if turn.get("area") != normalized_area:
            raise ValueError("área não corresponde ao turno confirmado")
        if turn.get("session_id") != normalized_session_id:
            raise ValueError("sessão não corresponde ao turno confirmado")
        if turn.get("concept_id") != definition["concept_id"]:
            raise ValueError("conceito não corresponde ao turno confirmado")
        if turn.get("user_message") != normalized_answer:
            raise ValueError("resposta não corresponde ao turno confirmado")

        if normalized_source_turn_id:
            source_turn = LearningHistory.find(
                normalized_source_turn_id,
                student_id=normalized_student_id,
            )
            if source_turn is None:
                raise ValueError("source_turn_id não encontrado")
            if source_turn.get("area") != normalized_area:
                raise ValueError("source_turn_id pertence a outra área")
            if source_turn.get("session_id") != normalized_session_id:
                raise ValueError("source_turn_id pertence a outra sessão")
            if source_turn.get("concept_id") != definition["concept_id"]:
                raise ValueError("source_turn_id pertence a outro conceito")
            if not source_turn.get("assistant_message"):
                raise ValueError("source_turn_id não possui resposta do tutor")

        if normalized_task_id:
            task = LearningTask.find(
                normalized_task_id,
                student_id=normalized_student_id,
            )
            if task is None:
                raise ValueError("task_id não encontrado")
            if task.get("session_id") != normalized_session_id:
                raise ValueError("task_id pertence a outra sessão")
            if task.get("area") != normalized_area:
                raise ValueError("task_id pertence a outra área")
            if task.get("concept_id") != definition["concept_id"]:
                raise ValueError("task_id pertence a outro conceito")
            if task.get("source_turn_id") != normalized_source_turn_id:
                raise ValueError("task_id não corresponde ao turno fonte")

        normalized_artifact_ref = cls._normalize_optional_text(artifact_ref)
        normalized_assistance = EvidencePolicy.normalize_assistance_level(
            assistance_level
        )
        attempt_id = uuid4().hex

        connection = get_db_connection()
        try:
            connection.execute(
                """
                INSERT INTO learning_attempts (
                    attempt_id,
                    student_id,
                    session_id,
                    turn_id,
                    source_turn_id,
                    task_id,
                    area,
                    concept_id,
                    stage,
                    attempt_kind,
                    student_answer,
                    artifact_ref,
                    assistance_level,
                    policy_id,
                    policy_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    normalized_student_id,
                    normalized_session_id,
                    normalized_turn_id,
                    normalized_source_turn_id,
                    normalized_task_id,
                    normalized_area,
                    definition["concept_id"],
                    stage,
                    attempt_kind,
                    normalized_answer,
                    normalized_artifact_ref,
                    normalized_assistance,
                    AttemptPolicy.POLICY_ID,
                    AttemptPolicy.POLICY_VERSION,
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
                    attempt.*,
                    definition.canonical_name AS concept
                FROM learning_attempts AS attempt
                JOIN concept_definitions AS definition
                  ON definition.area = attempt.area
                 AND definition.concept_id = attempt.concept_id
                WHERE attempt.student_id = ?
                  AND attempt.turn_id = ?
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
        concept_id,
        *,
        student_id=DEFAULT_STUDENT_ID,
        limit=200,
    ):
        normalized_area = LearningHistory.normalize_area(area)
        normalized_student_id = normalize_student_id(student_id)
        definition = ConceptCatalog.resolve(normalized_area, concept_id)
        if definition is None:
            return []
        try:
            normalized_limit = min(500, max(1, int(limit)))
        except (TypeError, ValueError):
            normalized_limit = 200

        connection = get_db_connection()
        try:
            rows = connection.execute(
                """
                SELECT *
                FROM learning_attempts
                WHERE student_id = ?
                  AND area = ?
                  AND concept_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
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
