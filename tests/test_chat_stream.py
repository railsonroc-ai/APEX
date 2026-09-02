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

def test_chat_uses_pedagogical_state(monkeypatch):
    state = {
        "area": "ads",
        "current_concept": "variáveis",
        "stage": "testar",
        "last_evidence": None,
        "difficulty_count": 0,
        "mastery": 0.5,
        "updated_at": None,
    }
    captured = {}
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(app_module, "GROQ_API_KEY", "teste")
    monkeypatch.setattr(app_module.LearnerState, "get", lambda area: state)
    monkeypatch.setattr(app_module.TeachingPolicy, "choose_action", lambda value: "testar")
    def fake_build_messages(user_message, history=None, area="ads", learner_state=None, teaching_action=None):
        captured["learner_state"] = learner_state
        captured["teaching_action"] = teaching_action
        return [{"role": "user", "content": user_message}]

    monkeypatch.setattr(app_module.TutorCore, "build_messages", fake_build_messages)

    class FakeCompletions:
        def create(self, **kwargs):
            return []

    class FakeChat:
        completions = FakeCompletions()

    class FakeGroq:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setattr(app_module, "Groq", FakeGroq)

    client = app_module.app.test_client()
    response = client.post(
        "/chat/stream",
        json={"message": "teste", "history": [], "area": "ads"},
    )
    response.get_data(as_text=True)
    assert response.status_code == 200
    assert captured["learner_state"] == state
    assert captured["teaching_action"] == "testar"
