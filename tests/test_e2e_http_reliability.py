from types import SimpleNamespace

import pytest

import backend.app as app_module
import backend.database as database_module
from backend.identity import DEFAULT_STUDENT_ID, default_session_id
from backend.services.evidence_event import EvidenceEvent
from backend.services.learning_attempt import LearningAttempt
from backend.services.learning_task import LearningTask
from backend.services.rubric_assessment import RubricAssessment


pytestmark = [pytest.mark.e2e, pytest.mark.reliability]


class ScriptedCompletions:
    calls = []

    def create(self, **kwargs):
        messages = kwargs.get("messages") or []
        stream = bool(kwargs.get("stream"))
        self.__class__.calls.append(
            {
                "stream": stream,
                "messages": messages,
            }
        )

        if stream:
            text = "Responda com uma aplicação curta do conceito."
            return [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(content=text)
                        )
                    ]
                )
            ]

        system = "\n".join(
            str(item.get("content", ""))
            for item in messages
            if item.get("role") == "system"
        )
        if "Escolha o conceito pedagógico principal" in system:
            content = '{"concept_id":"ads.variables"}'
        elif "Avalie semanticamente a evidência" in system:
            content = (
                '{"criteria":{'
                '"task_response":"met",'
                '"conceptual_correctness":"met",'
                '"understanding_application":"met"},'
                '"confidence":0.95,'
                '"evidence":"Demonstrou compreensão."}'
            )
        else:
            raise AssertionError("chamada LLM não reconhecida")

        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content)
                )
            ]
        )


class FakeGroq:
    def __init__(self, **kwargs):
        self.chat = SimpleNamespace(completions=ScriptedCompletions())


def _fresh_database(monkeypatch, tmp_path):
    path = tmp_path / "e2e-http.db"
    monkeypatch.setattr(database_module, "DATABASE_PATH", path)
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    return path


def test_http_two_turn_journey_creates_task_attempt_rubric_and_replays_safely(
    monkeypatch,
    tmp_path,
):
    _fresh_database(monkeypatch, tmp_path)
    ScriptedCompletions.calls = []

    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(app_module, "GROQ_API_KEY", "e2e-test-key")
    monkeypatch.setattr(
        app_module.LLMGateway,
        "PROVIDER_FACTORY",
        FakeGroq,
    )

    client = app_module.app.test_client()

    first = client.post(
        "/chat/stream",
        json={
            "message": "Quero aprender variáveis",
            "area": "ads",
            "turn_id": "http-e2e-1",
        },
    )
    first_body = first.get_data(as_text=True)

    assert first.status_code == 200
    assert first.headers.get("X-Apex-Request-ID")
    assert '"done": true' in first_body.lower()
    assert '"error"' not in first_body.lower()

    task = LearningTask.find_by_source_turn(
        "http-e2e-1",
        student_id=DEFAULT_STUDENT_ID,
        session_id=default_session_id("ads"),
    )
    assert task is not None
    assert task["concept_id"] == "ads.variables"

    second = client.post(
        "/chat/stream",
        json={
            "message": "Uma variável guarda um valor que pode mudar.",
            "area": "ads",
            "turn_id": "http-e2e-2",
        },
    )
    second_body = second.get_data(as_text=True)

    assert second.status_code == 200
    assert second.headers.get("X-Apex-Request-ID")
    assert '"done": true' in second_body.lower()
    assert '"error"' not in second_body.lower()

    attempt = LearningAttempt.for_turn(
        "http-e2e-2",
        student_id=DEFAULT_STUDENT_ID,
    )
    event = EvidenceEvent.for_turn(
        "http-e2e-2",
        student_id=DEFAULT_STUDENT_ID,
    )
    rubric = RubricAssessment.for_turn(
        "http-e2e-2",
        student_id=DEFAULT_STUDENT_ID,
    )

    assert attempt is not None
    assert event is not None
    assert rubric is not None
    assert attempt["task_id"] == task["task_id"]
    assert rubric["attempt_id"] == attempt["attempt_id"]
    assert rubric["evidence_event_id"] == event["event_id"]
    assert event["outcome"] == "demonstrated"

    calls_before_replay = len(ScriptedCompletions.calls)
    replay = client.post(
        "/chat/stream",
        json={
            "message": "Uma variável guarda um valor que pode mudar.",
            "area": "ads",
            "turn_id": "http-e2e-2",
        },
    )
    replay_body = replay.get_data(as_text=True)

    assert replay.status_code == 200
    assert '"done": true' in replay_body.lower()
    assert len(ScriptedCompletions.calls) == calls_before_replay

    assert len(
        EvidenceEvent.list_for_concept(
            "ads",
            "ads.variables",
            student_id=DEFAULT_STUDENT_ID,
        )
    ) == 1
