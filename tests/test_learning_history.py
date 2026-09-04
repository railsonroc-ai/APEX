import sqlite3

import backend.database as database_module

from backend.services.learning_history import LearningHistory


def prepare_database(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "learning-history.db"

    monkeypatch.setattr(
        database_module,
        "DATABASE_PATH",
        path,
    )
    monkeypatch.setattr(
        database_module,
        "DATA_DIR",
        tmp_path,
    )

    database_module.init_database()


def test_returns_only_confirmed_turns_in_order(
    monkeypatch,
    tmp_path,
):
    prepare_database(
        monkeypatch,
        tmp_path,
    )

    LearningHistory.record(
        turn_id="turn-001",
        area="ads",
        user_message="Pergunta 1",
        assistant_message="Resposta 1",
        concept="variáveis",
    )
    LearningHistory.record(
        turn_id="turn-002",
        area="ads",
        user_message="Pergunta interrompida",
        assistant_message=None,
        concept="variáveis",
    )
    LearningHistory.record(
        turn_id="turn-003",
        area="ads",
        user_message="Pergunta 3",
        assistant_message="Resposta 3",
        concept="variáveis",
    )

    assert LearningHistory.get_messages(
        "ads",
        concept="variáveis",
        limit=8,
    ) == [
        {
            "role": "user",
            "content": "Pergunta 1",
        },
        {
            "role": "assistant",
            "content": "Resposta 1",
        },
        {
            "role": "user",
            "content": "Pergunta 3",
        },
        {
            "role": "assistant",
            "content": "Resposta 3",
        },
    ]


def test_history_is_isolated_by_area_and_limited(
    monkeypatch,
    tmp_path,
):
    prepare_database(
        monkeypatch,
        tmp_path,
    )

    for number in range(1, 4):
        LearningHistory.record(
            turn_id=f"ads-{number}",
            area="ads",
            user_message=f"Pergunta ADS {number}",
            assistant_message=f"Resposta ADS {number}",
            concept="variáveis",
        )

    LearningHistory.record(
        turn_id="it-1",
        area="it",
        user_message="Pergunta IT",
        assistant_message="Resposta IT",
        concept="redes",
    )

    messages = LearningHistory.get_messages(
        "ads",
        concept="variáveis",
        limit=4,
    )

    assert messages == [
        {
            "role": "user",
            "content": "Pergunta ADS 2",
        },
        {
            "role": "assistant",
            "content": "Resposta ADS 2",
        },
        {
            "role": "user",
            "content": "Pergunta ADS 3",
        },
        {
            "role": "assistant",
            "content": "Resposta ADS 3",
        },
    ]


def test_find_returns_committed_turn(
    monkeypatch,
    tmp_path,
):
    prepare_database(
        monkeypatch,
        tmp_path,
    )

    LearningHistory.record(
        turn_id="turn-existing",
        area="ads",
        user_message="Pergunta",
        assistant_message="Resposta",
        concept="variáveis",
    )

    turn = LearningHistory.find(
        "turn-existing"
    )

    assert turn["area"] == "ads"
    assert turn["user_message"] == "Pergunta"
    assert turn["assistant_message"] == "Resposta"
    assert turn["concept_id"] == "ads.variables"
    assert turn["concept"] == "variáveis"


def test_history_is_isolated_by_concept(
    monkeypatch,
    tmp_path,
):
    prepare_database(
        monkeypatch,
        tmp_path,
    )

    LearningHistory.record(
        turn_id="variables-turn",
        area="ads",
        user_message="O que é variável?",
        assistant_message="Resposta sobre variável.",
        concept="variáveis",
    )
    LearningHistory.record(
        turn_id="functions-turn",
        area="ads",
        user_message="O que é função?",
        assistant_message="Resposta sobre função.",
        concept="funções",
    )

    assert LearningHistory.get_messages(
        "ads",
        concept="funções",
    ) == [
        {
            "role": "user",
            "content": "O que é função?",
        },
        {
            "role": "assistant",
            "content": "Resposta sobre função.",
        },
    ]

    assert LearningHistory.get_messages(
        "ads",
        concept="funções",
        limit=1,
    ) == []


def test_existing_learning_turns_table_is_migrated(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "legacy-learning-turns.db"

    connection = sqlite3.connect(
        str(path)
    )
    connection.execute(
        """
        CREATE TABLE learning_turns (
            turn_id TEXT PRIMARY KEY,
            area TEXT NOT NULL,
            user_message TEXT NOT NULL,
            assistant_message TEXT,
            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.commit()
    connection.close()

    monkeypatch.setattr(
        database_module,
        "DATABASE_PATH",
        path,
    )
    monkeypatch.setattr(
        database_module,
        "DATA_DIR",
        tmp_path,
    )

    database_module.init_database()

    connection = sqlite3.connect(
        str(path)
    )

    try:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(learning_turns)"
            ).fetchall()
        }
    finally:
        connection.close()

    assert "concept_id" in columns
    assert "concept" not in columns


def test_latest_confirmed_turn_returns_exact_source_context(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)

    LearningHistory.record(
        turn_id="source-old",
        area="ads",
        user_message="Pergunta antiga",
        assistant_message="Resposta antiga",
        concept="variáveis",
    )
    LearningHistory.record(
        turn_id="source-latest",
        area="ads",
        user_message="Pergunta nova",
        assistant_message="Resposta nova",
        concept="variáveis",
    )

    turn = LearningHistory.latest_confirmed_turn(
        "ads",
        concept_id="ads.variables",
        session_id="session_default_ads",
    )

    assert turn["turn_id"] == "source-latest"
    assert turn["assistant_message"] == "Resposta nova"
    assert turn["concept_id"] == "ads.variables"
