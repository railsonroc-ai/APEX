import sqlite3

import backend.services.learner_state as learner_state_module
from backend.services.learner_state import LearnerState


def create_learner_database(path):
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("""
        CREATE TABLE learner_state (
            area TEXT PRIMARY KEY,
            current_concept TEXT,
            stage TEXT NOT NULL,
            last_evidence TEXT,
            difficulty_count INTEGER NOT NULL,
            mastery REAL NOT NULL,
            updated_at TEXT
        )
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
    assert state["current_concept"] is None
    assert state["stage"] == "compreender"
    assert state["mastery"] == 0.0


def test_update_persists_state(monkeypatch, tmp_path):
    path = tmp_path / "learner-update.db"
    create_learner_database(path)
    use_test_database(monkeypatch, path)
    state = LearnerState.update("ads", current_concept="variáveis", stage="testar", difficulty_count=2, mastery=0.5)
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
