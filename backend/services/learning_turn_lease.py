from datetime import datetime, timedelta, timezone

from backend.config import TURN_LEASE_SECONDS
from backend.database import (
    get_db_connection,
    transaction,
)


class LearningTurnLease:
    """
    Reserva cross-process para o turno pedagógico.

    A linha é persistida apenas enquanto o turno está sendo
    processado. A expiração permite recuperação caso um worker
    seja interrompido antes de liberar a reserva.
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
    ):
        normalized_area = cls.normalize_area(
            area
        )
        normalized_owner = (
            cls.normalize_owner_token(
                owner_token
            )
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
                    area,
                    owner_token,
                    acquired_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (
                    normalized_area,
                    normalized_owner,
                    current_text,
                    expires_text,
                ),
            )

            return cursor.rowcount == 1

    @classmethod
    def release(cls, area, owner_token):
        normalized_area = cls.normalize_area(
            area
        )
        normalized_owner = (
            cls.normalize_owner_token(
                owner_token
            )
        )

        if not normalized_owner:
            return False

        with transaction() as connection:
            cursor = connection.execute(
                """
                DELETE FROM learning_turn_leases
                WHERE area = ?
                  AND owner_token = ?
                """,
                (
                    normalized_area,
                    normalized_owner,
                ),
            )

            return cursor.rowcount == 1

    @classmethod
    def get(cls, area):
        normalized_area = cls.normalize_area(
            area
        )
        connection = get_db_connection()

        try:
            row = connection.execute(
                """
                SELECT
                    area,
                    owner_token,
                    acquired_at,
                    expires_at
                FROM learning_turn_leases
                WHERE area = ?
                """,
                (normalized_area,),
            ).fetchone()

            return (
                dict(row)
                if row is not None
                else None
            )

        finally:
            connection.close()
