from dataclasses import dataclass
from typing import Callable


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
