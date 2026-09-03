import sqlite3

import backend.database as database_module


def prepare_database(path):
    connection = sqlite3.connect(str(path))
    connection.execute(
        "CREATE TABLE items (id INTEGER PRIMARY KEY, value TEXT)"
    )
    connection.commit()
    connection.close()


def configure_database(monkeypatch, tmp_path):
    path = tmp_path / "transaction.db"
    prepare_database(path)

    monkeypatch.setattr(database_module, "DATABASE_PATH", path)
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)

    return path


def test_transaction_commits_all_changes(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path)

    with database_module.transaction():
        connection = database_module.get_db_connection()
        connection.execute(
            "INSERT INTO items (value) VALUES (?)",
            ("persistir",),
        )

        # Simula os commits que os serviços atuais executam.
        connection.commit()
        connection.close()

    connection = sqlite3.connect(str(path))
    rows = connection.execute(
        "SELECT value FROM items"
    ).fetchall()
    connection.close()

    assert rows == [("persistir",)]


def test_transaction_rolls_back_all_changes(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path)

    try:
        with database_module.transaction():
            connection = database_module.get_db_connection()
            connection.execute(
                "INSERT INTO items (value) VALUES (?)",
                ("nao_persistir",),
            )

            # Deve ser neutralizado enquanto a transação está ativa.
            connection.commit()
            connection.close()

            raise RuntimeError("falha simulada")
    except RuntimeError:
        pass

    connection = sqlite3.connect(str(path))
    rows = connection.execute(
        "SELECT value FROM items"
    ).fetchall()
    connection.close()

    assert rows == []
