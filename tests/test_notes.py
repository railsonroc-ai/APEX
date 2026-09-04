import sqlite3

import backend.app as app_module


def create_notes_database(path):
    connection = sqlite3.connect(
        str(path)
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            text TEXT NOT NULL,
            area TEXT NOT NULL,
            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.commit()
    connection.close()


def test_note_rejects_empty_text(
    monkeypatch,
):
    monkeypatch.setattr(
        app_module,
        "verify_auth",
        lambda: True,
    )

    monkeypatch.setattr(
        app_module.StudentContext,
        "resolve",
        lambda area: {
            "student_id": "student_default",
            "session_id": f"session_default_{area}",
            "area": area,
        },
    )

    client = (
        app_module
        .app
        .test_client()
    )

    response = client.post(
        "/api/notes",
        json={
            "text": "",
            "area": "ads",
        },
    )

    assert response.status_code == 400

    assert response.get_json() == {
        "error":
            "Texto da nota é obrigatório"
    }


def test_note_is_saved(
    monkeypatch,
    tmp_path,
):
    database_path = (
        tmp_path
        / "notes-test.db"
    )

    create_notes_database(
        database_path
    )

    def get_test_connection():
        connection = sqlite3.connect(
            str(database_path)
        )

        connection.row_factory = (
            sqlite3.Row
        )

        return connection

    monkeypatch.setattr(
        app_module,
        "verify_auth",
        lambda: True,
    )

    monkeypatch.setattr(
        app_module.StudentContext,
        "resolve",
        lambda area: {
            "student_id": "student_default",
            "session_id": f"session_default_{area}",
            "area": area,
        },
    )

    monkeypatch.setattr(
        app_module,
        "get_db_connection",
        get_test_connection,
    )

    client = (
        app_module
        .app
        .test_client()
    )

    response = client.post(
        "/api/notes",
        json={
            "text":
                "Minha nota de teste",
            "area":
                "ads",
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["ok"] is True
    assert isinstance(
        data["id"],
        int,
    )

    connection = sqlite3.connect(
        str(database_path)
    )

    try:
        row = connection.execute(
            """
            SELECT
                student_id,
                text,
                area
            FROM notes
            WHERE id = ?
            """,
            (
                data["id"],
            ),
        ).fetchone()

    finally:
        connection.close()

    assert row == (
        "student_default",
        "Minha nota de teste",
        "ads",
    )


def test_note_over_4000_characters_is_rejected(
    monkeypatch,
    tmp_path,
):
    database_path = tmp_path / "notes-limit-test.db"
    create_notes_database(database_path)

    def get_test_connection():
        connection = sqlite3.connect(str(database_path))
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(
        app_module.StudentContext,
        "resolve",
        lambda area: {
            "student_id": "student_default",
            "session_id": f"session_default_{area}",
            "area": area,
        },
    )
    monkeypatch.setattr(
        app_module,
        "get_db_connection",
        get_test_connection,
    )

    response = app_module.app.test_client().post(
        "/api/notes",
        json={
            "text": "A" * 5000,
            "area": "ads",
        },
    )

    assert response.status_code == 400
    assert "4000" in response.get_json()["error"]

    connection = sqlite3.connect(str(database_path))
    try:
        count = connection.execute(
            "SELECT COUNT(*) FROM notes"
        ).fetchone()[0]
    finally:
        connection.close()

    assert count == 0


def test_invalid_note_area_falls_back_to_ads(
    monkeypatch,
    tmp_path,
):
    database_path = (
        tmp_path
        / "notes-area-test.db"
    )

    create_notes_database(
        database_path
    )

    def get_test_connection():
        connection = sqlite3.connect(
            str(database_path)
        )

        connection.row_factory = (
            sqlite3.Row
        )

        return connection

    monkeypatch.setattr(
        app_module,
        "verify_auth",
        lambda: True,
    )

    monkeypatch.setattr(
        app_module.StudentContext,
        "resolve",
        lambda area: {
            "student_id": "student_default",
            "session_id": f"session_default_{area}",
            "area": area,
        },
    )

    monkeypatch.setattr(
        app_module,
        "get_db_connection",
        get_test_connection,
    )

    client = (
        app_module
        .app
        .test_client()
    )

    response = client.post(
        "/api/notes",
        json={
            "text":
                "Nota com área inválida",
            "area":
                "area-invalida",
        },
    )

    assert response.status_code == 200

    note_id = (
        response
        .get_json()["id"]
    )

    connection = sqlite3.connect(
        str(database_path)
    )

    try:
        row = connection.execute(
            """
            SELECT area
            FROM notes
            WHERE id = ?
            """,
            (
                note_id,
            ),
        ).fetchone()

    finally:
        connection.close()

    assert row[0] == "ads"