from backend.app import app
from backend.config import (
    APEX_ACCESS_KEY,
    MAX_USER_MESSAGE_CHARS,
)


def auth_headers():
    """
    Retorna a autenticação configurada no ambiente local.

    Se não houver chave configurada em desenvolvimento,
    nenhum cabeçalho adicional é necessário.
    """

    if not APEX_ACCESS_KEY:
        return {}

    return {
        "X-Apex-Key": APEX_ACCESS_KEY,
    }


def test_home_returns_200():
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200


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
        headers=auth_headers(),
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
        headers=auth_headers(),
    )

    assert response.status_code == 400

    assert response.get_json() == {
        "error":
            "Mensagem muito longa. "
            "Reduza o texto e tente novamente."
    }