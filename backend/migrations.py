from dataclasses import dataclass
from typing import Callable

from backend.identity import (
    DEFAULT_SESSION_IDS,
    DEFAULT_STUDENT_ID,
)


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable


def create_core_schema(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            area TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS learner_state (
            area TEXT PRIMARY KEY,
            current_concept TEXT,
            stage TEXT NOT NULL DEFAULT 'compreender',
            last_evidence TEXT,
            difficulty_count INTEGER NOT NULL DEFAULT 0,
            mastery REAL NOT NULL DEFAULT 0.0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS concept_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area TEXT NOT NULL,
            concept TEXT NOT NULL,
            mastery REAL NOT NULL DEFAULT 0.0,
            difficulty_count INTEGER NOT NULL DEFAULT 0,
            last_evidence TEXT,
            review_count INTEGER NOT NULL DEFAULT 0,
            next_review_at TEXT,
            last_reviewed_at TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(area, concept)
        )
    """)


def create_learning_turns(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS learning_turns (
            turn_id TEXT PRIMARY KEY,
            area TEXT NOT NULL,
            user_message TEXT NOT NULL,
            assistant_message TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)


def add_learning_turn_concept(connection):
    columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(learning_turns)"
        ).fetchall()
    }

    if "concept" not in columns:
        connection.execute(
            """
            ALTER TABLE learning_turns
            ADD COLUMN concept TEXT
            """
        )

    connection.execute("""
        CREATE INDEX IF NOT EXISTS
            idx_learning_turns_area_concept_created_at
        ON learning_turns (
            area,
            concept,
            created_at
        )
    """)


def create_learning_turn_leases(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS learning_turn_leases (
            area TEXT PRIMARY KEY,
            owner_token TEXT NOT NULL UNIQUE,
            acquired_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS
            idx_learning_turn_leases_expires_at
        ON learning_turn_leases (
            expires_at
        )
    """)


def add_student_identity(connection):
    connection.execute("""
        CREATE TABLE students (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE learning_sessions (
            id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            area TEXT NOT NULL,
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ended_at TEXT,
            FOREIGN KEY(student_id)
                REFERENCES students(id),
            UNIQUE(student_id, id, area)
        )
    """)

    connection.execute(
        """
        INSERT INTO students (id)
        VALUES (?)
        """,
        (DEFAULT_STUDENT_ID,),
    )

    connection.executemany(
        """
        INSERT INTO learning_sessions (
            id,
            student_id,
            area
        )
        VALUES (?, ?, ?)
        """,
        [
            (
                DEFAULT_SESSION_IDS["ads"],
                DEFAULT_STUDENT_ID,
                "ads",
            ),
            (
                DEFAULT_SESSION_IDS["it"],
                DEFAULT_STUDENT_ID,
                "it",
            ),
        ],
    )

    connection.execute("""
        CREATE TABLE notes_v5 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            text TEXT NOT NULL,
            area TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id)
                REFERENCES students(id)
        )
    """)

    connection.execute(
        """
        INSERT INTO notes_v5 (
            id,
            student_id,
            text,
            area,
            created_at
        )
        SELECT
            id,
            ?,
            text,
            area,
            created_at
        FROM notes
        """,
        (DEFAULT_STUDENT_ID,),
    )

    connection.execute("""
        CREATE TABLE learner_state_v5 (
            student_id TEXT NOT NULL,
            area TEXT NOT NULL,
            current_concept TEXT,
            stage TEXT NOT NULL DEFAULT 'compreender',
            last_evidence TEXT,
            difficulty_count INTEGER NOT NULL DEFAULT 0,
            mastery REAL NOT NULL DEFAULT 0.0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(student_id, area),
            FOREIGN KEY(student_id)
                REFERENCES students(id)
        )
    """)

    connection.execute(
        """
        INSERT INTO learner_state_v5 (
            student_id,
            area,
            current_concept,
            stage,
            last_evidence,
            difficulty_count,
            mastery,
            updated_at
        )
        SELECT
            ?,
            area,
            current_concept,
            stage,
            last_evidence,
            difficulty_count,
            mastery,
            updated_at
        FROM learner_state
        """,
        (DEFAULT_STUDENT_ID,),
    )

    connection.execute("""
        CREATE TABLE concept_progress_v5 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            area TEXT NOT NULL,
            concept TEXT NOT NULL,
            mastery REAL NOT NULL DEFAULT 0.0,
            difficulty_count INTEGER NOT NULL DEFAULT 0,
            last_evidence TEXT,
            review_count INTEGER NOT NULL DEFAULT 0,
            next_review_at TEXT,
            last_reviewed_at TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id)
                REFERENCES students(id),
            UNIQUE(student_id, area, concept)
        )
    """)

    connection.execute(
        """
        INSERT INTO concept_progress_v5 (
            id,
            student_id,
            area,
            concept,
            mastery,
            difficulty_count,
            last_evidence,
            review_count,
            next_review_at,
            last_reviewed_at,
            updated_at
        )
        SELECT
            id,
            ?,
            area,
            concept,
            mastery,
            difficulty_count,
            last_evidence,
            review_count,
            next_review_at,
            last_reviewed_at,
            updated_at
        FROM concept_progress
        """,
        (DEFAULT_STUDENT_ID,),
    )

    connection.execute("""
        CREATE TABLE learning_turns_v5 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            turn_id TEXT NOT NULL,
            area TEXT NOT NULL,
            user_message TEXT NOT NULL,
            assistant_message TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            concept TEXT,
            FOREIGN KEY(student_id)
                REFERENCES students(id),
            FOREIGN KEY(student_id, session_id, area)
                REFERENCES learning_sessions(
                    student_id,
                    id,
                    area
                ),
            UNIQUE(student_id, turn_id)
        )
    """)

    connection.execute(
        """
        INSERT INTO learning_turns_v5 (
            student_id,
            session_id,
            turn_id,
            area,
            user_message,
            assistant_message,
            created_at,
            concept
        )
        SELECT
            ?,
            CASE
                WHEN area = 'it' THEN ?
                ELSE ?
            END,
            turn_id,
            area,
            user_message,
            assistant_message,
            created_at,
            concept
        FROM learning_turns
        """,
        (
            DEFAULT_STUDENT_ID,
            DEFAULT_SESSION_IDS["it"],
            DEFAULT_SESSION_IDS["ads"],
        ),
    )

    connection.execute("""
        CREATE TABLE learning_turn_leases_v5 (
            student_id TEXT NOT NULL,
            area TEXT NOT NULL,
            owner_token TEXT NOT NULL,
            acquired_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            PRIMARY KEY(student_id, area),
            FOREIGN KEY(student_id)
                REFERENCES students(id),
            UNIQUE(student_id, owner_token)
        )
    """)

    connection.execute(
        """
        INSERT INTO learning_turn_leases_v5 (
            student_id,
            area,
            owner_token,
            acquired_at,
            expires_at
        )
        SELECT
            ?,
            area,
            owner_token,
            acquired_at,
            expires_at
        FROM learning_turn_leases
        """,
        (DEFAULT_STUDENT_ID,),
    )

    connection.execute(
        "DROP INDEX IF EXISTS "
        "idx_learning_turns_area_concept_created_at"
    )
    connection.execute(
        "DROP INDEX IF EXISTS "
        "idx_learning_turn_leases_expires_at"
    )

    connection.execute("DROP TABLE notes")
    connection.execute("DROP TABLE learner_state")
    connection.execute("DROP TABLE concept_progress")
    connection.execute("DROP TABLE learning_turns")
    connection.execute("DROP TABLE learning_turn_leases")

    connection.execute(
        "ALTER TABLE notes_v5 RENAME TO notes"
    )
    connection.execute(
        "ALTER TABLE learner_state_v5 "
        "RENAME TO learner_state"
    )
    connection.execute(
        "ALTER TABLE concept_progress_v5 "
        "RENAME TO concept_progress"
    )
    connection.execute(
        "ALTER TABLE learning_turns_v5 "
        "RENAME TO learning_turns"
    )
    connection.execute(
        "ALTER TABLE learning_turn_leases_v5 "
        "RENAME TO learning_turn_leases"
    )

    connection.execute("""
        CREATE INDEX
            idx_notes_student_area_created_at
        ON notes (
            student_id,
            area,
            created_at
        )
    """)

    connection.execute("""
        CREATE INDEX
            idx_concept_progress_student_area_review
        ON concept_progress (
            student_id,
            area,
            next_review_at
        )
    """)

    connection.execute("""
        CREATE INDEX
            idx_learning_turns_student_area_concept_created_at
        ON learning_turns (
            student_id,
            area,
            concept,
            created_at
        )
    """)

    connection.execute("""
        CREATE INDEX
            idx_learning_turns_session_created_at
        ON learning_turns (
            student_id,
            session_id,
            created_at
        )
    """)

    connection.execute("""
        CREATE INDEX
            idx_learning_turn_leases_expires_at
        ON learning_turn_leases (
            expires_at
        )
    """)

    connection.execute("""
        CREATE INDEX
            idx_learning_sessions_student_area_started_at
        ON learning_sessions (
            student_id,
            area,
            started_at
        )
    """)


def create_evidence_events(connection):
    connection.execute("""
        CREATE TABLE evidence_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            student_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            turn_id TEXT NOT NULL,
            area TEXT NOT NULL,
            concept TEXT NOT NULL,
            stage_before TEXT NOT NULL,
            stage_after TEXT NOT NULL,
            outcome TEXT NOT NULL,
            confidence REAL NOT NULL,
            evidence_text TEXT,
            tutor_message TEXT NOT NULL,
            student_answer TEXT NOT NULL,
            assistance_level TEXT NOT NULL DEFAULT 'untracked',
            artifact_ref TEXT,
            rubric_id TEXT NOT NULL,
            rubric_version INTEGER NOT NULL,
            policy_id TEXT NOT NULL,
            policy_version INTEGER NOT NULL,
            source TEXT NOT NULL,
            applied INTEGER NOT NULL,
            mastery_before REAL NOT NULL,
            mastery_after REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id)
                REFERENCES students(id),
            FOREIGN KEY(student_id, session_id, area)
                REFERENCES learning_sessions(
                    student_id,
                    id,
                    area
                ),
            FOREIGN KEY(student_id, turn_id)
                REFERENCES learning_turns(
                    student_id,
                    turn_id
                ),
            UNIQUE(student_id, turn_id),
            CHECK(area IN ('ads', 'it')),
            CHECK(outcome IN (
                'insufficient',
                'partial',
                'demonstrated',
                'misconception'
            )),
            CHECK(confidence >= 0.0 AND confidence <= 1.0),
            CHECK(assistance_level IN (
                'untracked',
                'independent',
                'light',
                'guided',
                'direct'
            )),
            CHECK(rubric_version > 0),
            CHECK(policy_version > 0),
            CHECK(applied IN (0, 1)),
            CHECK(mastery_before >= 0.0 AND mastery_before <= 1.0),
            CHECK(mastery_after >= 0.0 AND mastery_after <= 1.0)
        )
    """)

    connection.execute("""
        CREATE INDEX idx_evidence_events_student_concept_created
        ON evidence_events (
            student_id,
            area,
            concept,
            created_at
        )
    """)

    connection.execute("""
        CREATE INDEX idx_evidence_events_policy
        ON evidence_events (
            policy_id,
            policy_version,
            created_at
        )
    """)

    connection.execute("""
        CREATE TRIGGER evidence_events_no_update
        BEFORE UPDATE ON evidence_events
        BEGIN
            SELECT RAISE(ABORT, 'evidence_events are immutable');
        END
    """)

    connection.execute("""
        CREATE TRIGGER evidence_events_no_delete
        BEFORE DELETE ON evidence_events
        BEGIN
            SELECT RAISE(ABORT, 'evidence_events are immutable');
        END
    """)


MIGRATIONS = (
    Migration(
        1,
        "create_core_schema",
        create_core_schema,
    ),
    Migration(
        2,
        "create_learning_turns",
        create_learning_turns,
    ),
    Migration(
        3,
        "add_learning_turn_concept",
        add_learning_turn_concept,
    ),
    Migration(
        4,
        "create_learning_turn_leases",
        create_learning_turn_leases,
    ),
    Migration(
        5,
        "add_student_identity",
        add_student_identity,
    ),
    Migration(
        6,
        "create_evidence_events",
        create_evidence_events,
    ),
)


def validate_migrations(migrations):
    versions = [
        migration.version
        for migration in migrations
    ]

    if (
        versions != sorted(versions)
        or len(versions) != len(set(versions))
        or any(version <= 0 for version in versions)
    ):
        raise MigrationError(
            "Migrações devem ter versões positivas, "
            "únicas e ordenadas."
        )


def validate_applied_migrations(connection, migrations):
    known = {
        migration.version: migration.name
        for migration in migrations
    }

    rows = connection.execute(
        """
        SELECT version, name
        FROM schema_migrations
        ORDER BY version
        """
    ).fetchall()

    for row in rows:
        version = row["version"]
        applied_name = row["name"]
        expected_name = known.get(version)

        if expected_name is None:
            raise MigrationError(
                "Banco possui migração desconhecida: "
                f"{version}."
            )

        if applied_name != expected_name:
            raise MigrationError(
                "Migração aplicada não corresponde "
                f"ao código: {version}."
            )


def run_migrations(connection):
    migrations = tuple(MIGRATIONS)
    validate_migrations(migrations)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.commit()

    validate_applied_migrations(
        connection,
        migrations,
    )

    for migration in migrations:
        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            applied = connection.execute(
                """
                SELECT name
                FROM schema_migrations
                WHERE version = ?
                """,
                (migration.version,),
            ).fetchone()

            if applied is not None:
                if applied["name"] != migration.name:
                    raise MigrationError(
                        "Migração aplicada não corresponde "
                        f"ao código: {migration.version}."
                    )

                connection.commit()
                continue

            migration.apply(connection)

            connection.execute(
                """
                INSERT INTO schema_migrations (
                    version,
                    name
                )
                VALUES (?, ?)
                """,
                (
                    migration.version,
                    migration.name,
                ),
            )

            connection.commit()

        except Exception as exc:
            connection.rollback()

            if isinstance(exc, MigrationError):
                raise

            raise MigrationError(
                "Falha ao aplicar migração "
                f"{migration.version}: "
                f"{migration.name}."
            ) from exc
