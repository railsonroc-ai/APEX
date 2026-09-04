from backend.config import MAX_HISTORY_MESSAGES
from backend.database import get_db_connection
from backend.identity import (
    DEFAULT_STUDENT_ID,
    default_session_id,
    normalize_student_id,
)


class LearningHistory:
    """
    Persistência e leitura do histórico confirmado do tutor.

    Somente pares completos de aluno e tutor podem voltar ao
    contexto pedagógico. O navegador não é fonte de verdade.
    """

    ALLOWED_AREAS = {
        "ads",
        "it",
    }

    MAX_CONTENT_CHARS = 4000

    @classmethod
    def normalize_area(cls, area):
        if not isinstance(area, str):
            return "ads"

        normalized = area.strip().lower()

        if normalized not in cls.ALLOWED_AREAS:
            return "ads"

        return normalized

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

        normalized = " ".join(
            str(concept).split()
        )

        return normalized or None

    @staticmethod
    def normalize_session_id(session_id):
        if session_id is None:
            return None

        return str(session_id).strip() or None

    @classmethod
    def find(
        cls,
        turn_id,
        student_id=DEFAULT_STUDENT_ID,
    ):
        normalized_turn_id = cls.normalize_turn_id(
            turn_id
        )
        normalized_student_id = normalize_student_id(
            student_id
        )

        if not normalized_turn_id:
            return None

        connection = get_db_connection()

        try:
            row = connection.execute(
                """
                SELECT
                    student_id,
                    session_id,
                    turn_id,
                    area,
                    user_message,
                    assistant_message,
                    concept,
                    created_at
                FROM learning_turns
                WHERE student_id = ?
                  AND turn_id = ?
                """,
                (
                    normalized_student_id,
                    normalized_turn_id,
                ),
            ).fetchone()

            return (
                dict(row)
                if row is not None
                else None
            )

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
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
    ):
        normalized_turn_id = cls.normalize_turn_id(
            turn_id
        )
        normalized_area = cls.normalize_area(area)
        normalized_user = cls.normalize_message(
            user_message
        )
        normalized_assistant = cls.normalize_message(
            assistant_message
        )
        normalized_concept = cls.normalize_concept(
            concept
        )
        normalized_student_id = normalize_student_id(
            student_id
        )
        normalized_session_id = cls.normalize_session_id(
            session_id
        )

        if (
            not normalized_session_id
            and normalized_student_id == DEFAULT_STUDENT_ID
        ):
            normalized_session_id = default_session_id(
                normalized_area
            )

        if not normalized_turn_id:
            raise ValueError(
                "turn_id obrigatório"
            )

        if not normalized_user:
            raise ValueError(
                "user_message obrigatória"
            )

        if not normalized_session_id:
            raise ValueError(
                "session_id obrigatória"
            )

        connection = get_db_connection()

        try:
            connection.execute(
                """
                INSERT INTO learning_turns (
                    student_id,
                    session_id,
                    turn_id,
                    area,
                    user_message,
                    assistant_message,
                    concept
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
                    normalized_concept,
                ),
            )
            connection.commit()

        finally:
            connection.close()

        return cls.find(
            normalized_turn_id,
            student_id=normalized_student_id,
        )

    @classmethod
    def attach_response(
        cls,
        turn_id,
        assistant_message,
        concept=None,
        student_id=DEFAULT_STUDENT_ID,
    ):
        normalized_turn_id = cls.normalize_turn_id(
            turn_id
        )
        normalized_assistant = cls.normalize_message(
            assistant_message
        )
        normalized_concept = cls.normalize_concept(
            concept
        )
        normalized_student_id = normalize_student_id(
            student_id
        )

        if (
            not normalized_turn_id
            or not normalized_assistant
        ):
            return cls.find(
                normalized_turn_id,
                student_id=normalized_student_id,
            )

        connection = get_db_connection()

        try:
            connection.execute(
                """
                UPDATE learning_turns
                SET
                    assistant_message = ?,
                    concept = COALESCE(
                        concept,
                        ?
                    )
                WHERE student_id = ?
                  AND turn_id = ?
                  AND (
                      assistant_message IS NULL
                      OR TRIM(assistant_message) = ''
                  )
                """,
                (
                    normalized_assistant,
                    normalized_concept,
                    normalized_student_id,
                    normalized_turn_id,
                ),
            )
            connection.commit()

        finally:
            connection.close()

        return cls.find(
            normalized_turn_id,
            student_id=normalized_student_id,
        )

    @classmethod
    def get_messages(
        cls,
        area,
        concept=None,
        limit=MAX_HISTORY_MESSAGES,
        student_id=DEFAULT_STUDENT_ID,
    ):
        normalized_area = cls.normalize_area(area)
        normalized_concept = cls.normalize_concept(
            concept
        )
        normalized_student_id = normalize_student_id(
            student_id
        )

        try:
            message_limit = int(limit)
        except (TypeError, ValueError):
            message_limit = MAX_HISTORY_MESSAGES

        message_limit = max(
            0,
            min(
                message_limit,
                MAX_HISTORY_MESSAGES,
            ),
        )

        message_limit -= (
            message_limit % 2
        )

        if message_limit == 0:
            return []

        turn_limit = (
            message_limit + 1
        ) // 2

        connection = get_db_connection()

        try:
            if normalized_concept:
                rows = connection.execute(
                    """
                    SELECT
                        user_message,
                        assistant_message
                    FROM learning_turns
                    WHERE student_id = ?
                      AND area = ?
                      AND concept = ?
                      AND assistant_message IS NOT NULL
                      AND TRIM(assistant_message) != ''
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (
                        normalized_student_id,
                        normalized_area,
                        normalized_concept,
                        turn_limit,
                    ),
                ).fetchall()

            else:
                rows = connection.execute(
                    """
                    SELECT
                        user_message,
                        assistant_message
                    FROM learning_turns
                    WHERE student_id = ?
                      AND area = ?
                      AND concept IS NULL
                      AND assistant_message IS NOT NULL
                      AND TRIM(assistant_message) != ''
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (
                        normalized_student_id,
                        normalized_area,
                        turn_limit,
                    ),
                ).fetchall()

        finally:
            connection.close()

        messages = []

        for row in reversed(rows):
            messages.extend(
                [
                    {
                        "role": "user",
                        "content": str(
                            row["user_message"]
                        ).strip()[
                            :cls.MAX_CONTENT_CHARS
                        ],
                    },
                    {
                        "role": "assistant",
                        "content": str(
                            row["assistant_message"]
                        ).strip()[
                            :cls.MAX_CONTENT_CHARS
                        ],
                    },
                ]
            )

        return messages[
            -message_limit:
        ]
