from uuid import uuid4

from backend.database import get_db_connection, transaction
from backend.identity import DEFAULT_STUDENT_ID, default_session_id, normalize_student_id
from backend.services.evidence_evaluator import EvidenceEvaluator
from backend.services.learner_state import LearnerState
from backend.services.learning_history import LearningHistory


class SessionLifecycleError(ValueError):
    pass


class LearningSessionLifecycle:
    """State machine persistente para pausar e retomar estudo.

    O estado operacional fica em ``learning_session_states`` e cada transição
    confirmada gera um evento imutável em ``learning_session_events``.
    """

    POLICY_ID = "learning_session_lifecycle"
    POLICY_VERSION = 1

    STUDYING = "studying"
    PAUSED = "paused"
    REVIEWING = "reviewing"

    DIRECT = "direct"
    REVIEW = "review"

    VALID_STATUSES = {STUDYING, PAUSED, REVIEWING}
    VALID_RESUME_MODES = {DIRECT, REVIEW}

    EVENT_PAUSED = "paused"
    EVENT_RESUMED_DIRECT = "resumed_direct"
    EVENT_RESUME_REVIEW_STARTED = "resume_review_started"
    EVENT_RESUME_REVIEW_COMPLETED = "resume_review_completed"

    @classmethod
    def _normalize_context(
        cls,
        area,
        *,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
    ):
        normalized_area = LearnerState.normalize_area(area)
        normalized_student_id = normalize_student_id(student_id)
        normalized_session_id = LearningHistory.normalize_session_id(session_id)

        if not normalized_session_id and normalized_student_id == DEFAULT_STUDENT_ID:
            normalized_session_id = default_session_id(normalized_area)

        if not normalized_session_id:
            raise SessionLifecycleError("session_id obrigatória")

        return normalized_area, normalized_student_id, normalized_session_id

    @classmethod
    def _ensure_state(cls, connection, *, area, student_id, session_id):
        session = connection.execute(
            """
            SELECT id
            FROM learning_sessions
            WHERE student_id = ?
              AND id = ?
              AND area = ?
            """,
            (student_id, session_id, area),
        ).fetchone()

        if session is None:
            raise SessionLifecycleError("sessão de aprendizagem não encontrada")

        connection.execute(
            """
            INSERT OR IGNORE INTO learning_session_states (
                student_id,
                session_id,
                area,
                status
            )
            VALUES (?, ?, ?, 'studying')
            """,
            (student_id, session_id, area),
        )

    @classmethod
    def _read_state(cls, connection, *, area, student_id, session_id):
        row = connection.execute(
            """
            SELECT
                state.student_id,
                state.session_id,
                state.area,
                state.status,
                state.resume_concept_id,
                definition.canonical_name AS resume_concept,
                state.resume_stage,
                state.review_task_id,
                state.paused_at,
                state.last_resumed_at,
                state.updated_at
            FROM learning_session_states AS state
            LEFT JOIN concept_definitions AS definition
              ON definition.area = state.area
             AND definition.concept_id = state.resume_concept_id
            WHERE state.student_id = ?
              AND state.session_id = ?
              AND state.area = ?
            """,
            (student_id, session_id, area),
        ).fetchone()
        return dict(row) if row is not None else None

    @classmethod
    def get(
        cls,
        area="ads",
        *,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
    ):
        area, student_id, session_id = cls._normalize_context(
            area,
            student_id=student_id,
            session_id=session_id,
        )

        connection = get_db_connection()
        try:
            cls._ensure_state(
                connection,
                area=area,
                student_id=student_id,
                session_id=session_id,
            )
            connection.commit()
            return cls._read_state(
                connection,
                area=area,
                student_id=student_id,
                session_id=session_id,
            )
        finally:
            connection.close()

    @classmethod
    def _record_event(
        cls,
        connection,
        *,
        student_id,
        session_id,
        area,
        event_type,
        status_before,
        status_after,
        concept_id=None,
        stage_snapshot=None,
    ):
        event_id = f"session_event_{uuid4().hex}"
        connection.execute(
            """
            INSERT INTO learning_session_events (
                event_id,
                student_id,
                session_id,
                area,
                event_type,
                status_before,
                status_after,
                concept_id,
                stage_snapshot,
                policy_id,
                policy_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                student_id,
                session_id,
                area,
                event_type,
                status_before,
                status_after,
                concept_id,
                stage_snapshot,
                cls.POLICY_ID,
                cls.POLICY_VERSION,
            ),
        )
        return event_id

    @classmethod
    def pause(
        cls,
        area="ads",
        *,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
    ):
        area, student_id, session_id = cls._normalize_context(
            area,
            student_id=student_id,
            session_id=session_id,
        )

        with transaction() as connection:
            cls._ensure_state(
                connection,
                area=area,
                student_id=student_id,
                session_id=session_id,
            )
            runtime = cls._read_state(
                connection,
                area=area,
                student_id=student_id,
                session_id=session_id,
            )

            if runtime["status"] == cls.PAUSED:
                return {**runtime, "duplicate": True}

            if runtime["status"] == cls.REVIEWING:
                raise SessionLifecycleError(
                    "Não é possível pausar durante a revisão de retomada."
                )

            learner_state = LearnerState.get(area, student_id=student_id)
            if learner_state.get("stage") == "reencontrar":
                raise SessionLifecycleError(
                    "Conclua a revisão em andamento antes de pausar."
                )

            concept_id = learner_state.get("current_concept_id")
            stage = learner_state.get("stage") or "compreender"

            connection.execute(
                """
                UPDATE learning_session_states
                SET status = 'paused',
                    resume_concept_id = ?,
                    resume_stage = ?,
                    paused_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE student_id = ?
                  AND session_id = ?
                  AND area = ?
                """,
                (concept_id, stage, student_id, session_id, area),
            )

            cls._record_event(
                connection,
                student_id=student_id,
                session_id=session_id,
                area=area,
                event_type=cls.EVENT_PAUSED,
                status_before=cls.STUDYING,
                status_after=cls.PAUSED,
                concept_id=concept_id,
                stage_snapshot=stage,
            )

            updated = cls._read_state(
                connection,
                area=area,
                student_id=student_id,
                session_id=session_id,
            )
            return {**updated, "duplicate": False}

    @classmethod
    def resume(
        cls,
        area="ads",
        *,
        mode=DIRECT,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
    ):
        area, student_id, session_id = cls._normalize_context(
            area,
            student_id=student_id,
            session_id=session_id,
        )
        normalized_mode = str(mode or "").strip().lower()
        if normalized_mode not in cls.VALID_RESUME_MODES:
            raise SessionLifecycleError("modo de retomada inválido")

        with transaction() as connection:
            cls._ensure_state(
                connection,
                area=area,
                student_id=student_id,
                session_id=session_id,
            )
            runtime = cls._read_state(
                connection,
                area=area,
                student_id=student_id,
                session_id=session_id,
            )

            if runtime["status"] == cls.STUDYING:
                if normalized_mode == cls.DIRECT:
                    return {**runtime, "duplicate": True}
                raise SessionLifecycleError("sessão não está pausada")

            if runtime["status"] == cls.REVIEWING:
                if normalized_mode == cls.REVIEW:
                    return {**runtime, "duplicate": True}
                raise SessionLifecycleError(
                    "revisão de retomada já está em andamento"
                )

            concept_id = runtime.get("resume_concept_id")
            stage = runtime.get("resume_stage") or "compreender"

            if normalized_mode == cls.DIRECT:
                connection.execute(
                    """
                    UPDATE learning_session_states
                    SET status = 'studying',
                        resume_concept_id = NULL,
                        resume_stage = NULL,
                        review_task_id = NULL,
                        paused_at = NULL,
                        last_resumed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE student_id = ?
                      AND session_id = ?
                      AND area = ?
                    """,
                    (student_id, session_id, area),
                )
                event_type = cls.EVENT_RESUMED_DIRECT
                status_after = cls.STUDYING
            else:
                if not concept_id:
                    raise SessionLifecycleError(
                        "não há conceito ativo para revisar antes da retomada"
                    )

                LearnerState.update(
                    area,
                    current_concept_id=concept_id,
                    stage="reencontrar",
                    student_id=student_id,
                )
                connection.execute(
                    """
                    UPDATE learning_session_states
                    SET status = 'reviewing',
                        review_task_id = NULL,
                        paused_at = NULL,
                        last_resumed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE student_id = ?
                      AND session_id = ?
                      AND area = ?
                    """,
                    (student_id, session_id, area),
                )
                event_type = cls.EVENT_RESUME_REVIEW_STARTED
                status_after = cls.REVIEWING

            cls._record_event(
                connection,
                student_id=student_id,
                session_id=session_id,
                area=area,
                event_type=event_type,
                status_before=cls.PAUSED,
                status_after=status_after,
                concept_id=concept_id,
                stage_snapshot=stage,
            )

            updated = cls._read_state(
                connection,
                area=area,
                student_id=student_id,
                session_id=session_id,
            )
            return {**updated, "duplicate": False}

    @classmethod
    def bind_review_task(
        cls,
        task_id,
        area="ads",
        *,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
    ):
        area, student_id, session_id = cls._normalize_context(
            area,
            student_id=student_id,
            session_id=session_id,
        )
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return None

        with transaction() as connection:
            cls._ensure_state(
                connection,
                area=area,
                student_id=student_id,
                session_id=session_id,
            )
            runtime = cls._read_state(
                connection,
                area=area,
                student_id=student_id,
                session_id=session_id,
            )
            if runtime["status"] != cls.REVIEWING:
                return None

            task = connection.execute(
                """
                SELECT task_id, student_id, session_id, area, concept_id
                FROM learning_tasks
                WHERE task_id = ?
                """,
                (normalized_task_id,),
            ).fetchone()
            if task is None:
                raise SessionLifecycleError("tarefa da revisão não encontrada")
            if (
                task["student_id"] != student_id
                or task["session_id"] != session_id
                or task["area"] != area
                or task["concept_id"] != runtime.get("resume_concept_id")
            ):
                raise SessionLifecycleError(
                    "tarefa não pertence à revisão de retomada"
                )

            existing = runtime.get("review_task_id")
            if existing:
                if existing != normalized_task_id:
                    raise SessionLifecycleError(
                        "revisão de retomada já possui outra tarefa"
                    )
                return runtime

            connection.execute(
                """
                UPDATE learning_session_states
                SET review_task_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE student_id = ?
                  AND session_id = ?
                  AND area = ?
                """,
                (normalized_task_id, student_id, session_id, area),
            )
            return cls._read_state(
                connection,
                area=area,
                student_id=student_id,
                session_id=session_id,
            )

    @classmethod
    def complete_resume_review(
        cls,
        area,
        learner_state,
        semantic_evidence,
        *,
        evidence_applied,
        task_id=None,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
    ):
        if not evidence_applied or not isinstance(semantic_evidence, dict):
            return None
        if semantic_evidence.get("outcome") != EvidenceEvaluator.DEMONSTRATED:
            return None

        area, student_id, session_id = cls._normalize_context(
            area,
            student_id=student_id,
            session_id=session_id,
        )

        with transaction() as connection:
            cls._ensure_state(
                connection,
                area=area,
                student_id=student_id,
                session_id=session_id,
            )
            runtime = cls._read_state(
                connection,
                area=area,
                student_id=student_id,
                session_id=session_id,
            )
            if runtime["status"] != cls.REVIEWING:
                return None

            bound_task_id = runtime.get("review_task_id")
            normalized_task_id = str(task_id or "").strip() or None
            if not bound_task_id or normalized_task_id != bound_task_id:
                return None

            concept_id = runtime.get("resume_concept_id")
            if not concept_id:
                raise SessionLifecycleError(
                    "revisão de retomada sem conceito de origem"
                )
            if learner_state.get("current_concept_id") != concept_id:
                raise SessionLifecycleError(
                    "conceito ativo mudou durante a revisão de retomada"
                )

            restore_stage = runtime.get("resume_stage") or "compreender"
            updated_learner_state = LearnerState.update(
                area,
                current_concept_id=concept_id,
                stage=restore_stage,
                student_id=student_id,
            )

            connection.execute(
                """
                UPDATE learning_session_states
                SET status = 'studying',
                    resume_concept_id = NULL,
                    resume_stage = NULL,
                    review_task_id = NULL,
                    paused_at = NULL,
                    last_resumed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE student_id = ?
                  AND session_id = ?
                  AND area = ?
                """,
                (student_id, session_id, area),
            )

            cls._record_event(
                connection,
                student_id=student_id,
                session_id=session_id,
                area=area,
                event_type=cls.EVENT_RESUME_REVIEW_COMPLETED,
                status_before=cls.REVIEWING,
                status_after=cls.STUDYING,
                concept_id=concept_id,
                stage_snapshot=restore_stage,
            )

            return {
                "session": cls._read_state(
                    connection,
                    area=area,
                    student_id=student_id,
                    session_id=session_id,
                ),
                "learner_state": updated_learner_state,
            }
