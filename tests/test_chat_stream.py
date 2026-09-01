import backend.app as app_module


def test_chat_stream_without_groq_key_returns_sse_error(
    monkeypatch,
):
    monkeypatch.setattr(
        app_module,
        "verify_auth",
        lambda: True,
    )

    monkeypatch.setattr(
        app_module,
        "GROQ_API_KEY",
        "",
    )

    client = (
        app_module
        .app
        .test_client()
    )

    response = client.post(
        "/chat/stream",
        json={
            "message":
                "O que é uma variável?",
            "history": [],
            "area": "ads",
        },
    )

    body = response.get_data(
        as_text=True
    )

    assert response.status_code == 200

    assert (
        response.mimetype
        == "text/event-stream"
    )

    assert (
        response.headers[
            "Cache-Control"
        ]
        == "no-cache"
    )

    assert (
        response.headers[
            "X-Accel-Buffering"
        ]
        == "no"
    )

    assert (
        "Chave GROQ_API_KEY "
        "não configurada"
        in body
    )