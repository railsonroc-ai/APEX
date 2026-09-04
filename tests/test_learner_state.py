import sqlite3

import backend.services.learner_state as learner_state_module
from backend.services.learner_state import LearnerState


def create_learner_database(path):
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
            ('ads.variables','ads','variáveis',1,1,'seed');
        CREATE TABLE learner_state (
            student_id TEXT NOT NULL,
            area TEXT NOT NULL,
            current_concept_id TEXT,
            stage TEXT NOT NULL,
            last_evidence TEXT,
            difficulty_count INTEGER NOT NULL,
            mastery REAL NOT NULL,
            updated_at TEXT,
            PRIMARY KEY(student_id, area)
        );
    """)
    connection.commit()
    connection.close()


def use_test_database(monkeypatch, path):
    def get_test_connection():
        connection = sqlite3.connect(str(path))
        connection.row_factory = sqlite3.Row
        return connection
    monkeypatch.setattr(learner_state_module, "get_db_connection", get_test_connection)


def test_default_state(monkeypatch, tmp_path):
    path = tmp_path / "learner.db"
    create_learner_database(path)
    use_test_database(monkeypatch, path)
    state = LearnerState.get("ads")
    assert state["area"] == "ads"
    assert state["current_concept_id"] is None
    assert state["current_concept"] is None
    assert state["stage"] == "compreender"
    assert state["mastery"] == 0.0


def test_update_persists_stable_concept_id(monkeypatch, tmp_path):
    path = tmp_path / "learner-update.db"
    create_learner_database(path)
    use_test_database(monkeypatch, path)
    state = LearnerState.update(
        "ads", current_concept="variaveis", stage="testar",
        difficulty_count=2, mastery=0.5,
    )
    assert state["current_concept_id"] == "ads.variables"
    assert state["current_concept"] == "variáveis"
    assert state["stage"] == "testar"
    assert state["difficulty_count"] == 2
    assert state["mastery"] == 0.5


def test_invalid_values_are_normalized(monkeypatch, tmp_path):
    path = tmp_path / "learner-normalize.db"
    create_learner_database(path)
    use_test_database(monkeypatch, path)
    state = LearnerState.update("area-invalida", stage="x", difficulty_count=-3, mastery=9)
    assert state["area"] == "ads"
    assert state["stage"] == "compreender"
    assert state["difficulty_count"] == 0
    assert state["mastery"] == 1.0


def test_completed_stage_is_persisted(monkeypatch, tmp_path):
    path = tmp_path / "learner-completed.db"
    create_learner_database(path)
    use_test_database(monkeypatch, path)
    state = LearnerState.update(
        "ads", current_concept_id="ads.variables",
        stage="concluido", mastery=0.9,
    )
    assert state["stage"] == "concluido"
    assert state["current_concept_id"] == "ads.variables"
    assert state["current_concept"] == "variáveis"
    assert state["mastery"] == 0.9
