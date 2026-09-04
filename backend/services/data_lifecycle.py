import json
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from backend.database import get_db_connection, transaction
from backend.identity import DEFAULT_STUDENT_ID


class DataLifecycleError(RuntimeError):
    pass


class DataLifecycle:
    """Exportação, exclusão e retenção dos dados de um aluno.

    O serviço nunca aceita student_id do navegador diretamente: as rotas devem
    fornecer a identidade já autenticada pelo servidor. A exclusão é
    transacional e usa uma autorização temporária de migration para permitir a
    remoção dos ledgers que, fora deste fluxo, continuam imutáveis.
    """

    POLICY_ID = "student_data_lifecycle"
    POLICY_VERSION = 1
    EXPORT_FORMAT_VERSION = 1
    DELETE_CONFIRMATION = "EXCLUIR MEUS DADOS"

    EXPORT_QUERIES = (
        (
            "student",
            "SELECT id, created_at, updated_at FROM students WHERE id = ?",
        ),
        (
            "learning_sessions",
            """
            SELECT id, student_id, area, started_at, ended_at
            FROM learning_sessions
            WHERE student_id = ?
            ORDER BY area, started_at, id
            """,
        ),
        (
            "learning_session_states",
            """
            SELECT student_id, session_id, area, status, resume_concept_id,
                   resume_stage, review_task_id, paused_at, last_resumed_at,
                   updated_at
            FROM learning_session_states
            WHERE student_id = ?
            ORDER BY area, session_id
            """,
        ),
        (
            "learner_state",
            """
            SELECT student_id, area, current_concept_id, stage, last_evidence,
                   difficulty_count, mastery, updated_at
            FROM learner_state
            WHERE student_id = ?
            ORDER BY area
            """,
        ),
        (
            "concept_progress",
            """
            SELECT student_id, area, concept_id, mastery, difficulty_count,
                   last_evidence, review_count, next_review_at,
                   last_reviewed_at, updated_at
            FROM concept_progress
            WHERE student_id = ?
            ORDER BY area, concept_id
            """,
        ),
        (
            "learning_turns",
            """
            SELECT student_id, session_id, turn_id, area, user_message,
                   assistant_message, concept_id, created_at
            FROM learning_turns
            WHERE student_id = ?
            ORDER BY created_at, id
            """,
        ),
        (
            "learning_tasks",
            """
            SELECT task_id, student_id, session_id, source_turn_id, area,
                   concept_id, stage, teaching_action, task_kind, prompt_text,
                   assistance_level, rubric_id, rubric_version, policy_id,
                   policy_version, created_at
            FROM learning_tasks
            WHERE student_id = ?
            ORDER BY created_at, id
            """,
        ),
        (
            "learning_attempts",
            """
            SELECT attempt_id, student_id, session_id, turn_id, source_turn_id,
                   area, concept_id, stage, attempt_kind, student_answer,
                   artifact_ref, assistance_level, policy_id, policy_version,
                   task_id, created_at
            FROM learning_attempts
            WHERE student_id = ?
            ORDER BY created_at, id
            """,
        ),
        (
            "rubric_assessments",
            """
            SELECT assessment_id, student_id, session_id, turn_id, attempt_id,
                   evidence_event_id, area, concept_id, task_response,
                   conceptual_correctness, understanding_application,
                   criteria_complete, outcome, outcome_source, confidence,
                   rubric_id, rubric_version, created_at
            FROM rubric_assessments
            WHERE student_id = ?
            ORDER BY created_at, id
            """,
        ),
        (
            "evidence_events",
            """
            SELECT event_id, student_id, session_id, turn_id, area, concept_id,
                   stage_before, stage_after, outcome, confidence, evidence_text,
                   tutor_message, student_answer, assistance_level, artifact_ref,
                   rubric_id, rubric_version, policy_id, policy_version, source,
                   applied, mastery_before, mastery_after, created_at
            FROM evidence_events
            WHERE student_id = ?
            ORDER BY created_at, id
            """,
        ),
        (
            "mastery_assessments",
            """
            SELECT assessment_id, student_id, session_id, turn_id,
                   evidence_event_id, area, concept_id, score, can_complete,
                   applied_evidence_count, demonstrated_count,
                   demonstrated_stage_count, retention_demonstrated_count,
                   low_assistance_demonstrated_count, latest_outcome,
                   recommended_stage, blockers_json, policy_id, policy_version,
                   created_at
            FROM mastery_assessments
            WHERE student_id = ?
            ORDER BY created_at, id
            """,
        ),
        (
            "assistance_events",
            """
            SELECT assistance_id, student_id, session_id, turn_id, area,
                   concept_id, teaching_action, assistance_level, policy_id,
                   policy_version, created_at
            FROM assistance_events
            WHERE student_id = ?
            ORDER BY created_at, id
            """,
        ),
        (
            "learning_session_events",
            """
            SELECT event_id, student_id, session_id, area, event_type,
                   status_before, status_after, concept_id, stage_snapshot,
                   policy_id, policy_version, created_at
            FROM learning_session_events
            WHERE student_id = ?
            ORDER BY created_at, id
            """,
        ),
        (
            "notes",
            """
            SELECT id, student_id, text, area, created_at
            FROM notes
            WHERE student_id = ?
            ORDER BY created_at, id
            """,
        ),
        (
            "access_credentials",
            """
            SELECT credential_id, student_id, label, is_active,
                   created_at, revoked_at
            FROM access_credentials
            WHERE student_id = ?
            ORDER BY created_at, credential_id
            """,
        ),
    )

    DELETE_ORDER = (
        "learning_session_states",
        "rubric_assessments",
        "mastery_assessments",
        "assistance_events",
        "learning_attempts",
        "learning_session_events",
        "evidence_events",
        "learning_tasks",
        "concept_progress",
        "learner_state",
        "notes",
        "learning_turn_leases",
        "learning_turns",
        "learning_sessions",
    )

    @staticmethod
    def _rows(connection, query, student_id):
        rows = connection.execute(query, (student_id,)).fetchall()
        return [dict(row) for row in rows]

    @classmethod
    def export_student(cls, student_id):
        normalized = str(student_id or "").strip()
        if not normalized:
            raise DataLifecycleError("student_id obrigatorio")

        connection = get_db_connection()
        try:
            student = connection.execute(
                "SELECT id FROM students WHERE id = ?",
                (normalized,),
            ).fetchone()
            if student is None:
                raise DataLifecycleError("aluno nao encontrado")

            datasets = {}
            for name, query in cls.EXPORT_QUERIES:
                datasets[name] = cls._rows(connection, query, normalized)
        finally:
            connection.close()

        return {
            "format": "apex_student_export",
            "format_version": cls.EXPORT_FORMAT_VERSION,
            "policy_id": cls.POLICY_ID,
            "policy_version": cls.POLICY_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "student_id": normalized,
            "datasets": datasets,
        }

    @classmethod
    def delete_student(cls, student_id):
        normalized = str(student_id or "").strip()
        if not normalized:
            raise DataLifecycleError("student_id obrigatorio")

        receipt_id = f"privacy_{uuid4().hex}"
        counts = {}

        with transaction() as connection:
            exists = connection.execute(
                "SELECT 1 FROM students WHERE id = ?",
                (normalized,),
            ).fetchone()
            if exists is None:
                raise DataLifecycleError("aluno nao encontrado")

            credential_ids = [
                row["credential_id"]
                for row in connection.execute(
                    "SELECT credential_id FROM access_credentials WHERE student_id = ?",
                    (normalized,),
                ).fetchall()
            ]

            connection.execute(
                """
                INSERT INTO privacy_deletion_authorizations (
                    student_id,
                    receipt_id
                )
                VALUES (?, ?)
                """,
                (normalized, receipt_id),
            )

            for table in cls.DELETE_ORDER:
                cursor = connection.execute(
                    f"DELETE FROM {table} WHERE student_id = ?",
                    (normalized,),
                )
                counts[table] = cursor.rowcount

            rate_limit_subjects = list(credential_ids)
            if normalized == DEFAULT_STUDENT_ID:
                rate_limit_subjects.extend(
                    ["environment-default", "development-default"]
                )

            deleted_rate_limits = 0
            for subject_id in dict.fromkeys(rate_limit_subjects):
                cursor = connection.execute(
                    "DELETE FROM api_rate_limits WHERE subject_id = ?",
                    (subject_id,),
                )
                deleted_rate_limits += cursor.rowcount
            counts["api_rate_limits"] = deleted_rate_limits

            cursor = connection.execute(
                "DELETE FROM access_credentials WHERE student_id = ?",
                (normalized,),
            )
            counts["access_credentials"] = cursor.rowcount

            cursor = connection.execute(
                "DELETE FROM students WHERE id = ?",
                (normalized,),
            )
            counts["students"] = cursor.rowcount

            connection.execute(
                "DELETE FROM privacy_deletion_authorizations WHERE student_id = ?",
                (normalized,),
            )

        return {
            "receipt_id": receipt_id,
            "policy_id": cls.POLICY_ID,
            "policy_version": cls.POLICY_VERSION,
            "deleted": counts,
        }

    @classmethod
    def _last_activity_rows(cls, connection):
        """Uma linha por aluno com atividade máxima conhecida.

        O cálculo é deliberadamente conservador: a retenção só considera alunos
        sem credencial ativa e nunca inclui o aluno padrão.
        """

        return connection.execute(
            """
            SELECT
                s.id AS student_id,
                MAX(
                    s.updated_at,
                    COALESCE((
                        SELECT MAX(t.created_at)
                        FROM learning_turns t
                        WHERE t.student_id = s.id
                    ), s.updated_at),
                    COALESCE((
                        SELECT MAX(n.created_at)
                        FROM notes n
                        WHERE n.student_id = s.id
                    ), s.updated_at),
                    COALESCE((
                        SELECT MAX(cp.updated_at)
                        FROM concept_progress cp
                        WHERE cp.student_id = s.id
                    ), s.updated_at),
                    COALESCE((
                        SELECT MAX(ls.started_at)
                        FROM learning_sessions ls
                        WHERE ls.student_id = s.id
                    ), s.updated_at),
                    COALESCE((
                        SELECT MAX(COALESCE(ac.revoked_at, ac.created_at))
                        FROM access_credentials ac
                        WHERE ac.student_id = s.id
                    ), s.updated_at)
                ) AS last_activity_at
            FROM students s
            WHERE s.id <> ?
              AND NOT EXISTS (
                  SELECT 1
                  FROM access_credentials active
                  WHERE active.student_id = s.id
                    AND active.is_active = 1
              )
            GROUP BY s.id
            ORDER BY s.id
            """,
            (DEFAULT_STUDENT_ID,),
        ).fetchall()

    @classmethod
    def retention_candidates(cls, retention_days, *, now=None):
        days = int(retention_days)
        if days < 30:
            raise DataLifecycleError(
                "retention_days deve ser pelo menos 30"
            )

        reference = now or datetime.now(timezone.utc)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        cutoff = reference - timedelta(days=days)

        connection = get_db_connection()
        try:
            rows = cls._last_activity_rows(connection)
        finally:
            connection.close()

        candidates = []
        for row in rows:
            raw = row["last_activity_at"]
            if not raw:
                continue
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if parsed <= cutoff:
                candidates.append(
                    {
                        "student_id": row["student_id"],
                        "last_activity_at": parsed.isoformat(),
                    }
                )
        return candidates

    @classmethod
    def apply_retention(cls, retention_days, *, now=None, dry_run=True):
        candidates = cls.retention_candidates(retention_days, now=now)
        result = {
            "policy_id": cls.POLICY_ID,
            "policy_version": cls.POLICY_VERSION,
            "retention_days": int(retention_days),
            "dry_run": bool(dry_run),
            "candidates": candidates,
            "deleted": [],
        }
        if dry_run:
            return result

        for candidate in candidates:
            deletion = cls.delete_student(candidate["student_id"])
            result["deleted"].append(
                {
                    "student_id": candidate["student_id"],
                    "receipt_id": deletion["receipt_id"],
                }
            )
        return result

    @staticmethod
    def to_json_bytes(payload):
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ).encode("utf-8")
