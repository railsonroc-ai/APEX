import json
import logging

import pytest

from backend.services.observability import Observability


class CaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def build_logger():
    logger = logging.getLogger("apex-test-observability")
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.INFO)
    handler = CaptureHandler()
    logger.addHandler(handler)
    return logger, handler


def parse_event(message):
    assert message.startswith(Observability.EVENT_PREFIX)
    return json.loads(message[len(Observability.EVENT_PREFIX):])


def test_event_is_structured_and_correlated_without_raw_identity():
    logger, handler = build_logger()
    Observability.begin_request("request-123")
    Observability.bind(turn_id="turn-456", area="ads")
    Observability.bind_identity(
        student_id="student-sensitive",
        session_id="session-sensitive",
    )

    try:
        payload = Observability.event(
            logger,
            "learning_turn_completed",
            latency_ms=42,
            stage_before="testar",
            stage_after="fixar",
            teaching_action="consolidar",
        )
    finally:
        Observability.clear()

    logged = parse_event(handler.messages[-1])
    assert logged == payload
    assert logged["request_id"] == "request-123"
    assert logged["turn_id"] == "turn-456"
    assert logged["area"] == "ads"
    assert logged["latency_ms"] == 42
    assert logged["student_ref"]
    assert logged["session_ref"]
    serialized = handler.messages[-1]
    assert "student-sensitive" not in serialized
    assert "session-sensitive" not in serialized


def test_sensitive_content_fields_are_rejected_by_contract():
    logger, _ = build_logger()
    Observability.begin_request("request-sensitive")
    try:
        with pytest.raises(ValueError, match="sensíveis"):
            Observability.event(
                logger,
                "unsafe_event",
                user_message="segredo do aluno",
            )

        with pytest.raises(ValueError, match="sensíveis"):
            Observability.event(
                logger,
                "unsafe_event",
                api_key="provider-secret",
            )
    finally:
        Observability.clear()


def test_context_clear_prevents_cross_request_leakage():
    logger, handler = build_logger()

    Observability.begin_request("first")
    Observability.bind(turn_id="turn-first", area="ads")
    Observability.clear()

    Observability.begin_request("second")
    try:
        Observability.event(logger, "http_response_ready", status_code=200)
    finally:
        Observability.clear()

    logged = parse_event(handler.messages[-1])
    assert logged["request_id"] == "second"
    assert "turn_id" not in logged
    assert "area" not in logged


def test_only_safe_scalar_values_are_accepted():
    logger, _ = build_logger()
    Observability.begin_request("request-scalars")
    try:
        with pytest.raises(TypeError, match="escalares seguros"):
            Observability.event(
                logger,
                "bad_shape",
                details={"nested": "not allowed"},
            )
    finally:
        Observability.clear()


def test_app_routes_use_structured_observability_boundary():
    from pathlib import Path

    app_source = (
        Path(__file__).resolve().parents[1] / "backend" / "app.py"
    ).read_text()

    assert "current_app.logger.exception(" not in app_source
    assert '"learning_turn_completed"' in app_source
    assert '"learning_turn_failed"' in app_source
    assert '"session_transition"' in app_source
    assert '"X-Apex-Request-ID"' in app_source
