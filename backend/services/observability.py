from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timezone
import hashlib
import json
import logging
import re
import time
from typing import Any
from uuid import uuid4


_CONTEXT: ContextVar[dict[str, Any]] = ContextVar(
    "apex_observability_context",
    default={},
)

_EVENT_RE = re.compile(r"^[a-z0-9_.-]{1,80}$")

_FORBIDDEN_FIELDS = {
    "user_message",
    "assistant_message",
    "student_answer",
    "prompt",
    "messages",
    "response",
    "content",
    "text",
    "note_text",
    "api_key",
    "access_key",
    "secret",
    "authorization",
}

_CONTEXT_KEYS = {
    "request_id",
    "turn_id",
    "student_ref",
    "session_ref",
    "area",
}


class Observability:
    """Observabilidade estruturada, correlacionável e privacy-first.

    O contexto mantém apenas IDs operacionais/pseudônimos. Conteúdo do aluno,
    prompts, respostas e segredos são proibidos por contrato.
    """

    EVENT_PREFIX = "apex_event "

    @staticmethod
    def _ref(value: Any) -> str | None:
        normalized = str(value or "").strip()
        if not normalized:
            return None
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def begin_request(cls, request_id: str | None = None) -> str:
        rid = str(request_id or uuid4().hex).strip() or uuid4().hex
        _CONTEXT.set({"request_id": rid})
        return rid

    @classmethod
    def clear(cls) -> None:
        _CONTEXT.set({})

    @classmethod
    def bind(cls, **fields: Any) -> dict[str, Any]:
        invalid = set(fields) - _CONTEXT_KEYS
        if invalid:
            raise ValueError(
                "Campos de contexto não permitidos: "
                + ", ".join(sorted(invalid))
            )
        current = dict(_CONTEXT.get())
        for key, value in fields.items():
            if value is None:
                current.pop(key, None)
            else:
                current[key] = str(value)
        _CONTEXT.set(current)
        return dict(current)

    @classmethod
    def bind_identity(
        cls,
        *,
        student_id: Any = None,
        session_id: Any = None,
    ) -> dict[str, Any]:
        return cls.bind(
            student_ref=cls._ref(student_id),
            session_ref=cls._ref(session_id),
        )

    @classmethod
    def context(cls) -> dict[str, Any]:
        return dict(_CONTEXT.get())

    @staticmethod
    def elapsed_ms(started_at: float) -> int:
        return max(0, int((time.monotonic() - float(started_at)) * 1000))

    @staticmethod
    def _safe_value(value: Any) -> Any:
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            return value[:256]
        raise TypeError(
            "Eventos operacionais aceitam apenas valores escalares seguros"
        )

    @classmethod
    def _payload(cls, event: str, fields: dict[str, Any]) -> dict[str, Any]:
        normalized_event = str(event or "").strip().lower()
        if not _EVENT_RE.fullmatch(normalized_event):
            raise ValueError(f"Nome de evento inválido: {event!r}")

        forbidden = _FORBIDDEN_FIELDS.intersection(fields)
        if forbidden:
            raise ValueError(
                "Campos sensíveis não podem ser registrados: "
                + ", ".join(sorted(forbidden))
            )

        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "event": normalized_event,
            **cls.context(),
        }
        for key, value in fields.items():
            payload[str(key)] = cls._safe_value(value)
        return payload

    @classmethod
    def event(
        cls,
        logger: logging.Logger,
        event: str,
        *,
        level: int = logging.INFO,
        **fields: Any,
    ) -> dict[str, Any]:
        payload = cls._payload(event, fields)
        logger.log(
            level,
            cls.EVENT_PREFIX
            + json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )
        return payload

    @classmethod
    def exception(
        cls,
        logger: logging.Logger,
        event: str,
        **fields: Any,
    ) -> dict[str, Any]:
        payload = cls._payload(event, fields)
        logger.error(
            cls.EVENT_PREFIX
            + json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
            exc_info=True,
        )
        return payload
