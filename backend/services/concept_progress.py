from backend.database import get_db_connection


class ConceptProgress:
    ALLOWED_AREAS = {"ads", "it"}

    @classmethod
    def normalize_area(cls, area):
        if not isinstance(area, str):
            return "ads"
        area = area.strip().lower()
        return area if area in cls.ALLOWED_AREAS else "ads"

    @staticmethod
    def normalize_concept(concept):
        if not isinstance(concept, str):
            return None
        concept = " ".join(concept.split())
        return concept or None

    @classmethod
    def get(cls, area, concept):
        area = cls.normalize_area(area)
        concept = cls.normalize_concept(concept)
        if not concept:
            return None
        connection = get_db_connection()
        try:
            row = connection.execute(
                "SELECT * FROM concept_progress WHERE area = ? AND concept = ?",
                (area, concept),
            ).fetchone()
            if row is not None:
                return dict(row)
            return {
                "area": area,
                "concept": concept,
                "mastery": 0.0,
                "difficulty_count": 0,
                "last_evidence": None,
                "review_count": 0,
                "next_review_at": None,
                "last_reviewed_at": None,
                "updated_at": None,
            }
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

    @staticmethod
    def normalize_review_count(value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return 0
        return max(0, value)

    @classmethod
    def update(
        cls,
        area,
        concept,
        mastery=None,
        difficulty_count=None,
        last_evidence=None,
        review_count=None,
        next_review_at=None,
        last_reviewed_at=None,
    ):
        area = cls.normalize_area(area)
        concept = cls.normalize_concept(concept)
        if not concept:
            return None
        current = cls.get(area, concept)
        mastery_value = current["mastery"] if mastery is None else cls.normalize_mastery(mastery)
        difficulty = current["difficulty_count"] if difficulty_count is None else cls.normalize_difficulty_count(difficulty_count)
        reviews = current["review_count"] if review_count is None else cls.normalize_review_count(review_count)
        evidence = current["last_evidence"] if last_evidence is None else str(last_evidence).strip() or None
        next_review = current["next_review_at"] if next_review_at is None else str(next_review_at).strip() or None
        last_reviewed = current["last_reviewed_at"] if last_reviewed_at is None else str(last_reviewed_at).strip() or None
        connection = get_db_connection()
        try:
            connection.execute("""
                INSERT INTO concept_progress (
                    area, concept, mastery, difficulty_count, last_evidence,
                    review_count, next_review_at, last_reviewed_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(area, concept) DO UPDATE SET
                    mastery = excluded.mastery,
                    difficulty_count = excluded.difficulty_count,
                    last_evidence = excluded.last_evidence,
                    review_count = excluded.review_count,
                    next_review_at = excluded.next_review_at,
                    last_reviewed_at = excluded.last_reviewed_at,
                    updated_at = CURRENT_TIMESTAMP
            """, (area, concept, mastery_value, difficulty, evidence, reviews, next_review, last_reviewed))
            connection.commit()
        finally:
            connection.close()

        return cls.get(area, concept)

    @classmethod
    def list_scheduled(cls, area):
        area = cls.normalize_area(area)
        connection = get_db_connection()
        try:
            rows = connection.execute(
                """
                SELECT * FROM concept_progress
                WHERE area = ?
                  AND next_review_at IS NOT NULL
                ORDER BY next_review_at ASC
                """,
                (area,),
            ).fetchall()

            return [dict(row) for row in rows]
        finally:
            connection.close()
