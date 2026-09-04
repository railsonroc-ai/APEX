import hashlib
import sqlite3
import time
from uuid import uuid4

from backend.database import get_db_connection
from backend.identity import (
    DEFAULT_STUDENT_ID,
    session_id_for_student,
)


class AccessControl:
    """Credenciais de acesso vinculadas a um aluno.

    A chave em texto puro nunca e persistida. O hash SHA-256 e suficiente para
    API keys de alta entropia e permite lookup deterministico sem expor o
    segredo no SQLite.
    """

    DEFAULT_CREDENTIAL_ID = "credential_default"
    DEFAULT_LABEL = "environment-default"

    @staticmethod
    def hash_key(raw_key):
        normalized = str(raw_key or "").strip()
        if not normalized:
            return None
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @classmethod
    def ensure_default_credential(
        cls,
        raw_key,
        *,
        student_id=DEFAULT_STUDENT_ID,
    ):
        key_hash = cls.hash_key(raw_key)
        if not key_hash:
            return None

        connection = get_db_connection()
        try:
            connection.execute(
                """
                INSERT INTO access_credentials (
                    credential_id,
                    student_id,
                    label,
                    key_hash,
                    is_active,
                    revoked_at
                )
                VALUES (?, ?, ?, ?, 1, NULL)
                ON CONFLICT(credential_id) DO UPDATE SET
                    student_id = excluded.student_id,
                    label = excluded.label,
                    key_hash = excluded.key_hash,
                    is_active = 1,
                    revoked_at = NULL
                """,
                (
                    cls.DEFAULT_CREDENTIAL_ID,
                    student_id,
                    cls.DEFAULT_LABEL,
                    key_hash,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        return cls.DEFAULT_CREDENTIAL_ID

    @classmethod
    def _ensure_student_runtime(cls, connection, student_id):
        connection.execute(
            """
            INSERT INTO students (id)
            VALUES (?)
            ON CONFLICT(id) DO NOTHING
            """,
            (student_id,),
        )

        for area in ("ads", "it"):
            session_id = session_id_for_student(student_id, area)
            connection.execute(
                """
                INSERT INTO learning_sessions (
                    id,
                    student_id,
                    area
                )
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (session_id, student_id, area),
            )
            connection.execute(
                """
                INSERT INTO learning_session_states (
                    student_id,
                    session_id,
                    area,
                    status
                )
                VALUES (?, ?, ?, 'studying')
                ON CONFLICT(student_id, session_id, area) DO NOTHING
                """,
                (student_id, session_id, area),
            )

    @classmethod
    def ensure_student_runtime(cls, student_id):
        normalized_student = str(student_id or "").strip()
        if not normalized_student:
            raise ValueError("student_id obrigatorio")

        connection = get_db_connection()
        try:
            cls._ensure_student_runtime(connection, normalized_student)
            connection.commit()
        finally:
            connection.close()

        return normalized_student

    @classmethod
    def create_credential(cls, student_id, label, raw_key):
        key_hash = cls.hash_key(raw_key)
        normalized_label = str(label or "").strip()
        normalized_student = str(student_id or "").strip()

        if not normalized_student:
            raise ValueError("student_id obrigatorio")
        if not normalized_label:
            raise ValueError("label obrigatorio")
        if not key_hash:
            raise ValueError("chave obrigatoria")

        credential_id = f"credential_{uuid4().hex}"
        connection = get_db_connection()
        try:
            cls._ensure_student_runtime(
                connection,
                normalized_student,
            )
            connection.execute(
                """
                INSERT INTO access_credentials (
                    credential_id,
                    student_id,
                    label,
                    key_hash,
                    is_active
                )
                VALUES (?, ?, ?, ?, 1)
                """,
                (
                    credential_id,
                    normalized_student,
                    normalized_label,
                    key_hash,
                ),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("credencial invalida ou duplicada") from exc
        finally:
            connection.close()

        return credential_id

    @classmethod
    def authenticate(cls, raw_key):
        key_hash = cls.hash_key(raw_key)
        if not key_hash:
            return None

        connection = get_db_connection()
        try:
            row = connection.execute(
                """
                SELECT
                    credential_id,
                    student_id,
                    label
                FROM access_credentials
                WHERE key_hash = ?
                  AND is_active = 1
                LIMIT 1
                """,
                (key_hash,),
            ).fetchone()
        finally:
            connection.close()

        if row is None:
            return None

        return {
            "credential_id": row["credential_id"],
            "student_id": row["student_id"],
            "label": row["label"],
        }

    @classmethod
    def revoke(cls, credential_id):
        connection = get_db_connection()
        try:
            cursor = connection.execute(
                """
                UPDATE access_credentials
                SET
                    is_active = 0,
                    revoked_at = CURRENT_TIMESTAMP
                WHERE credential_id = ?
                  AND is_active = 1
                """,
                (str(credential_id),),
            )
            connection.commit()
            return cursor.rowcount == 1
        finally:
            connection.close()


class AccessRateLimiter:
    """Fixed-window rate limiter persistido em SQLite.

    O estado no banco e compartilhado por todos os workers Gunicorn, evitando
    que cada processo tenha sua propria contagem independente.
    """

    @classmethod
    def allow(
        cls,
        subject_id,
        *,
        limit,
        window_seconds,
        now_epoch=None,
    ):
        normalized_subject = str(subject_id or "").strip()
        if not normalized_subject:
            return False

        limit = int(limit)
        window_seconds = int(window_seconds)
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("limite e janela devem ser positivos")

        now_epoch = int(time.time() if now_epoch is None else now_epoch)
        connection = get_db_connection()

        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT window_started_at, request_count
                FROM api_rate_limits
                WHERE subject_id = ?
                """,
                (normalized_subject,),
            ).fetchone()

            if row is None or now_epoch - int(row["window_started_at"]) >= window_seconds:
                connection.execute(
                    """
                    INSERT INTO api_rate_limits (
                        subject_id,
                        window_started_at,
                        request_count
                    )
                    VALUES (?, ?, 1)
                    ON CONFLICT(subject_id) DO UPDATE SET
                        window_started_at = excluded.window_started_at,
                        request_count = 1
                    """,
                    (normalized_subject, now_epoch),
                )
                allowed = True
            elif int(row["request_count"]) >= limit:
                allowed = False
            else:
                connection.execute(
                    """
                    UPDATE api_rate_limits
                    SET request_count = request_count + 1
                    WHERE subject_id = ?
                    """,
                    (normalized_subject,),
                )
                allowed = True

            connection.commit()
            return allowed
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
