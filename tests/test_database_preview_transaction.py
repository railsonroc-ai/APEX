import sqlite3

import backend.database as database_module


def prepare_database(path):
    connection = sqlite3.connect(str(path))

    connection.execute(
        "CREATE TABLE items ("
        "id INTEGER PRIMARY KEY, "
        "value TEXT"
        ")"
    )

    connection.commit()
    connection.close()


def test_preview_transaction_always_rolls_back(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "preview.db"

    prepare_database(path)

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

    with database_module.preview_transaction():
        connection = (
            database_module.get_db_connection()
        )

        connection.execute(
            "INSERT INTO items (value) VALUES (?)",
            ("temporario",),
        )

        # Simula commits internos dos serviços.
        connection.commit()
        connection.close()

        visible_inside = (
            database_module
            .get_db_connection()
            .execute(
                "SELECT value FROM items"
            )
            .fetchall()
        )

        assert (
            [row["value"] for row in visible_inside]
            == ["temporario"]
        )

    connection = sqlite3.connect(
        str(path)
    )

    rows = connection.execute(
        "SELECT value FROM items"
    ).fetchall()

    connection.close()

    assert rows == []
