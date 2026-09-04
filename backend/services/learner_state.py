from backend.database import get_db_connection
from backend.identity import DEFAULT_STUDENT_ID, normalize_student_id
from backend.services.concept_catalog import ConceptCatalog


class LearnerState:
    ALLOWED_AREAS = {"ads", "it"}
    ALLOWED_STAGES = {
        "ler", "compreender", "explicar", "testar", "corrigir",
        "fixar", "concluido", "reencontrar",
    }

    @classmethod
    def normalize_area(cls, area):
        if not isinstance(area, str):
            return "ads"
        area = area.strip().lower()
        return area if area in cls.ALLOWED_AREAS else "ads"

    @classmethod
    def normalize_stage(cls, stage):
        if not isinstance(stage, str):
            return "compreender"
        stage = stage.strip().lower()
        return stage if stage in cls.ALLOWED_STAGES else "compreender"

    @classmethod
    def get(cls, area="ads", student_id=DEFAULT_STUDENT_ID):
        area = cls.normalize_area(area)
        student_id = normalize_student_id(student_id)
        connection = get_db_connection()
        try:
            row = connection.execute(
                """
                SELECT
                    state.*,
                    definition.canonical_name AS current_concept
                FROM learner_state AS state
                LEFT JOIN concept_definitions AS definition
                  ON definition.area = state.area
                 AND definition.concept_id = state.current_concept_id
                WHERE state.student_id = ?
                  AND state.area = ?
                """,
                (student_id, area),
            ).fetchone()
            if row is None:
                return {
                    "student_id": student_id,
                    "area": area,
                    "current_concept_id": None,
                    "current_concept": None,
                    "stage": "compreender",
                    "last_evidence": None,
                    "difficulty_count": 0,
                    "mastery": 0.0,
                    "updated_at": None,
                }
            return dict(row)
        finally:
            connection.close()

    @staticmethod
    def normalize_mastery(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return 0.0
        return min(1.0, max(0.0, value))

    @staticmethod
    def normalize_difficulty_count(value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return 0
        return max(0, value)

    @classmethod
    def update(
        cls,
        area="ads",
        current_concept=None,
        current_concept_id=None,
        stage=None,
        last_evidence=None,
        difficulty_count=None,
        mastery=None,
        student_id=DEFAULT_STUDENT_ID,
    ):
        area = cls.normalize_area(area)
        student_id = normalize_student_id(student_id)
        current = cls.get(area, student_id=student_id)

        concept_value_supplied = current_concept_id is not None or current_concept is not None
        if not concept_value_supplied:
            concept_id = current.get("current_concept_id")
        else:
            requested = current_concept_id if current_concept_id is not None else current_concept
            if isinstance(requested, str) and not requested.strip():
                concept_id = None
            else:
                resolved = ConceptCatalog.resolve(area, requested)
                if resolved is None:
                    raise ValueError("conceito não pertence ao catálogo")
                concept_id = resolved["concept_id"]

        stage_value = current["stage"] if stage is None else cls.normalize_stage(stage)
        evidence = current["last_evidence"] if last_evidence is None else str(last_evidence).strip() or None
        difficulty = current["difficulty_count"] if difficulty_count is None else cls.normalize_difficulty_count(difficulty_count)
        mastery_value = current["mastery"] if mastery is None else cls.normalize_mastery(mastery)

        connection = get_db_connection()
        try:
            connection.execute(
                """
                INSERT INTO learner_state (
                    student_id, area, current_concept_id, stage,
                    last_evidence, difficulty_count, mastery, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(student_id, area) DO UPDATE SET
                    current_concept_id = excluded.current_concept_id,
                    stage = excluded.stage,
                    last_evidence = excluded.last_evidence,
                    difficulty_count = excluded.difficulty_count,
                    mastery = excluded.mastery,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    student_id, area, concept_id, stage_value, evidence,
                    difficulty, mastery_value,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        return cls.get(area, student_id=student_id)
