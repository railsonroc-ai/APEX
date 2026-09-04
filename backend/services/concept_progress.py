from backend.database import get_db_connection
from backend.identity import DEFAULT_STUDENT_ID, normalize_student_id
from backend.services.concept_catalog import ConceptCatalog


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
        return " ".join(concept.split()) or None

    @classmethod
    def _resolve(cls, area, concept):
        return ConceptCatalog.resolve(cls.normalize_area(area), concept)

    @classmethod
    def get(cls, area, concept, student_id=DEFAULT_STUDENT_ID):
        area = cls.normalize_area(area)
        student_id = normalize_student_id(student_id)
        definition = cls._resolve(area, concept)
        if not definition:
            return None
        concept_id = definition["concept_id"]

        connection = get_db_connection()
        try:
            row = connection.execute(
                """
                SELECT
                    progress.*,
                    definition.canonical_name AS concept
                FROM concept_progress AS progress
                JOIN concept_definitions AS definition
                  ON definition.area = progress.area
                 AND definition.concept_id = progress.concept_id
                WHERE progress.student_id = ?
                  AND progress.area = ?
                  AND progress.concept_id = ?
                """,
                (student_id, area, concept_id),
            ).fetchone()
            if row is not None:
                return dict(row)
            return {
                "student_id": student_id,
                "area": area,
                "concept_id": concept_id,
                "concept": definition["canonical_name"],
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
        cls, area, concept, mastery=None, difficulty_count=None,
        last_evidence=None, review_count=None, next_review_at=None,
        last_reviewed_at=None, student_id=DEFAULT_STUDENT_ID,
    ):
        area = cls.normalize_area(area)
        student_id = normalize_student_id(student_id)
        definition = cls._resolve(area, concept)
        if not definition:
            return None
        concept_id = definition["concept_id"]
        current = cls.get(area, concept_id, student_id=student_id)
        mastery_value = current["mastery"] if mastery is None else cls.normalize_mastery(mastery)
        difficulty = current["difficulty_count"] if difficulty_count is None else cls.normalize_difficulty_count(difficulty_count)
        reviews = current["review_count"] if review_count is None else cls.normalize_review_count(review_count)
        evidence = current["last_evidence"] if last_evidence is None else str(last_evidence).strip() or None
        next_review = current["next_review_at"] if next_review_at is None else str(next_review_at).strip() or None
        last_reviewed = current["last_reviewed_at"] if last_reviewed_at is None else str(last_reviewed_at).strip() or None

        connection = get_db_connection()
        try:
            connection.execute(
                """
                INSERT INTO concept_progress (
                    student_id, area, concept_id, mastery, difficulty_count,
                    last_evidence, review_count, next_review_at,
                    last_reviewed_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(student_id, area, concept_id) DO UPDATE SET
                    mastery = excluded.mastery,
                    difficulty_count = excluded.difficulty_count,
                    last_evidence = excluded.last_evidence,
                    review_count = excluded.review_count,
                    next_review_at = excluded.next_review_at,
                    last_reviewed_at = excluded.last_reviewed_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    student_id, area, concept_id, mastery_value, difficulty,
                    evidence, reviews, next_review, last_reviewed,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        return cls.get(area, concept_id, student_id=student_id)

    @classmethod
    def list_scheduled(cls, area, student_id=DEFAULT_STUDENT_ID):
        area = cls.normalize_area(area)
        student_id = normalize_student_id(student_id)
        connection = get_db_connection()
        try:
            rows = connection.execute(
                """
                SELECT
                    progress.*,
                    definition.canonical_name AS concept
                FROM concept_progress AS progress
                JOIN concept_definitions AS definition
                  ON definition.area = progress.area
                 AND definition.concept_id = progress.concept_id
                WHERE progress.student_id = ?
                  AND progress.area = ?
                  AND progress.next_review_at IS NOT NULL
                ORDER BY progress.next_review_at ASC
                """,
                (student_id, area),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()
