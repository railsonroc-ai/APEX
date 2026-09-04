from backend.config import MAX_HISTORY_MESSAGES
from backend.database import get_db_connection
from backend.identity import (
    DEFAULT_STUDENT_ID,
    default_session_id,
    normalize_student_id,
)
from backend.services.concept_catalog import ConceptCatalog


class LearningHistory:
    """Histórico confirmado do servidor, isolado por aluno e concept_id."""

    ALLOWED_AREAS = {"ads", "it"}
    MAX_CONTENT_CHARS = 4000

    @classmethod
    def normalize_area(cls, area):
        if not isinstance(area, str):
            return "ads"
        normalized = area.strip().lower()
        return normalized if normalized in cls.ALLOWED_AREAS else "ads"

    @staticmethod
    def normalize_turn_id(turn_id):
        if turn_id is None:
            return None
        return str(turn_id).strip() or None

    @staticmethod
    def normalize_message(message):
        if message is None:
            return None
        return str(message).strip() or None

    @staticmethod
    def normalize_concept(concept):
        if concept is None:
            return None
        normalized = " ".join(str(concept).split())
        return normalized or None

    @staticmethod
    def normalize_session_id(session_id):
        if session_id is None:
            return None
        return str(session_id).strip() or None

    @classmethod
    def resolve_concept_id(cls, area, concept=None, concept_id=None):
        requested = concept_id if concept_id is not None else concept
        if requested is None:
            return None
        definition = ConceptCatalog.resolve(cls.normalize_area(area), requested)
        return definition.get("concept_id") if definition else None

    @classmethod
    def find(cls, turn_id, student_id=DEFAULT_STUDENT_ID):
        normalized_turn_id = cls.normalize_turn_id(turn_id)
        normalized_student_id = normalize_student_id(student_id)
        if not normalized_turn_id:
            return None

        connection = get_db_connection()
        try:
            row = connection.execute(
                """
                SELECT
                    turns.student_id,
                    turns.session_id,
                    turns.turn_id,
                    turns.area,
                    turns.user_message,
                    turns.assistant_message,
                    turns.concept_id,
                    definition.canonical_name AS concept,
                    turns.created_at
                FROM learning_turns AS turns
                LEFT JOIN concept_definitions AS definition
                  ON definition.area = turns.area
                 AND definition.concept_id = turns.concept_id
                WHERE turns.student_id = ?
                  AND turns.turn_id = ?
                """,
                (normalized_student_id, normalized_turn_id),
            ).fetchone()
            return dict(row) if row is not None else None
        finally:
            connection.close()

    @classmethod
    def record(
        cls,
        turn_id,
        area,
        user_message,
        assistant_message,
        concept=None,
        concept_id=None,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
    ):
        normalized_turn_id = cls.normalize_turn_id(turn_id)
        normalized_area = cls.normalize_area(area)
        normalized_user = cls.normalize_message(user_message)
        normalized_assistant = cls.normalize_message(assistant_message)
        normalized_concept_id = cls.resolve_concept_id(
            normalized_area,
            concept=concept,
            concept_id=concept_id,
        )
        normalized_student_id = normalize_student_id(student_id)
        normalized_session_id = cls.normalize_session_id(session_id)

        if not normalized_session_id and normalized_student_id == DEFAULT_STUDENT_ID:
            normalized_session_id = default_session_id(normalized_area)
        if not normalized_turn_id:
            raise ValueError("turn_id obrigatório")
        if not normalized_user:
            raise ValueError("user_message obrigatória")
        if not normalized_session_id:
            raise ValueError("session_id obrigatória")
        if (concept is not None or concept_id is not None) and not normalized_concept_id:
            raise ValueError("conceito não pertence ao catálogo")

        connection = get_db_connection()
        try:
            connection.execute(
                """
                INSERT INTO learning_turns (
                    student_id, session_id, turn_id, area,
                    user_message, assistant_message, concept_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_student_id,
                    normalized_session_id,
                    normalized_turn_id,
                    normalized_area,
                    normalized_user,
                    normalized_assistant,
                    normalized_concept_id,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        return cls.find(normalized_turn_id, student_id=normalized_student_id)

    @classmethod
    def attach_response(
        cls,
        turn_id,
        assistant_message,
        concept=None,
        concept_id=None,
        student_id=DEFAULT_STUDENT_ID,
    ):
        normalized_turn_id = cls.normalize_turn_id(turn_id)
        normalized_assistant = cls.normalize_message(assistant_message)
        normalized_student_id = normalize_student_id(student_id)

        existing = cls.find(normalized_turn_id, student_id=normalized_student_id)
        if existing is None or not normalized_assistant:
            return existing

        normalized_concept_id = cls.resolve_concept_id(
            existing["area"],
            concept=concept,
            concept_id=concept_id,
        )
        if (concept is not None or concept_id is not None) and not normalized_concept_id:
            raise ValueError("conceito não pertence ao catálogo")

        connection = get_db_connection()
        try:
            connection.execute(
                """
                UPDATE learning_turns
                SET
                    assistant_message = ?,
                    concept_id = COALESCE(concept_id, ?)
                WHERE student_id = ?
                  AND turn_id = ?
                  AND (
                      assistant_message IS NULL
                      OR TRIM(assistant_message) = ''
                  )
                """,
                (
                    normalized_assistant,
                    normalized_concept_id,
                    normalized_student_id,
                    normalized_turn_id,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        return cls.find(normalized_turn_id, student_id=normalized_student_id)

    @classmethod
    def latest_confirmed_turn(
        cls,
        area,
        concept=None,
        concept_id=None,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
    ):
        normalized_area = cls.normalize_area(area)
        normalized_student_id = normalize_student_id(student_id)
        normalized_session_id = cls.normalize_session_id(session_id)
        normalized_concept_id = cls.resolve_concept_id(
            normalized_area,
            concept=concept,
            concept_id=concept_id,
        )
        if not normalized_concept_id:
            return None

        connection = get_db_connection()
        try:
            params = [
                normalized_student_id,
                normalized_area,
                normalized_concept_id,
            ]
            session_filter = ""
            if normalized_session_id:
                session_filter = " AND turns.session_id = ?"
                params.append(normalized_session_id)

            row = connection.execute(
                f"""
                SELECT
                    turns.student_id,
                    turns.session_id,
                    turns.turn_id,
                    turns.area,
                    turns.user_message,
                    turns.assistant_message,
                    turns.concept_id,
                    definition.canonical_name AS concept,
                    turns.created_at
                FROM learning_turns AS turns
                LEFT JOIN concept_definitions AS definition
                  ON definition.area = turns.area
                 AND definition.concept_id = turns.concept_id
                WHERE turns.student_id = ?
                  AND turns.area = ?
                  AND turns.concept_id = ?
                  AND turns.assistant_message IS NOT NULL
                  AND TRIM(turns.assistant_message) != ''
                  {session_filter}
                ORDER BY turns.id DESC
                LIMIT 1
                """,
                tuple(params),
            ).fetchone()
            return dict(row) if row is not None else None
        finally:
            connection.close()

    @classmethod
    def get_messages(
        cls,
        area,
        concept=None,
        concept_id=None,
        limit=MAX_HISTORY_MESSAGES,
        student_id=DEFAULT_STUDENT_ID,
    ):
        normalized_area = cls.normalize_area(area)
        normalized_student_id = normalize_student_id(student_id)
        normalized_concept_id = cls.resolve_concept_id(
            normalized_area,
            concept=concept,
            concept_id=concept_id,
        )
        requested_concept = concept is not None or concept_id is not None
        if requested_concept and not normalized_concept_id:
            return []

        try:
            message_limit = int(limit)
        except (TypeError, ValueError):
            message_limit = MAX_HISTORY_MESSAGES
        message_limit = max(0, min(message_limit, MAX_HISTORY_MESSAGES))
        message_limit -= message_limit % 2
        if message_limit == 0:
            return []
        turn_limit = (message_limit + 1) // 2

        connection = get_db_connection()
        try:
            if normalized_concept_id:
                rows = connection.execute(
                    """
                    SELECT user_message, assistant_message
                    FROM learning_turns
                    WHERE student_id = ?
                      AND area = ?
                      AND concept_id = ?
                      AND assistant_message IS NOT NULL
                      AND TRIM(assistant_message) != ''
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (
                        normalized_student_id,
                        normalized_area,
                        normalized_concept_id,
                        turn_limit,
                    ),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT user_message, assistant_message
                    FROM learning_turns
                    WHERE student_id = ?
                      AND area = ?
                      AND concept_id IS NULL
                      AND assistant_message IS NOT NULL
                      AND TRIM(assistant_message) != ''
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (normalized_student_id, normalized_area, turn_limit),
                ).fetchall()
        finally:
            connection.close()

        messages = []
        for row in reversed(rows):
            messages.extend([
                {
                    "role": "user",
                    "content": str(row["user_message"]).strip()[:cls.MAX_CONTENT_CHARS],
                },
                {
                    "role": "assistant",
                    "content": str(row["assistant_message"]).strip()[:cls.MAX_CONTENT_CHARS],
                },
            ])
        return messages[-message_limit:]
