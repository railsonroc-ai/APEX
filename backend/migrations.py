from dataclasses import dataclass
from typing import Callable

from backend.identity import (
    DEFAULT_SESSION_IDS,
    DEFAULT_STUDENT_ID,
)
from backend.concepts import (
    CATALOG_VERSION,
    CATALOG_V2_VERSION,
    CATALOG_V2_SEEDS,
    CATALOG_V3_VERSION,
    CATALOG_V3_SEEDS,
    CATALOG_V4_VERSION,
    CATALOG_V4_SEEDS,
    CONCEPT_SEEDS,
    CATALOG_V1_VERSION,
    CORE_CONCEPT_SEEDS,
    legacy_canonical_name,
    legacy_concept_id,
    normalize_alias,
    seed_for_value,
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



def add_concept_catalog(connection):
    connection.execute("""
        CREATE TABLE concept_definitions (
            concept_id TEXT PRIMARY KEY,
            area TEXT NOT NULL,
            canonical_name TEXT NOT NULL,
            catalog_version INTEGER NOT NULL,
            selectable INTEGER NOT NULL DEFAULT 1,
            source TEXT NOT NULL DEFAULT 'seed',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(area, concept_id),
            UNIQUE(area, canonical_name),
            CHECK(area IN ('ads', 'it')),
            CHECK(catalog_version > 0),
            CHECK(selectable IN (0, 1)),
            CHECK(source IN ('seed', 'legacy_migration'))
        )
    """)

    connection.execute("""
        CREATE TABLE concept_aliases (
            area TEXT NOT NULL,
            normalized_alias TEXT NOT NULL,
            concept_id TEXT NOT NULL,
            catalog_version INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(area, normalized_alias),
            FOREIGN KEY(area, concept_id)
                REFERENCES concept_definitions(area, concept_id),
            CHECK(area IN ('ads', 'it')),
            CHECK(catalog_version > 0)
        )
    """)

    # A migration histórica permanece congelada no catálogo que existia na v1.
    for seed in CORE_CONCEPT_SEEDS:
        connection.execute(
            """
            INSERT INTO concept_definitions (
                concept_id,
                area,
                canonical_name,
                catalog_version,
                selectable,
                source
            )
            VALUES (?, ?, ?, ?, 1, 'seed')
            """,
            (
                seed.concept_id,
                seed.area,
                seed.canonical_name,
                CATALOG_V1_VERSION,
            ),
        )

        for alias in (
            seed.canonical_name,
            *seed.aliases,
        ):
            normalized = normalize_alias(alias)
            if not normalized:
                continue
            connection.execute(
                """
                INSERT OR IGNORE INTO concept_aliases (
                    area,
                    normalized_alias,
                    concept_id,
                    catalog_version
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    seed.area,
                    normalized,
                    seed.concept_id,
                    CATALOG_V1_VERSION,
                ),
            )

    legacy_values = []
    legacy_values.extend(
        connection.execute(
            """
            SELECT area, current_concept AS concept
            FROM learner_state
            WHERE current_concept IS NOT NULL
              AND TRIM(current_concept) != ''
            """
        ).fetchall()
    )
    legacy_values.extend(
        connection.execute(
            """
            SELECT area, concept
            FROM concept_progress
            WHERE concept IS NOT NULL
              AND TRIM(concept) != ''
            """
        ).fetchall()
    )
    legacy_values.extend(
        connection.execute(
            """
            SELECT area, concept
            FROM learning_turns
            WHERE concept IS NOT NULL
              AND TRIM(concept) != ''
            """
        ).fetchall()
    )
    legacy_values.extend(
        connection.execute(
            """
            SELECT area, concept
            FROM evidence_events
            WHERE concept IS NOT NULL
              AND TRIM(concept) != ''
            """
        ).fetchall()
    )

    def resolve_legacy(area, value):
        if value is None or not str(value).strip():
            return None

        seed = seed_for_value(area, str(value))
        if seed is not None:
            return seed.concept_id

        concept_id = legacy_concept_id(area, str(value))
        connection.execute(
            """
            INSERT OR IGNORE INTO concept_definitions (
                concept_id,
                area,
                canonical_name,
                catalog_version,
                selectable,
                source
            )
            VALUES (?, ?, ?, ?, 0, 'legacy_migration')
            """,
            (
                concept_id,
                area,
                legacy_canonical_name(concept_id),
                CATALOG_V1_VERSION,
            ),
        )

        normalized = normalize_alias(str(value))
        if normalized:
            connection.execute(
                """
                INSERT OR IGNORE INTO concept_aliases (
                    area,
                    normalized_alias,
                    concept_id,
                    catalog_version
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    area,
                    normalized,
                    concept_id,
                    CATALOG_V1_VERSION,
                ),
            )
        return concept_id

    for row in legacy_values:
        resolve_legacy(row["area"], row["concept"])

    connection.execute("""
        CREATE TABLE learner_state_v7 (
            student_id TEXT NOT NULL,
            area TEXT NOT NULL,
            current_concept_id TEXT,
            stage TEXT NOT NULL DEFAULT 'compreender',
            last_evidence TEXT,
            difficulty_count INTEGER NOT NULL DEFAULT 0,
            mastery REAL NOT NULL DEFAULT 0.0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(student_id, area),
            FOREIGN KEY(student_id)
                REFERENCES students(id),
            FOREIGN KEY(area, current_concept_id)
                REFERENCES concept_definitions(area, concept_id)
        )
    """)

    for row in connection.execute(
        "SELECT * FROM learner_state"
    ).fetchall():
        connection.execute(
            """
            INSERT INTO learner_state_v7 (
                student_id,
                area,
                current_concept_id,
                stage,
                last_evidence,
                difficulty_count,
                mastery,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["student_id"],
                row["area"],
                resolve_legacy(row["area"], row["current_concept"]),
                row["stage"],
                row["last_evidence"],
                row["difficulty_count"],
                row["mastery"],
                row["updated_at"],
            ),
        )

    connection.execute("""
        CREATE TABLE concept_progress_v7 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            area TEXT NOT NULL,
            concept_id TEXT NOT NULL,
            mastery REAL NOT NULL DEFAULT 0.0,
            difficulty_count INTEGER NOT NULL DEFAULT 0,
            last_evidence TEXT,
            review_count INTEGER NOT NULL DEFAULT 0,
            next_review_at TEXT,
            last_reviewed_at TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id)
                REFERENCES students(id),
            FOREIGN KEY(area, concept_id)
                REFERENCES concept_definitions(area, concept_id),
            UNIQUE(student_id, area, concept_id)
        )
    """)

    for row in connection.execute(
        "SELECT * FROM concept_progress"
    ).fetchall():
        connection.execute(
            """
            INSERT INTO concept_progress_v7 (
                id,
                student_id,
                area,
                concept_id,
                mastery,
                difficulty_count,
                last_evidence,
                review_count,
                next_review_at,
                last_reviewed_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id, area, concept_id) DO UPDATE SET
                mastery = MAX(
                    concept_progress_v7.mastery,
                    excluded.mastery
                ),
                difficulty_count = MAX(
                    concept_progress_v7.difficulty_count,
                    excluded.difficulty_count
                ),
                last_evidence = CASE
                    WHEN excluded.updated_at >= concept_progress_v7.updated_at
                         AND excluded.last_evidence IS NOT NULL
                    THEN excluded.last_evidence
                    ELSE concept_progress_v7.last_evidence
                END,
                review_count = MAX(
                    concept_progress_v7.review_count,
                    excluded.review_count
                ),
                next_review_at = CASE
                    WHEN concept_progress_v7.next_review_at IS NULL
                    THEN excluded.next_review_at
                    WHEN excluded.next_review_at IS NULL
                    THEN concept_progress_v7.next_review_at
                    WHEN excluded.next_review_at < concept_progress_v7.next_review_at
                    THEN excluded.next_review_at
                    ELSE concept_progress_v7.next_review_at
                END,
                last_reviewed_at = CASE
                    WHEN concept_progress_v7.last_reviewed_at IS NULL
                    THEN excluded.last_reviewed_at
                    WHEN excluded.last_reviewed_at IS NULL
                    THEN concept_progress_v7.last_reviewed_at
                    WHEN excluded.last_reviewed_at > concept_progress_v7.last_reviewed_at
                    THEN excluded.last_reviewed_at
                    ELSE concept_progress_v7.last_reviewed_at
                END,
                updated_at = CASE
                    WHEN excluded.updated_at > concept_progress_v7.updated_at
                    THEN excluded.updated_at
                    ELSE concept_progress_v7.updated_at
                END
            """,
            (
                row["id"],
                row["student_id"],
                row["area"],
                resolve_legacy(row["area"], row["concept"]),
                row["mastery"],
                row["difficulty_count"],
                row["last_evidence"],
                row["review_count"],
                row["next_review_at"],
                row["last_reviewed_at"],
                row["updated_at"],
            ),
        )

    connection.execute("""
        CREATE TABLE learning_turns_v7 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            turn_id TEXT NOT NULL,
            area TEXT NOT NULL,
            user_message TEXT NOT NULL,
            assistant_message TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            concept_id TEXT,
            FOREIGN KEY(student_id)
                REFERENCES students(id),
            FOREIGN KEY(student_id, session_id, area)
                REFERENCES learning_sessions(student_id, id, area),
            FOREIGN KEY(area, concept_id)
                REFERENCES concept_definitions(area, concept_id),
            UNIQUE(student_id, turn_id)
        )
    """)

    for row in connection.execute(
        "SELECT * FROM learning_turns"
    ).fetchall():
        connection.execute(
            """
            INSERT INTO learning_turns_v7 (
                id,
                student_id,
                session_id,
                turn_id,
                area,
                user_message,
                assistant_message,
                created_at,
                concept_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["student_id"],
                row["session_id"],
                row["turn_id"],
                row["area"],
                row["user_message"],
                row["assistant_message"],
                row["created_at"],
                resolve_legacy(row["area"], row["concept"]),
            ),
        )

    connection.execute("""
        CREATE TABLE evidence_events_v7 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            student_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            turn_id TEXT NOT NULL,
            area TEXT NOT NULL,
            concept_id TEXT NOT NULL,
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
                REFERENCES learning_sessions(student_id, id, area),
            FOREIGN KEY(student_id, turn_id)
                REFERENCES learning_turns_v7(student_id, turn_id),
            FOREIGN KEY(area, concept_id)
                REFERENCES concept_definitions(area, concept_id),
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

    for row in connection.execute(
        "SELECT * FROM evidence_events"
    ).fetchall():
        connection.execute(
            """
            INSERT INTO evidence_events_v7 (
                id,
                event_id,
                student_id,
                session_id,
                turn_id,
                area,
                concept_id,
                stage_before,
                stage_after,
                outcome,
                confidence,
                evidence_text,
                tutor_message,
                student_answer,
                assistance_level,
                artifact_ref,
                rubric_id,
                rubric_version,
                policy_id,
                policy_version,
                source,
                applied,
                mastery_before,
                mastery_after,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["event_id"],
                row["student_id"],
                row["session_id"],
                row["turn_id"],
                row["area"],
                resolve_legacy(row["area"], row["concept"]),
                row["stage_before"],
                row["stage_after"],
                row["outcome"],
                row["confidence"],
                row["evidence_text"],
                row["tutor_message"],
                row["student_answer"],
                row["assistance_level"],
                row["artifact_ref"],
                row["rubric_id"],
                row["rubric_version"],
                row["policy_id"],
                row["policy_version"],
                row["source"],
                row["applied"],
                row["mastery_before"],
                row["mastery_after"],
                row["created_at"],
            ),
        )

    for index_name in (
        "idx_concept_progress_student_area_review",
        "idx_learning_turns_student_area_concept_created_at",
        "idx_learning_turns_session_created_at",
        "idx_evidence_events_student_concept_created",
        "idx_evidence_events_policy",
    ):
        connection.execute(f"DROP INDEX IF EXISTS {index_name}")

    connection.execute("DROP TRIGGER IF EXISTS evidence_events_no_update")
    connection.execute("DROP TRIGGER IF EXISTS evidence_events_no_delete")

    connection.execute("DROP TABLE evidence_events")
    connection.execute("DROP TABLE learning_turns")
    connection.execute("DROP TABLE concept_progress")
    connection.execute("DROP TABLE learner_state")

    connection.execute(
        "ALTER TABLE learner_state_v7 RENAME TO learner_state"
    )
    connection.execute(
        "ALTER TABLE concept_progress_v7 RENAME TO concept_progress"
    )
    connection.execute(
        "ALTER TABLE learning_turns_v7 RENAME TO learning_turns"
    )
    connection.execute(
        "ALTER TABLE evidence_events_v7 RENAME TO evidence_events"
    )

    connection.execute("""
        CREATE INDEX idx_concept_progress_student_area_review
        ON concept_progress (
            student_id,
            area,
            next_review_at
        )
    """)

    connection.execute("""
        CREATE INDEX idx_learning_turns_student_area_concept_created_at
        ON learning_turns (
            student_id,
            area,
            concept_id,
            created_at
        )
    """)

    connection.execute("""
        CREATE INDEX idx_learning_turns_session_created_at
        ON learning_turns (
            student_id,
            session_id,
            created_at
        )
    """)

    connection.execute("""
        CREATE INDEX idx_evidence_events_student_concept_created
        ON evidence_events (
            student_id,
            area,
            concept_id,
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



def create_mastery_assessments(connection):
    connection.execute("""
        CREATE UNIQUE INDEX idx_evidence_events_student_event
        ON evidence_events (
            student_id,
            event_id
        )
    """)

    connection.execute("""
        CREATE TABLE mastery_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id TEXT NOT NULL UNIQUE,
            student_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            turn_id TEXT NOT NULL,
            evidence_event_id TEXT NOT NULL UNIQUE,
            area TEXT NOT NULL,
            concept_id TEXT NOT NULL,
            score REAL NOT NULL,
            can_complete INTEGER NOT NULL,
            applied_evidence_count INTEGER NOT NULL,
            demonstrated_count INTEGER NOT NULL,
            demonstrated_stage_count INTEGER NOT NULL,
            retention_demonstrated_count INTEGER NOT NULL,
            low_assistance_demonstrated_count INTEGER NOT NULL,
            latest_outcome TEXT,
            recommended_stage TEXT,
            blockers_json TEXT NOT NULL DEFAULT '[]',
            policy_id TEXT NOT NULL,
            policy_version INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id)
                REFERENCES students(id),
            FOREIGN KEY(student_id, session_id, area)
                REFERENCES learning_sessions(student_id, id, area),
            FOREIGN KEY(student_id, turn_id)
                REFERENCES learning_turns(student_id, turn_id),
            FOREIGN KEY(student_id, evidence_event_id)
                REFERENCES evidence_events(student_id, event_id),
            FOREIGN KEY(area, concept_id)
                REFERENCES concept_definitions(area, concept_id),
            UNIQUE(student_id, turn_id),
            CHECK(area IN ('ads', 'it')),
            CHECK(score >= 0.0 AND score <= 1.0),
            CHECK(can_complete IN (0, 1)),
            CHECK(applied_evidence_count >= 0),
            CHECK(demonstrated_count >= 0),
            CHECK(demonstrated_stage_count >= 0),
            CHECK(retention_demonstrated_count >= 0),
            CHECK(low_assistance_demonstrated_count >= 0),
            CHECK(latest_outcome IS NULL OR latest_outcome IN (
                'insufficient',
                'partial',
                'demonstrated',
                'misconception'
            )),
            CHECK(recommended_stage IS NULL OR recommended_stage IN ('testar')),
            CHECK(policy_version > 0)
        )
    """)

    connection.execute("""
        CREATE INDEX idx_mastery_assessments_student_concept_created
        ON mastery_assessments (
            student_id,
            area,
            concept_id,
            created_at
        )
    """)

    connection.execute("""
        CREATE INDEX idx_mastery_assessments_policy
        ON mastery_assessments (
            policy_id,
            policy_version,
            created_at
        )
    """)

    connection.execute("""
        CREATE TRIGGER mastery_assessments_no_update
        BEFORE UPDATE ON mastery_assessments
        BEGIN
            SELECT RAISE(ABORT, 'mastery_assessments are immutable');
        END
    """)

    connection.execute("""
        CREATE TRIGGER mastery_assessments_no_delete
        BEFORE DELETE ON mastery_assessments
        BEGIN
            SELECT RAISE(ABORT, 'mastery_assessments are immutable');
        END
    """)



def create_assistance_events(connection):
    connection.execute("""
        CREATE TABLE assistance_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assistance_id TEXT NOT NULL UNIQUE,
            student_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            turn_id TEXT NOT NULL,
            area TEXT NOT NULL,
            concept_id TEXT,
            teaching_action TEXT NOT NULL,
            assistance_level TEXT NOT NULL,
            policy_id TEXT NOT NULL,
            policy_version INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id)
                REFERENCES students(id),
            FOREIGN KEY(student_id, session_id, area)
                REFERENCES learning_sessions(student_id, id, area),
            FOREIGN KEY(student_id, turn_id)
                REFERENCES learning_turns(student_id, turn_id),
            FOREIGN KEY(area, concept_id)
                REFERENCES concept_definitions(area, concept_id),
            UNIQUE(student_id, turn_id),
            CHECK(area IN ('ads', 'it')),
            CHECK(teaching_action IN (
                'explicar',
                'verificar',
                'testar',
                'corrigir',
                'consolidar',
                'avancar',
                'revisar'
            )),
            CHECK(assistance_level IN (
                'untracked',
                'independent',
                'light',
                'guided',
                'direct'
            )),
            CHECK(policy_version > 0)
        )
    """)

    connection.execute("""
        CREATE INDEX idx_assistance_events_student_concept_created
        ON assistance_events (
            student_id,
            session_id,
            area,
            concept_id,
            created_at
        )
    """)

    connection.execute("""
        CREATE INDEX idx_assistance_events_policy
        ON assistance_events (
            policy_id,
            policy_version,
            created_at
        )
    """)

    connection.execute("""
        CREATE TRIGGER assistance_events_no_update
        BEFORE UPDATE ON assistance_events
        BEGIN
            SELECT RAISE(ABORT, 'assistance_events are immutable');
        END
    """)

    connection.execute("""
        CREATE TRIGGER assistance_events_no_delete
        BEFORE DELETE ON assistance_events
        BEGIN
            SELECT RAISE(ABORT, 'assistance_events are immutable');
        END
    """)


def create_learning_attempts_and_rubric_assessments(connection):
    connection.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_learning_turns_student_turn_v10
        ON learning_turns (student_id, turn_id)
    """)

    connection.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_events_student_event_v10
        ON evidence_events (student_id, event_id)
    """)

    connection.execute("""
        CREATE TABLE learning_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id TEXT NOT NULL UNIQUE,
            student_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            turn_id TEXT NOT NULL,
            source_turn_id TEXT,
            area TEXT NOT NULL,
            concept_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            attempt_kind TEXT NOT NULL,
            student_answer TEXT NOT NULL,
            artifact_ref TEXT,
            assistance_level TEXT NOT NULL,
            policy_id TEXT NOT NULL,
            policy_version INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id)
                REFERENCES students(id),
            FOREIGN KEY(student_id, session_id, area)
                REFERENCES learning_sessions(student_id, id, area),
            FOREIGN KEY(student_id, turn_id)
                REFERENCES learning_turns(student_id, turn_id),
            FOREIGN KEY(student_id, source_turn_id)
                REFERENCES learning_turns(student_id, turn_id),
            FOREIGN KEY(area, concept_id)
                REFERENCES concept_definitions(area, concept_id),
            UNIQUE(student_id, turn_id),
            CHECK(area IN ('ads', 'it')),
            CHECK(stage IN (
                'compreender',
                'explicar',
                'testar',
                'corrigir',
                'fixar',
                'reencontrar'
            )),
            CHECK(attempt_kind IN (
                'comprehension',
                'explanation',
                'practice',
                'correction',
                'consolidation',
                'retention'
            )),
            CHECK(assistance_level IN (
                'untracked',
                'independent',
                'light',
                'guided',
                'direct'
            )),
            CHECK(policy_version > 0)
        )
    """)

    connection.execute("""
        CREATE UNIQUE INDEX idx_learning_attempts_student_attempt
        ON learning_attempts (student_id, attempt_id)
    """)

    connection.execute("""
        CREATE INDEX idx_learning_attempts_student_concept_created
        ON learning_attempts (
            student_id,
            session_id,
            area,
            concept_id,
            created_at
        )
    """)

    connection.execute("""
        CREATE INDEX idx_learning_attempts_source_turn
        ON learning_attempts (
            student_id,
            source_turn_id
        )
    """)

    connection.execute("""
        CREATE TRIGGER learning_attempts_no_update
        BEFORE UPDATE ON learning_attempts
        BEGIN
            SELECT RAISE(ABORT, 'learning_attempts are immutable');
        END
    """)

    connection.execute("""
        CREATE TRIGGER learning_attempts_no_delete
        BEFORE DELETE ON learning_attempts
        BEGIN
            SELECT RAISE(ABORT, 'learning_attempts are immutable');
        END
    """)

    connection.execute("""
        CREATE TABLE rubric_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id TEXT NOT NULL UNIQUE,
            student_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            turn_id TEXT NOT NULL,
            attempt_id TEXT NOT NULL,
            evidence_event_id TEXT NOT NULL,
            area TEXT NOT NULL,
            concept_id TEXT NOT NULL,
            task_response TEXT NOT NULL,
            conceptual_correctness TEXT NOT NULL,
            understanding_application TEXT NOT NULL,
            criteria_complete INTEGER NOT NULL,
            outcome TEXT NOT NULL,
            outcome_source TEXT NOT NULL,
            confidence REAL NOT NULL,
            rubric_id TEXT NOT NULL,
            rubric_version INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id)
                REFERENCES students(id),
            FOREIGN KEY(student_id, session_id, area)
                REFERENCES learning_sessions(student_id, id, area),
            FOREIGN KEY(student_id, turn_id)
                REFERENCES learning_turns(student_id, turn_id),
            FOREIGN KEY(student_id, attempt_id)
                REFERENCES learning_attempts(student_id, attempt_id),
            FOREIGN KEY(student_id, evidence_event_id)
                REFERENCES evidence_events(student_id, event_id),
            FOREIGN KEY(area, concept_id)
                REFERENCES concept_definitions(area, concept_id),
            UNIQUE(student_id, turn_id),
            UNIQUE(student_id, attempt_id),
            UNIQUE(student_id, evidence_event_id),
            CHECK(area IN ('ads', 'it')),
            CHECK(task_response IN ('met', 'partial', 'not_met', 'unknown')),
            CHECK(conceptual_correctness IN ('met', 'partial', 'not_met', 'unknown')),
            CHECK(understanding_application IN ('met', 'partial', 'not_met', 'unknown')),
            CHECK(criteria_complete IN (0, 1)),
            CHECK(outcome IN (
                'insufficient',
                'partial',
                'demonstrated',
                'misconception'
            )),
            CHECK(outcome_source IN (
                'rubric',
                'legacy_outcome',
                'rubric_incomplete'
            )),
            CHECK(confidence >= 0.0 AND confidence <= 1.0),
            CHECK(rubric_version > 0)
        )
    """)

    connection.execute("""
        CREATE INDEX idx_rubric_assessments_student_concept_created
        ON rubric_assessments (
            student_id,
            session_id,
            area,
            concept_id,
            created_at
        )
    """)

    connection.execute("""
        CREATE INDEX idx_rubric_assessments_rubric
        ON rubric_assessments (
            rubric_id,
            rubric_version,
            created_at
        )
    """)

    connection.execute("""
        CREATE TRIGGER rubric_assessments_no_update
        BEFORE UPDATE ON rubric_assessments
        BEGIN
            SELECT RAISE(ABORT, 'rubric_assessments are immutable');
        END
    """)

    connection.execute("""
        CREATE TRIGGER rubric_assessments_no_delete
        BEFORE DELETE ON rubric_assessments
        BEGIN
            SELECT RAISE(ABORT, 'rubric_assessments are immutable');
        END
    """)


def create_learning_tasks(connection):
    connection.execute("""
        CREATE TABLE learning_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL UNIQUE,
            student_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            source_turn_id TEXT NOT NULL,
            area TEXT NOT NULL,
            concept_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            teaching_action TEXT NOT NULL,
            task_kind TEXT NOT NULL,
            prompt_text TEXT NOT NULL,
            assistance_level TEXT NOT NULL,
            rubric_id TEXT NOT NULL,
            rubric_version INTEGER NOT NULL,
            policy_id TEXT NOT NULL,
            policy_version INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id)
                REFERENCES students(id),
            FOREIGN KEY(student_id, session_id, area)
                REFERENCES learning_sessions(student_id, id, area),
            FOREIGN KEY(student_id, source_turn_id)
                REFERENCES learning_turns(student_id, turn_id),
            FOREIGN KEY(area, concept_id)
                REFERENCES concept_definitions(area, concept_id),
            UNIQUE(student_id, source_turn_id),
            CHECK(area IN ('ads', 'it')),
            CHECK(stage IN (
                'ler',
                'compreender',
                'explicar',
                'testar',
                'corrigir',
                'fixar',
                'concluido',
                'reencontrar'
            )),
            CHECK(teaching_action IN (
                'testar',
                'revisar',
                'verificar',
                'consolidar',
                'explicar',
                'corrigir'
            )),
            CHECK(task_kind IN (
                'practice',
                'retention',
                'verification',
                'consolidation',
                'guided_check',
                'correction_retry'
            )),
            CHECK(assistance_level IN (
                'independent',
                'light',
                'guided',
                'direct'
            )),
            CHECK(rubric_version > 0),
            CHECK(policy_version > 0)
        )
    """)

    connection.execute("""
        CREATE UNIQUE INDEX idx_learning_tasks_student_task
        ON learning_tasks (student_id, task_id)
    """)

    connection.execute("""
        CREATE INDEX idx_learning_tasks_student_concept_created
        ON learning_tasks (
            student_id,
            session_id,
            area,
            concept_id,
            created_at
        )
    """)

    connection.execute("""
        CREATE INDEX idx_learning_tasks_policy
        ON learning_tasks (
            policy_id,
            policy_version,
            created_at
        )
    """)

    connection.execute("""
        CREATE TRIGGER learning_tasks_no_update
        BEFORE UPDATE ON learning_tasks
        BEGIN
            SELECT RAISE(ABORT, 'learning_tasks are immutable');
        END
    """)

    connection.execute("""
        CREATE TRIGGER learning_tasks_no_delete
        BEFORE DELETE ON learning_tasks
        BEGIN
            SELECT RAISE(ABORT, 'learning_tasks are immutable');
        END
    """)

    connection.execute("""
        ALTER TABLE learning_attempts
        ADD COLUMN task_id TEXT
            REFERENCES learning_tasks(task_id)
    """)

    connection.execute("""
        CREATE INDEX idx_learning_attempts_task
        ON learning_attempts (student_id, task_id)
    """)

    connection.execute("""
        CREATE TRIGGER learning_attempts_task_scope_insert
        BEFORE INSERT ON learning_attempts
        WHEN NEW.task_id IS NOT NULL
        BEGIN
            SELECT CASE
                WHEN NOT EXISTS (
                    SELECT 1
                    FROM learning_tasks t
                    WHERE t.task_id = NEW.task_id
                      AND t.student_id = NEW.student_id
                      AND t.session_id = NEW.session_id
                      AND t.area = NEW.area
                      AND t.concept_id = NEW.concept_id
                      AND t.source_turn_id = NEW.source_turn_id
                )
                THEN RAISE(ABORT, 'learning_attempt task scope mismatch')
            END;
        END
    """)


def create_learning_session_lifecycle(connection):
    connection.execute("""
        CREATE TABLE learning_session_states (
            student_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            area TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'studying',
            resume_concept_id TEXT,
            resume_stage TEXT,
            review_task_id TEXT,
            paused_at TEXT,
            last_resumed_at TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(student_id, session_id, area),
            FOREIGN KEY(student_id, session_id, area)
                REFERENCES learning_sessions(student_id, id, area),
            FOREIGN KEY(area, resume_concept_id)
                REFERENCES concept_definitions(area, concept_id),
            FOREIGN KEY(review_task_id)
                REFERENCES learning_tasks(task_id),
            CHECK(status IN ('studying', 'paused', 'reviewing')),
            CHECK(resume_stage IS NULL OR resume_stage IN (
                'ler',
                'compreender',
                'explicar',
                'testar',
                'corrigir',
                'fixar',
                'concluido',
                'reencontrar'
            ))
        )
    """)

    connection.execute("""
        INSERT INTO learning_session_states (
            student_id,
            session_id,
            area,
            status
        )
        SELECT student_id, id, area, 'studying'
        FROM learning_sessions
    """)

    connection.execute("""
        CREATE INDEX idx_learning_session_states_status
        ON learning_session_states (
            student_id,
            status,
            area
        )
    """)

    connection.execute("""
        CREATE INDEX idx_learning_session_states_review_task
        ON learning_session_states (
            student_id,
            review_task_id
        )
    """)

    connection.execute("""
        CREATE TRIGGER learning_session_states_review_task_scope_insert
        BEFORE INSERT ON learning_session_states
        WHEN NEW.review_task_id IS NOT NULL
        BEGIN
            SELECT CASE
                WHEN NOT EXISTS (
                    SELECT 1
                    FROM learning_tasks t
                    WHERE t.task_id = NEW.review_task_id
                      AND t.student_id = NEW.student_id
                      AND t.session_id = NEW.session_id
                      AND t.area = NEW.area
                      AND t.concept_id = NEW.resume_concept_id
                )
                THEN RAISE(ABORT, 'session review task scope mismatch')
            END;
        END
    """)

    connection.execute("""
        CREATE TRIGGER learning_session_states_review_task_scope_update
        BEFORE UPDATE OF review_task_id ON learning_session_states
        WHEN NEW.review_task_id IS NOT NULL
        BEGIN
            SELECT CASE
                WHEN NOT EXISTS (
                    SELECT 1
                    FROM learning_tasks t
                    WHERE t.task_id = NEW.review_task_id
                      AND t.student_id = NEW.student_id
                      AND t.session_id = NEW.session_id
                      AND t.area = NEW.area
                      AND t.concept_id = NEW.resume_concept_id
                )
                THEN RAISE(ABORT, 'session review task scope mismatch')
            END;
        END
    """)

    connection.execute("""
        CREATE TABLE learning_session_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            student_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            area TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status_before TEXT NOT NULL,
            status_after TEXT NOT NULL,
            concept_id TEXT,
            stage_snapshot TEXT,
            policy_id TEXT NOT NULL,
            policy_version INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id, session_id, area)
                REFERENCES learning_sessions(student_id, id, area),
            FOREIGN KEY(area, concept_id)
                REFERENCES concept_definitions(area, concept_id),
            CHECK(event_type IN (
                'paused',
                'resumed_direct',
                'resume_review_started',
                'resume_review_completed'
            )),
            CHECK(status_before IN ('studying', 'paused', 'reviewing')),
            CHECK(status_after IN ('studying', 'paused', 'reviewing')),
            CHECK(stage_snapshot IS NULL OR stage_snapshot IN (
                'ler',
                'compreender',
                'explicar',
                'testar',
                'corrigir',
                'fixar',
                'concluido',
                'reencontrar'
            )),
            CHECK(policy_version > 0)
        )
    """)

    connection.execute("""
        CREATE INDEX idx_learning_session_events_session_created
        ON learning_session_events (
            student_id,
            session_id,
            created_at
        )
    """)

    connection.execute("""
        CREATE INDEX idx_learning_session_events_policy
        ON learning_session_events (
            policy_id,
            policy_version,
            created_at
        )
    """)

    connection.execute("""
        CREATE TRIGGER learning_session_events_no_update
        BEFORE UPDATE ON learning_session_events
        BEGIN
            SELECT RAISE(ABORT, 'learning_session_events are immutable');
        END
    """)

    connection.execute("""
        CREATE TRIGGER learning_session_events_no_delete
        BEFORE DELETE ON learning_session_events
        BEGIN
            SELECT RAISE(ABORT, 'learning_session_events are immutable');
        END
    """)


def create_access_control(connection):
    connection.execute("""
        CREATE TABLE access_credentials (
            credential_id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            label TEXT NOT NULL,
            key_hash TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            revoked_at TEXT,
            FOREIGN KEY(student_id)
                REFERENCES students(id),
            CHECK(is_active IN (0, 1)),
            CHECK(length(label) BETWEEN 1 AND 120),
            CHECK(length(key_hash) = 64)
        )
    """)

    connection.execute("""
        CREATE INDEX idx_access_credentials_student_active
        ON access_credentials (
            student_id,
            is_active,
            created_at
        )
    """)

    connection.execute("""
        CREATE TABLE api_rate_limits (
            subject_id TEXT PRIMARY KEY,
            window_started_at INTEGER NOT NULL,
            request_count INTEGER NOT NULL DEFAULT 0,
            CHECK(request_count >= 0),
            CHECK(window_started_at >= 0)
        )
    """)


def enable_privacy_lifecycle(connection):
    connection.execute("""
        CREATE TABLE privacy_deletion_authorizations (
            student_id TEXT PRIMARY KEY,
            receipt_id TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    immutable_tables = (
        ("evidence_events", "evidence_events_no_delete"),
        ("mastery_assessments", "mastery_assessments_no_delete"),
        ("assistance_events", "assistance_events_no_delete"),
        ("learning_attempts", "learning_attempts_no_delete"),
        ("rubric_assessments", "rubric_assessments_no_delete"),
        ("learning_tasks", "learning_tasks_no_delete"),
        ("learning_session_events", "learning_session_events_no_delete"),
    )

    for table, trigger in immutable_tables:
        connection.execute(f"DROP TRIGGER {trigger}")
        connection.execute(
            f"""
            CREATE TRIGGER {trigger}
            BEFORE DELETE ON {table}
            WHEN NOT EXISTS (
                SELECT 1
                FROM privacy_deletion_authorizations p
                WHERE p.student_id = OLD.student_id
            )
            BEGIN
                SELECT RAISE(ABORT, '{table} are immutable');
            END
            """
        )




def _sync_catalog_seeds(connection, seeds, catalog_version):
    for seed in seeds:
        connection.execute(
            """
            INSERT INTO concept_definitions (
                concept_id, area, canonical_name, catalog_version,
                selectable, source
            ) VALUES (?, ?, ?, ?, ?, 'seed')
            ON CONFLICT(concept_id) DO UPDATE SET
                canonical_name = excluded.canonical_name,
                catalog_version = excluded.catalog_version,
                selectable = excluded.selectable,
                source = 'seed'
            """,
            (
                seed.concept_id,
                seed.area,
                seed.canonical_name,
                catalog_version,
                int(seed.selectable),
            ),
        )
        for alias in (seed.canonical_name, *seed.aliases):
            normalized = normalize_alias(alias)
            if not normalized:
                continue
            connection.execute(
                """
                INSERT INTO concept_aliases (
                    area, normalized_alias, concept_id, catalog_version
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(area, normalized_alias) DO UPDATE SET
                    concept_id = excluded.concept_id,
                    catalog_version = excluded.catalog_version
                """,
                (seed.area, normalized, seed.concept_id, catalog_version),
            )


def sync_executable_curriculum_v2(connection):
    """Migration histórica congelada no primeiro nó executável."""

    _sync_catalog_seeds(
        connection,
        CATALOG_V2_SEEDS,
        CATALOG_V2_VERSION,
    )


def sync_executable_curriculum_v3(connection):
    """Migration histórica congelada na segunda microcompetência."""

    _sync_catalog_seeds(
        connection,
        CATALOG_V3_SEEDS,
        CATALOG_V3_VERSION,
    )


def sync_executable_curriculum_v4(connection):
    """Migration histórica congelada na terceira microcompetência."""

    _sync_catalog_seeds(
        connection,
        CATALOG_V4_SEEDS,
        CATALOG_V4_VERSION,
    )


def sync_executable_curriculum_v5(connection):
    """Adiciona representação estruturada como quarta microcompetência."""

    _sync_catalog_seeds(
        connection,
        CONCEPT_SEEDS,
        CATALOG_VERSION,
    )


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
    Migration(
        7,
        "add_concept_catalog",
        add_concept_catalog,
    ),
    Migration(
        8,
        "create_mastery_assessments",
        create_mastery_assessments,
    ),
    Migration(
        9,
        "create_assistance_events",
        create_assistance_events,
    ),
    Migration(
        10,
        "create_learning_attempts_and_rubric_assessments",
        create_learning_attempts_and_rubric_assessments,
    ),
    Migration(
        11,
        "create_learning_tasks",
        create_learning_tasks,
    ),
    Migration(
        12,
        "create_learning_session_lifecycle",
        create_learning_session_lifecycle,
    ),
    Migration(
        13,
        "create_access_control",
        create_access_control,
    ),
    Migration(
        14,
        "enable_privacy_lifecycle",
        enable_privacy_lifecycle,
    ),
    Migration(
        15,
        "sync_executable_curriculum_v2",
        sync_executable_curriculum_v2,
    ),
    Migration(
        16,
        "sync_executable_curriculum_v3",
        sync_executable_curriculum_v3,
    ),
    Migration(
        17,
        "sync_executable_curriculum_v4",
        sync_executable_curriculum_v4,
    ),
    Migration(
        18,
        "sync_executable_curriculum_v5",
        sync_executable_curriculum_v5,
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
