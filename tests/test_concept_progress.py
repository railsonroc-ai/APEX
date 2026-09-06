import sqlite3

import backend.services.concept_progress as concept_progress_module
from backend.services.concept_progress import ConceptProgress


def create_concept_progress_database(path):
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.executescript("""
        CREATE TABLE concept_definitions (
            concept_id TEXT PRIMARY KEY,
            area TEXT NOT NULL,
            canonical_name TEXT NOT NULL,
            catalog_version INTEGER NOT NULL,
            selectable INTEGER NOT NULL,
            source TEXT NOT NULL,
            UNIQUE(area, concept_id)
        );
        INSERT INTO concept_definitions VALUES
            ('ads.variables','ads','variáveis',1,1,'seed'),
            ('ads.conditionals','ads','condicionais',1,1,'seed'),
            ('ads.functions','ads','funções',1,1,'seed');
        CREATE TABLE concept_progress (
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
            updated_at TEXT,
            UNIQUE(student_id, area, concept_id)
        );
    """)
    connection.commit()
    connection.close()


def use_test_database(monkeypatch, path):
    def get_test_connection():
        connection = sqlite3.connect(str(path))
        connection.row_factory = sqlite3.Row
        return connection
    monkeypatch.setattr(concept_progress_module, "get_db_connection", get_test_connection)


def test_default_concept_progress(monkeypatch, tmp_path):
    path = tmp_path / "concept-progress.db"
    create_concept_progress_database(path)
    use_test_database(monkeypatch, path)
    state = ConceptProgress.get("ads", "  variáveis  ")
    assert state["area"] == "ads"
    assert state["concept_id"] == "ads.variables"
    assert state["concept"] == "variáveis"
    assert state["mastery"] == 0.0
    assert state["difficulty_count"] == 0
    assert state["review_count"] == 0
    assert state["next_review_at"] is None


def test_aliases_share_same_progress(monkeypatch, tmp_path):
    path = tmp_path / "concept-progress-update.db"
    create_concept_progress_database(path)
    use_test_database(monkeypatch, path)
    ConceptProgress.update("ads", "variaveis", mastery=0.7)
    state = ConceptProgress.get("ads", "variables")
    assert state["concept_id"] == "ads.variables"
    assert state["mastery"] == 0.7


def test_partial_update_preserves_existing_values(monkeypatch, tmp_path):
    path = tmp_path / "concept-progress-partial.db"
    create_concept_progress_database(path)
    use_test_database(monkeypatch, path)
    ConceptProgress.update(
        "ads", "variáveis", mastery=0.7,
        difficulty_count=1, last_evidence="Explicou corretamente.",
    )
    state = ConceptProgress.update("ads", "ads.variables", review_count=1)
    assert state["mastery"] == 0.7
    assert state["difficulty_count"] == 1
    assert state["last_evidence"] == "Explicou corretamente."
    assert state["review_count"] == 1


def test_invalid_progress_values_are_normalized(monkeypatch, tmp_path):
    path = tmp_path / "concept-progress-normalize.db"
    create_concept_progress_database(path)
    use_test_database(monkeypatch, path)
    state = ConceptProgress.update(
        "area-invalida", "variáveis", mastery=9,
        difficulty_count=-3, review_count=-2,
    )
    assert state["area"] == "ads"
    assert state["mastery"] == 1.0
    assert state["difficulty_count"] == 0
    assert state["review_count"] == 0


def test_list_scheduled_returns_only_scheduled_concepts(monkeypatch, tmp_path):
    path = tmp_path / "concept-scheduled.db"
    create_concept_progress_database(path)
    use_test_database(monkeypatch, path)
    ConceptProgress.update("ads", "variáveis", next_review_at="2026-09-04T12:00:00+00:00")
    ConceptProgress.update("ads", "condicionais", next_review_at="2026-09-06T12:00:00+00:00")
    ConceptProgress.update("ads", "funções")
    scheduled = ConceptProgress.list_scheduled("ads")
    assert [item["concept_id"] for item in scheduled] == [
        "ads.variables", "ads.conditionals",
    ]
    assert [item["concept"] for item in scheduled] == ["variáveis", "condicionais"]


def test_list_all_joins_catalog_with_real_student_progress(monkeypatch, tmp_path):
    path = tmp_path / "concept-list-all.db"
    create_concept_progress_database(path)
    use_test_database(monkeypatch, path)
    ConceptProgress.update(
        "ads",
        "variáveis",
        mastery=0.8,
        difficulty_count=1,
    )

    items = ConceptProgress.list_all("ads")

    assert [item["concept_id"] for item in items] == [
        "ads.conditionals",
        "ads.functions",
        "ads.variables",
    ]
    by_id = {item["concept_id"]: item for item in items}
    assert by_id["ads.variables"]["mastery"] == 0.8
    assert by_id["ads.variables"]["difficulty_count"] == 1
    assert by_id["ads.variables"]["updated_at"] is not None
    assert by_id["ads.functions"]["mastery"] == 0.0
    assert by_id["ads.functions"]["updated_at"] is None
