from datetime import datetime, timedelta, timezone

from backend.config import TURN_LEASE_SECONDS
from backend.database import (
    get_db_connection,
    transaction,
)
from backend.identity import (
    DEFAULT_STUDENT_ID,
    normalize_student_id,
)


class LearningTurnLease:
    """
    Reserva cross-process para o turno pedagógico.

    A chave de serialização é student_id + area. Assim, dois
    alunos podem estudar a mesma área em paralelo, enquanto duas
    sessões do mesmo aluno na mesma área continuam serializadas.
    """

    ALLOWED_AREAS = {
        "ads",
        "it",
    }

    MAX_OWNER_TOKEN_CHARS = 128

    @classmethod
    def normalize_area(cls, area):
        if not isinstance(area, str):
            return "ads"

        normalized = area.strip().lower()

        if normalized not in cls.ALLOWED_AREAS:
            return "ads"

        return normalized

    @classmethod
    def normalize_owner_token(cls, owner_token):
        if owner_token is None:
            return None

        normalized = str(owner_token).strip()

        if not normalized:
            return None

        if len(normalized) > cls.MAX_OWNER_TOKEN_CHARS:
            raise ValueError(
                "owner_token inválido"
            )

        return normalized

    @staticmethod
    def normalize_now(now=None):
        if now is None:
            return datetime.now(timezone.utc)

        if now.tzinfo is None:
            return now.replace(
                tzinfo=timezone.utc
            )

        return now.astimezone(
            timezone.utc
        )

    @staticmethod
    def normalize_lease_seconds(value):
        try:
            seconds = int(value)
        except (TypeError, ValueError):
            seconds = TURN_LEASE_SECONDS

        return max(1, seconds)

    @classmethod
    def acquire(
        cls,
        area,
        owner_token,
        now=None,
        lease_seconds=TURN_LEASE_SECONDS,
        student_id=DEFAULT_STUDENT_ID,
    ):
        normalized_area = cls.normalize_area(
            area
        )
        normalized_owner = (
            cls.normalize_owner_token(
                owner_token
            )
        )
        normalized_student_id = normalize_student_id(
            student_id
        )

        if not normalized_owner:
            raise ValueError(
                "owner_token obrigatório"
            )

        current_time = cls.normalize_now(now)
        expires_at = (
            current_time
            + timedelta(
                seconds=(
                    cls.normalize_lease_seconds(
                        lease_seconds
                    )
                )
            )
        )

        current_text = current_time.isoformat(
            timespec="microseconds"
        )
        expires_text = expires_at.isoformat(
            timespec="microseconds"
        )

        with transaction() as connection:
            connection.execute(
                """
                DELETE FROM learning_turn_leases
                WHERE expires_at <= ?
                """,
                (current_text,),
            )

            cursor = connection.execute(
                """
                INSERT INTO learning_turn_leases (
                    student_id,
                    area,
                    owner_token,
                    acquired_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (
                    normalized_student_id,
                    normalized_area,
                    normalized_owner,
                    current_text,
                    expires_text,
                ),
            )

            return cursor.rowcount == 1

    @classmethod
    def release(
        cls,
        area,
        owner_token,
        student_id=DEFAULT_STUDENT_ID,
    ):
        normalized_area = cls.normalize_area(
            area
        )
        normalized_owner = (
            cls.normalize_owner_token(
                owner_token
            )
        )
        normalized_student_id = normalize_student_id(
            student_id
        )

        if not normalized_owner:
            return False

        with transaction() as connection:
            cursor = connection.execute(
                """
                DELETE FROM learning_turn_leases
                WHERE student_id = ?
                  AND area = ?
                  AND owner_token = ?
                """,
                (
                    normalized_student_id,
                    normalized_area,
                    normalized_owner,
                ),
            )

            return cursor.rowcount == 1

    @classmethod
    def get(
        cls,
        area,
        student_id=DEFAULT_STUDENT_ID,
    ):
        normalized_area = cls.normalize_area(
            area
        )
        normalized_student_id = normalize_student_id(
            student_id
        )
        connection = get_db_connection()

        try:
            row = connection.execute(
                """
                SELECT
                    student_id,
                    area,
                    owner_token,
                    acquired_at,
                    expires_at
                FROM learning_turn_leases
                WHERE student_id = ?
                  AND area = ?
                """,
                (
                    normalized_student_id,
                    normalized_area,
                ),
            ).fetchone()

            return (
                dict(row)
                if row is not None
                else None
            )

        finally:
            connection.close()
