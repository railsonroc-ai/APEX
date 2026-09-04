import sqlite3

import backend.services.concept_progress as concept_progress_module
from backend.services.concept_progress import ConceptProgress


def create_concept_progress_database(path):
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("""
        CREATE TABLE concept_progress (
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
            updated_at TEXT,
            UNIQUE(student_id, area, concept)
        )
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
    assert state["concept"] == "variáveis"
    assert state["mastery"] == 0.0
    assert state["difficulty_count"] == 0
    assert state["review_count"] == 0
    assert state["next_review_at"] is None


def test_update_persists_concept_progress(monkeypatch, tmp_path):
    path = tmp_path / "concept-progress-update.db"
    create_concept_progress_database(path)
    use_test_database(monkeypatch, path)
    state = ConceptProgress.update(
        "ads",
        "variáveis",
        mastery=0.7,
        difficulty_count=1,
        last_evidence="Explicou corretamente.",
    )
    assert state["concept"] == "variáveis"
    assert state["mastery"] == 0.7
    assert state["difficulty_count"] == 1
    assert state["last_evidence"] == "Explicou corretamente."


def test_partial_update_preserves_existing_values(monkeypatch, tmp_path):
    path = tmp_path / "concept-progress-partial.db"
    create_concept_progress_database(path)
    use_test_database(monkeypatch, path)
    ConceptProgress.update(
        "ads",
        "variáveis",
        mastery=0.7,
        difficulty_count=1,
        last_evidence="Explicou corretamente.",
    )
    state = ConceptProgress.update("ads", "variáveis", review_count=1)
    assert state["mastery"] == 0.7
    assert state["difficulty_count"] == 1
    assert state["last_evidence"] == "Explicou corretamente."
    assert state["review_count"] == 1


def test_invalid_progress_values_are_normalized(monkeypatch, tmp_path):
    path = tmp_path / "concept-progress-normalize.db"
    create_concept_progress_database(path)
    use_test_database(monkeypatch, path)
    state = ConceptProgress.update(
        "area-invalida",
        "variáveis",
        mastery=9,
        difficulty_count=-3,
        review_count=-2,
    )
    assert state["area"] == "ads"
    assert state["mastery"] == 1.0
    assert state["difficulty_count"] == 0
    assert state["review_count"] == 0

def test_list_scheduled_returns_only_scheduled_concepts(monkeypatch, tmp_path):
    path = tmp_path / "concept-scheduled.db"
    create_concept_progress_database(path)
    use_test_database(monkeypatch, path)

    ConceptProgress.update(
        "ads",
        "variáveis",
        next_review_at="2026-09-04T12:00:00+00:00",
    )
    ConceptProgress.update(
        "ads",
        "condicionais",
        next_review_at="2026-09-06T12:00:00+00:00",
    )
    ConceptProgress.update(
        "ads",
        "funções",
    )

    scheduled = ConceptProgress.list_scheduled("ads")

    assert [item["concept"] for item in scheduled] == [
        "variáveis",
        "condicionais",
    ]
