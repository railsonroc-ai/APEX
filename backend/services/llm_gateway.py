from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import Any, Callable, Iterable, Iterator
from uuid import uuid4

from backend.services.observability import Observability


@dataclass(frozen=True)
class LLMCallMeta:
    call_id: str
    purpose: str
    model: str
    stream: bool
    latency_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


class LLMProviderError(RuntimeError):
    """Erro normalizado da camada de provider LLM."""

    def __init__(self, purpose: str, message: str = "Falha no provider LLM"):
        super().__init__(message)
        self.purpose = purpose


class LLMGateway:
    """
    Fronteira única entre o APEX e o provider de LLM.

    O domínio envia mensagens e recebe texto/tokens. Detalhes do SDK,
    timeout, retries e limites de geração ficam confinados aqui.
    """

    PURPOSE_CONCEPT_IDENTIFICATION = "concept_identification"
    PURPOSE_EVIDENCE_EVALUATION = "evidence_evaluation"
    PURPOSE_TUTOR_RESPONSE = "tutor_response"

    VALID_PURPOSES = {
        PURPOSE_CONCEPT_IDENTIFICATION,
        PURPOSE_EVIDENCE_EVALUATION,
        PURPOSE_TUTOR_RESPONSE,
    }

    # Ponto de injeção para testes. Em produção permanece None e o SDK
    # oficial é importado de forma lazy.
    PROVIDER_FACTORY: Callable[..., Any] | None = None

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        max_tokens_by_purpose: dict[str, int],
        logger: logging.Logger | None = None,
        provider_factory: Callable[..., Any] | None = None,
    ):
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "").strip()
        self.timeout_seconds = float(timeout_seconds)
        self.max_retries = int(max_retries)
        self.max_tokens_by_purpose = dict(max_tokens_by_purpose)
        self.logger = logger or logging.getLogger(__name__)
        self.provider_factory = provider_factory
        self._client = None

        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds deve ser maior que zero")
        if self.max_retries < 0:
            raise ValueError("max_retries não pode ser negativo")

        missing = self.VALID_PURPOSES - set(self.max_tokens_by_purpose)
        if missing:
            raise ValueError(
                "Limites ausentes para: " + ", ".join(sorted(missing))
            )

        for purpose, value in self.max_tokens_by_purpose.items():
            if purpose not in self.VALID_PURPOSES:
                raise ValueError(f"purpose desconhecido: {purpose}")
            if not isinstance(value, int) or value <= 0:
                raise ValueError(
                    f"max tokens inválido para {purpose}: {value!r}"
                )

    @classmethod
    def _default_provider_factory(cls):
        from groq import Groq

        return Groq

    def _resolve_provider_factory(self):
        return (
            self.provider_factory
            or self.PROVIDER_FACTORY
            or self._default_provider_factory()
        )

    def _get_client(self):
        if self._client is None:
            factory = self._resolve_provider_factory()
            self._client = factory(
                api_key=self.api_key,
                timeout=self.timeout_seconds,
                max_retries=self.max_retries,
            )
        return self._client

    def _validate_purpose(self, purpose: str) -> str:
        normalized = str(purpose or "").strip()
        if normalized not in self.VALID_PURPOSES:
            raise ValueError(f"purpose inválido: {purpose!r}")
        return normalized

    @staticmethod
    def _usage_values(obj: Any) -> tuple[int | None, int | None, int | None]:
        usage = getattr(obj, "usage", None)
        if usage is None:
            x_groq = getattr(obj, "x_groq", None)
            usage = getattr(x_groq, "usage", None) if x_groq is not None else None

        if usage is None:
            return None, None, None

        def value(name: str) -> int | None:
            raw = getattr(usage, name, None)
            if raw is None and isinstance(usage, dict):
                raw = usage.get(name)
            try:
                return int(raw) if raw is not None else None
            except (TypeError, ValueError):
                return None

        return (
            value("prompt_tokens"),
            value("completion_tokens"),
            value("total_tokens"),
        )

    def _log_call(
        self,
        *,
        call_id: str,
        purpose: str,
        stream: bool,
        started_at: float,
        usage_source: Any = None,
        ok: bool,
        error_type: str | None = None,
    ) -> LLMCallMeta:
        latency_ms = max(0, int((time.monotonic() - started_at) * 1000))
        prompt_tokens, completion_tokens, total_tokens = self._usage_values(
            usage_source
        )

        meta = LLMCallMeta(
            call_id=call_id,
            purpose=purpose,
            model=self.model,
            stream=stream,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

        # Não incluir messages, prompt nem resposta nos logs.
        Observability.event(
            self.logger,
            "llm_call",
            call_id=meta.call_id,
            purpose=meta.purpose,
            model=meta.model,
            stream=meta.stream,
            ok=bool(ok),
            latency_ms=meta.latency_ms,
            prompt_tokens=meta.prompt_tokens,
            completion_tokens=meta.completion_tokens,
            total_tokens=meta.total_tokens,
            error_type=error_type or None,
        )
        return meta

    def complete_text(
        self,
        messages: list[dict[str, str]],
        *,
        purpose: str,
    ) -> str | None:
        purpose = self._validate_purpose(purpose)
        call_id = uuid4().hex
        started_at = time.monotonic()
        response = None

        try:
            response = self._get_client().chat.completions.create(
                messages=messages,
                model=self.model,
                stream=False,
                max_completion_tokens=self.max_tokens_by_purpose[purpose],
            )

            choices = getattr(response, "choices", None) or []
            if not choices:
                self._log_call(
                    call_id=call_id,
                    purpose=purpose,
                    stream=False,
                    started_at=started_at,
                    usage_source=response,
                    ok=True,
                )
                return None

            message = getattr(choices[0], "message", None)
            content = getattr(message, "content", None)

            self._log_call(
                call_id=call_id,
                purpose=purpose,
                stream=False,
                started_at=started_at,
                usage_source=response,
                ok=True,
            )

            if content is None:
                return None
            return str(content)

        except Exception as exc:
            self._log_call(
                call_id=call_id,
                purpose=purpose,
                stream=False,
                started_at=started_at,
                usage_source=response,
                ok=False,
                error_type=type(exc).__name__,
            )
            raise LLMProviderError(purpose) from None

    def stream_text(
        self,
        messages: list[dict[str, str]],
        *,
        purpose: str,
    ) -> Iterator[str]:
        purpose = self._validate_purpose(purpose)
        call_id = uuid4().hex
        started_at = time.monotonic()
        last_chunk = None

        try:
            response = self._get_client().chat.completions.create(
                messages=messages,
                model=self.model,
                stream=True,
                max_completion_tokens=self.max_tokens_by_purpose[purpose],
            )

            for chunk in response:
                last_chunk = chunk
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                content = getattr(delta, "content", None)
                if content:
                    yield str(content)

            self._log_call(
                call_id=call_id,
                purpose=purpose,
                stream=True,
                started_at=started_at,
                usage_source=last_chunk,
                ok=True,
            )

        except Exception as exc:
            self._log_call(
                call_id=call_id,
                purpose=purpose,
                stream=True,
                started_at=started_at,
                usage_source=last_chunk,
                ok=False,
                error_type=type(exc).__name__,
            )
            raise LLMProviderError(purpose) from None
