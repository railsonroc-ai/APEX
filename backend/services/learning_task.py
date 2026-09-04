from uuid import uuid4

from backend.database import get_db_connection
from backend.identity import DEFAULT_STUDENT_ID, default_session_id, normalize_student_id
from backend.services.assistance_policy import AssistancePolicy
from backend.services.concept_catalog import ConceptCatalog
from backend.services.learning_history import LearningHistory
from backend.services.rubric_policy import RubricPolicy
from backend.services.task_policy import TaskPolicy


class LearningTask:
    """Ledger imutável da tarefa concreta apresentada pelo tutor ao aluno."""

    MAX_PROMPT_CHARS = 4000

    @classmethod
    def record(
        cls,
        *,
        source_turn_id,
        area,
        concept_id,
        stage,
        teaching_action,
        prompt_text,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
    ):
        normalized_student_id = normalize_student_id(student_id)
        normalized_area = LearningHistory.normalize_area(area)
        normalized_session_id = LearningHistory.normalize_session_id(session_id)
        normalized_source_turn_id = LearningHistory.normalize_turn_id(source_turn_id)
        normalized_prompt = LearningHistory.normalize_message(prompt_text)

        if not normalized_session_id and normalized_student_id == DEFAULT_STUDENT_ID:
            normalized_session_id = default_session_id(normalized_area)

        definition = ConceptCatalog.resolve(normalized_area, concept_id)
        contract = TaskPolicy.contract_for_action(teaching_action)

        if not normalized_source_turn_id:
            raise ValueError("source_turn_id obrigatória")
        if not normalized_session_id:
            raise ValueError("session_id obrigatória")
        if definition is None:
            raise ValueError("concept_id inválido")
        if not contract["assessable"]:
            return None
        if not isinstance(stage, str) or not stage.strip():
            raise ValueError("stage obrigatória")
        if not normalized_prompt:
            raise ValueError("prompt_text obrigatório")
        if len(normalized_prompt) > cls.MAX_PROMPT_CHARS:
            raise ValueError("prompt_text muito longo")

        source_turn = LearningHistory.find(
            normalized_source_turn_id,
            student_id=normalized_student_id,
        )
        if source_turn is None:
            raise ValueError("turno fonte da tarefa não encontrado")
        if source_turn["area"] != normalized_area:
            raise ValueError("turno fonte não corresponde à área")
        if source_turn.get("session_id") != normalized_session_id:
            raise ValueError("turno fonte não corresponde à sessão")
        if source_turn.get("concept_id") != definition["concept_id"]:
            raise ValueError("turno fonte não corresponde ao conceito")
        if LearningHistory.normalize_message(source_turn.get("assistant_message")) != normalized_prompt:
            raise ValueError("prompt da tarefa não corresponde ao turno confirmado")

        assistance_level = AssistancePolicy.level_for_action(teaching_action)
        task_id = f"task_{uuid4().hex}"

        connection = get_db_connection()
        try:
            existing = connection.execute(
                """
                SELECT * FROM learning_tasks
                WHERE student_id = ? AND source_turn_id = ?
                """,
                (normalized_student_id, normalized_source_turn_id),
            ).fetchone()
            if existing is not None:
                row = dict(existing)
                expected = {
                    "session_id": normalized_session_id,
                    "area": normalized_area,
                    "concept_id": definition["concept_id"],
                    "stage": stage,
                    "teaching_action": contract["teaching_action"],
                    "task_kind": contract["task_kind"],
                    "prompt_text": normalized_prompt,
                    "assistance_level": assistance_level,
                    "rubric_id": RubricPolicy.RUBRIC_ID,
                    "rubric_version": RubricPolicy.RUBRIC_VERSION,
                    "policy_id": TaskPolicy.POLICY_ID,
                    "policy_version": TaskPolicy.POLICY_VERSION,
                }
                if any(row.get(key) != value for key, value in expected.items()):
                    raise ValueError("turno fonte reutilizado com tarefa diferente")
                return row

            connection.execute(
                """
                INSERT INTO learning_tasks (
                    task_id, student_id, session_id, source_turn_id,
                    area, concept_id, stage, teaching_action, task_kind,
                    prompt_text, assistance_level, rubric_id, rubric_version,
                    policy_id, policy_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    normalized_student_id,
                    normalized_session_id,
                    normalized_source_turn_id,
                    normalized_area,
                    definition["concept_id"],
                    stage,
                    contract["teaching_action"],
                    contract["task_kind"],
                    normalized_prompt,
                    assistance_level,
                    RubricPolicy.RUBRIC_ID,
                    RubricPolicy.RUBRIC_VERSION,
                    TaskPolicy.POLICY_ID,
                    TaskPolicy.POLICY_VERSION,
                ),
            )
            row = connection.execute(
                "SELECT * FROM learning_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            connection.commit()
            return dict(row)
        finally:
            connection.close()

    @classmethod
    def find_by_source_turn(
        cls,
        source_turn_id,
        *,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
    ):
        normalized_student_id = normalize_student_id(student_id)
        normalized_turn_id = LearningHistory.normalize_turn_id(source_turn_id)
        normalized_session_id = LearningHistory.normalize_session_id(session_id)
        if not normalized_turn_id:
            return None

        connection = get_db_connection()
        try:
            query = (
                "SELECT * FROM learning_tasks "
                "WHERE student_id = ? AND source_turn_id = ?"
            )
            params = [normalized_student_id, normalized_turn_id]
            if normalized_session_id:
                query += " AND session_id = ?"
                params.append(normalized_session_id)
            row = connection.execute(query, tuple(params)).fetchone()
            return dict(row) if row is not None else None
        finally:
            connection.close()

    @classmethod
    def find(cls, task_id, *, student_id=DEFAULT_STUDENT_ID):
        normalized_student_id = normalize_student_id(student_id)
        if not isinstance(task_id, str) or not task_id.strip():
            return None
        connection = get_db_connection()
        try:
            row = connection.execute(
                "SELECT * FROM learning_tasks WHERE student_id = ? AND task_id = ?",
                (normalized_student_id, task_id.strip()),
            ).fetchone()
            return dict(row) if row is not None else None
        finally:
            connection.close()
