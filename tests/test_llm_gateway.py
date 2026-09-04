from types import SimpleNamespace
import json

import pytest

from backend.services.llm_gateway import (
    LLMGateway,
    LLMProviderError,
)
from backend.services.observability import Observability


LIMITS = {
    LLMGateway.PURPOSE_CONCEPT_IDENTIFICATION: 111,
    LLMGateway.PURPOSE_EVIDENCE_EVALUATION: 222,
    LLMGateway.PURPOSE_TUTOR_RESPONSE: 333,
}


def build_gateway(factory, logger=None):
    return LLMGateway(
        api_key="secret-provider-key",
        model="model-test",
        timeout_seconds=12.5,
        max_retries=1,
        max_tokens_by_purpose=LIMITS,
        logger=logger,
        provider_factory=factory,
    )


def test_complete_text_hides_provider_contract_from_caller():
    captured = {}

    class Completions:
        def create(self, **kwargs):
            captured["create"] = kwargs
            usage = SimpleNamespace(
                prompt_tokens=10,
                completion_tokens=4,
                total_tokens=14,
            )
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='{"ok":true}')
                    )
                ],
                usage=usage,
            )

    class Provider:
        def __init__(self, **kwargs):
            captured["init"] = kwargs
            self.chat = SimpleNamespace(completions=Completions())

    gateway = build_gateway(Provider)
    content = gateway.complete_text(
        [{"role": "user", "content": "segredo do aluno"}],
        purpose=LLMGateway.PURPOSE_EVIDENCE_EVALUATION,
    )

    assert content == '{"ok":true}'
    assert captured["init"] == {
        "api_key": "secret-provider-key",
        "timeout": 12.5,
        "max_retries": 1,
    }
    assert captured["create"]["model"] == "model-test"
    assert captured["create"]["stream"] is False
    assert captured["create"]["max_completion_tokens"] == 222


def test_stream_text_yields_only_text_tokens():
    class Completions:
        def create(self, **kwargs):
            assert kwargs["stream"] is True
            assert kwargs["max_completion_tokens"] == 333
            return iter(
                [
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(content="Olá")
                            )
                        ]
                    ),
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(content=None)
                            )
                        ]
                    ),
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(content=" mundo")
                            )
                        ],
                        x_groq=SimpleNamespace(
                            usage=SimpleNamespace(
                                prompt_tokens=5,
                                completion_tokens=2,
                                total_tokens=7,
                            )
                        ),
                    ),
                ]
            )

    class Provider:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=Completions())

    gateway = build_gateway(Provider)
    tokens = list(
        gateway.stream_text(
            [{"role": "user", "content": "oi"}],
            purpose=LLMGateway.PURPOSE_TUTOR_RESPONSE,
        )
    )

    assert tokens == ["Olá", " mundo"]


def test_provider_failure_is_normalized():
    class Completions:
        def create(self, **kwargs):
            raise TimeoutError("provider detail")

    class Provider:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=Completions())

    gateway = build_gateway(Provider)

    with pytest.raises(LLMProviderError) as exc_info:
        gateway.complete_text(
            [{"role": "user", "content": "conteúdo privado"}],
            purpose=LLMGateway.PURPOSE_CONCEPT_IDENTIFICATION,
        )

    assert exc_info.value.purpose == LLMGateway.PURPOSE_CONCEPT_IDENTIFICATION
    assert "provider detail" not in str(exc_info.value)
    assert "conteúdo privado" not in str(exc_info.value)


def test_invalid_purpose_is_rejected_before_provider_call():
    def forbidden_provider(**kwargs):
        raise AssertionError("provider não deveria ser criado")

    gateway = build_gateway(forbidden_provider)

    with pytest.raises(ValueError, match="purpose inválido"):
        gateway.complete_text([], purpose="inventado")


def test_gateway_reuses_single_provider_client():
    captured = {"clients": 0, "calls": 0}

    class Completions:
        def create(self, **kwargs):
            captured["calls"] += 1
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="ok")
                    )
                ]
            )

    class Provider:
        def __init__(self, **kwargs):
            captured["clients"] += 1
            self.chat = SimpleNamespace(completions=Completions())

    gateway = build_gateway(Provider)
    gateway.complete_text(
        [], purpose=LLMGateway.PURPOSE_CONCEPT_IDENTIFICATION
    )
    gateway.complete_text(
        [], purpose=LLMGateway.PURPOSE_EVIDENCE_EVALUATION
    )

    assert captured == {"clients": 1, "calls": 2}


def test_gateway_logs_metadata_without_prompt_or_response(caplog):
    class Completions:
        def create(self, **kwargs):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="RESPOSTA_SECRETA")
                    )
                ]
            )

    class Provider:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=Completions())

    gateway = build_gateway(Provider)

    Observability.begin_request("request-llm-test")
    Observability.bind(turn_id="turn-llm-test", area="ads")
    try:
        with caplog.at_level("INFO"):
            gateway.complete_text(
                [{"role": "user", "content": "PROMPT_SECRETO"}],
                purpose=LLMGateway.PURPOSE_EVIDENCE_EVALUATION,
            )
    finally:
        Observability.clear()

    logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "llm_call" in logs
    assert "evidence_evaluation" in logs
    assert "PROMPT_SECRETO" not in logs
    assert "RESPOSTA_SECRETA" not in logs

    structured = next(
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith(Observability.EVENT_PREFIX)
    )
    payload = json.loads(structured[len(Observability.EVENT_PREFIX):])
    assert payload["event"] == "llm_call"
    assert payload["request_id"] == "request-llm-test"
    assert payload["turn_id"] == "turn-llm-test"
    assert payload["purpose"] == LLMGateway.PURPOSE_EVIDENCE_EVALUATION
    assert payload["ok"] is True
