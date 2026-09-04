from backend.app import app
from backend.config import (
    MAX_HISTORY_MESSAGES,
    MAX_USER_MESSAGE_CHARS,
)



def test_home_returns_200():
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200


def test_home_exposes_history_limit():
    client = app.test_client()

    response = client.get("/")

    html = response.get_data(
        as_text=True
    )

    expected_config = (
        "maxHistoryMessages: "
        f"{MAX_HISTORY_MESSAGES}"
    )

    assert expected_config in html


def test_health_returns_database_ok():
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200

    assert response.get_json() == {
        "database": "ok",
        "ok": True,
        "service": "APEX",
    }


def test_chat_rejects_empty_message():
    client = app.test_client()

    response = client.post(
        "/chat/stream",
        json={
            "message": "",
            "history": [],
        },
    )

    assert response.status_code == 400

    assert response.get_json() == {
        "error": "Mensagem obrigatória"
    }


def test_chat_rejects_message_above_limit():
    client = app.test_client()

    response = client.post(
        "/chat/stream",
        json={
            "message":
                "A"
                * (
                    MAX_USER_MESSAGE_CHARS
                    + 1
                ),
            "history": [],
        },
    )

    assert response.status_code == 400

    assert response.get_json() == {
        "error":
            "Mensagem muito longa. "
            "Reduza o texto e tente novamente."
    }