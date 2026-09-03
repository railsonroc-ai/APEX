from backend.database import get_db_connection


class LearnerState:
    ALLOWED_AREAS = {"ads", "it"}
    ALLOWED_STAGES = {"ler", "compreender", "explicar", "testar", "corrigir", "fixar", "concluido", "reencontrar"}

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
    def get(cls, area="ads"):
        area = cls.normalize_area(area)
        connection = get_db_connection()
        try:
            row = connection.execute(
                "SELECT * FROM learner_state WHERE area = ?",
                (area,),
            ).fetchone()
            if row is None:
                return {
                    "area": area,
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
        stage=None,
        last_evidence=None,
        difficulty_count=None,
        mastery=None,
    ):
        area = cls.normalize_area(area)
        current = cls.get(area)
        concept = current["current_concept"] if current_concept is None else str(current_concept).strip() or None
        stage = current["stage"] if stage is None else cls.normalize_stage(stage)
        evidence = current["last_evidence"] if last_evidence is None else str(last_evidence).strip() or None
        difficulty = current["difficulty_count"] if difficulty_count is None else cls.normalize_difficulty_count(difficulty_count)
        mastery_value = current["mastery"] if mastery is None else cls.normalize_mastery(mastery)
        connection = get_db_connection()
        try:
            connection.execute("""
                INSERT INTO learner_state (
                    area, current_concept, stage, last_evidence,
                    difficulty_count, mastery, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(area) DO UPDATE SET
                    current_concept = excluded.current_concept,
                    stage = excluded.stage,
                    last_evidence = excluded.last_evidence,
                    difficulty_count = excluded.difficulty_count,
                    mastery = excluded.mastery,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (area, concept, stage, evidence, difficulty, mastery_value),
            )
            connection.commit()
        finally:
            connection.close()

        return cls.get(area)
