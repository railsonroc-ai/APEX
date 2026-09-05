from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "backend" / "templates" / "index.html").read_text()
API_JS = (ROOT / "backend" / "static" / "js" / "apex-api.js").read_text()
CHAT_JS = (ROOT / "backend" / "static" / "js" / "chat-engine.js").read_text()


def test_session_controls_are_present_in_main_interface():
    required_ids = {
        'id="session-status-badge"',
        'id="pause-btn"',
        'id="session-panel"',
        'id="session-panel-title"',
        'id="session-panel-detail"',
        'id="session-panel-actions"',
        'id="resume-direct-btn"',
        'id="resume-review-btn"',
        'id="learning-focus"',
        'id="learning-focus-title"',
        'id="learning-focus-detail"',
    }
    for marker in required_ids:
        assert marker in TEMPLATE

    assert "⏸ Pausar" in TEMPLATE
    assert "▶ Retomar direto" in TEMPLATE
    assert "↻ Revisar antes" in TEMPLATE


def test_frontend_api_exposes_server_session_lifecycle():
    assert "async function getSession(area)" in API_JS
    assert "async function pauseSession(area)" in API_JS
    assert "async function resumeSession(" in API_JS
    assert "'/api/session/pause'" in API_JS
    assert "'/api/session/resume'" in API_JS
    assert "`/api/session?${query.toString()}`" in API_JS

    public_api = API_JS.split("window.ApexApi =", 1)[1]
    assert "getSession," in public_api
    assert "pauseSession," in public_api
    assert "resumeSession," in public_api


def test_chat_engine_uses_server_status_to_control_input():
    assert "function chatBlockedBySession()" in CHAT_JS
    assert "sessionStatus() === 'paused'" in CHAT_JS
    assert "input.disabled =\n        blocked || loading;" in CHAT_JS
    assert "sendButton.disabled =\n        blocked || busy;" in CHAT_JS
    assert "pauseButton.hidden =\n        status !== 'studying';" in CHAT_JS
    assert "sessionPanelActions.hidden = true;" in CHAT_JS
    assert "Responda à tarefa atual ou peça ajuda..." in CHAT_JS
    assert "`Agora: ${focus.concept}. `" in CHAT_JS


def test_pause_and_both_resume_modes_are_wired_to_api():
    assert "await Api.pauseSession(AREA)" in CHAT_JS
    assert "await Api.resumeSession(" in CHAT_JS
    assert "() => resumeLearningSession('direct')" in CHAT_JS
    assert "() => resumeLearningSession('review')" in CHAT_JS


def test_resume_review_starts_review_turn_and_refreshes_after_chat():
    assert "Quero revisar antes de retomar." in CHAT_JS
    assert "await sendMessage();" in CHAT_JS
    assert "await refreshSessionRuntime({\n          quiet: true\n        });" in CHAT_JS
    assert "Responda à revisão de retomada..." in CHAT_JS
