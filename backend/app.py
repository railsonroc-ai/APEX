import json
import logging
import sqlite3
import time
from uuid import uuid4

from flask import (
    Flask,
    Blueprint,
    current_app,
    g,
    render_template,
    request,
    jsonify,
    Response,
    stream_with_context,
)

from backend.config import (
    APP_ENV,
    LOG_LEVEL,
    TEMPLATE_DIR,
    STATIC_DIR,
    SECRET_KEY,
    GROQ_API_KEY,
    GROQ_MODEL,
    AI_DIALOG_TIMEOUT_SECONDS,
    LLM_MAX_RETRIES,
    LLM_MAX_TOKENS_BY_PURPOSE,
    MAX_CONTENT_LENGTH,
    MAX_USER_MESSAGE_CHARS,
    MAX_NOTE_CHARS,
    MAX_HISTORY_MESSAGES,
)

from backend.database import (
    get_db_connection,
    init_database,
)

from backend.security import (
    bootstrap_access_control,
    verify_auth,
)

from backend.services.tutor_core import TutorCore
from backend.services.learner_state import LearnerState
from backend.services.teaching_policy import TeachingPolicy
from backend.services.learner_signals import LearnerSignals
from backend.services.learner_state_transition import LearnerStateTransition
from backend.services.learning_history import LearningHistory
from backend.services.learning_task import LearningTask
from backend.services.learning_session_lifecycle import (
    LearningSessionLifecycle,
    SessionLifecycleError,
)
from backend.services.learning_turn_lease import LearningTurnLease
from backend.services.concept_tracker import ConceptTracker
from backend.services.evidence_evaluator import EvidenceEvaluator
from backend.services.concept_progress import ConceptProgress
from backend.services.review_scheduler import ReviewScheduler
from backend.services.review_queue import ReviewQueue
from backend.services.concept_activation import ConceptActivation
from backend.services.review_lifecycle import ReviewLifecycle
from backend.services.process_learning_turn import ProcessLearningTurn
from backend.services.student_context import StudentContext
from backend.services.llm_gateway import (
    LLMGateway,
    LLMProviderError,
)
from backend.services.observability import Observability
from backend.services.data_lifecycle import (
    DataLifecycle,
    DataLifecycleError,
)
from backend.services.learning_intent import LearningIntent
from backend.services.task_spec import TaskSpec
from backend.services.turn_teaching_contract import TurnTeachingContract
from backend.services.tutor_response_validator import TutorResponseValidator
from backend.services.curriculum import Curriculum
from backend.services.concept_catalog import ConceptCatalog


# ============================================================
# HTTP ADAPTER / APP FACTORY
# ============================================================

bp = Blueprint("apex", __name__)


def _configure_application_logging(application):
    """Alinha logs do Flask ao error logger do Gunicorn sem perder INFO.

    O APEX registra eventos operacionais ``apex_event`` em nível INFO.
    Em produção, o logger padrão do Flask pode permanecer em WARNING,
    descartando esses eventos antes de chegarem ao arquivo do Gunicorn.
    """

    level_name = str(
        application.config.get("LOG_LEVEL", LOG_LEVEL)
    ).strip().upper()

    level = getattr(logging, level_name, logging.INFO)

    gunicorn_logger = logging.getLogger("gunicorn.error")

    if gunicorn_logger.handlers:
        application.logger.handlers = list(gunicorn_logger.handlers)
        application.logger.propagate = False

    application.logger.setLevel(level)


def create_app(config_overrides=None):
    """Cria uma instância Flask sem efeitos de persistência no import.

    A inicialização/migração do banco é responsabilidade explícita do
    bootstrap de execução ou do chamador de teste.
    """

    application = Flask(
        __name__,
        template_folder=str(TEMPLATE_DIR),
        static_folder=str(STATIC_DIR),
    )

    application.config.from_mapping(
        SECRET_KEY=SECRET_KEY,
        MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
        APP_ENV=APP_ENV,
        LOG_LEVEL=LOG_LEVEL,
    )

    if config_overrides:
        application.config.update(config_overrides)

    _configure_application_logging(application)

    application.register_blueprint(bp)
    application.before_request(_begin_request_observability)
    application.after_request(_finish_request_observability)
    application.after_request(_apply_security_headers)
    application.teardown_request(_clear_request_observability)
    return application


# ============================================================
# OBSERVABILIDADE HTTP
# ============================================================

def _begin_request_observability():
    g.apex_request_started_at = time.monotonic()
    g.apex_request_id = Observability.begin_request()


def _finish_request_observability(response):
    request_id = getattr(g, "apex_request_id", None) or Observability.begin_request()
    response.headers.setdefault("X-Apex-Request-ID", request_id)

    started_at = getattr(g, "apex_request_started_at", None)
    latency_ms = (
        Observability.elapsed_ms(started_at)
        if started_at is not None
        else None
    )

    rule = request.url_rule.rule if request.url_rule is not None else None
    Observability.event(
        current_app.logger,
        "http_response_ready",
        method=request.method,
        route=rule,
        endpoint=request.endpoint,
        status_code=response.status_code,
        latency_ms=latency_ms,
    )
    return response


def _clear_request_observability(_error=None):
    Observability.clear()


def _bind_observability_context(context, *, turn_id=None):
    Observability.bind(
        area=context.get("area"),
        turn_id=turn_id,
    )
    Observability.bind_identity(
        student_id=context.get("student_id"),
        session_id=context.get("session_id"),
    )


# ============================================================
# SEGURANCA HTTP / AUTENTICACAO
# ============================================================

def _apply_security_headers(response):
    response.headers.setdefault(
        "X-Content-Type-Options",
        "nosniff",
    )
    response.headers.setdefault(
        "X-Frame-Options",
        "DENY",
    )
    response.headers.setdefault(
        "Referrer-Policy",
        "no-referrer",
    )
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()",
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'",
    )
    return response


def _auth_failure_response():
    if getattr(g, "apex_rate_limited", False):
        Observability.event(
            current_app.logger,
            "auth_rate_limited",
            retry_after=getattr(g, "apex_retry_after", 60),
        )
        response = jsonify(
            {
                "error": "Muitas requisicoes. Aguarde e tente novamente.",
                "code": "rate_limited",
            }
        )
        response.headers["Retry-After"] = str(
            getattr(g, "apex_retry_after", 60)
        )
        return response, 429

    Observability.event(
        current_app.logger,
        "auth_rejected",
        reason="invalid_or_missing_credential",
    )
    return jsonify({"error": "Não autorizado"}), 401


# ============================================================
# SSE
# ============================================================

def sse(data):
    """
    Converte um objeto Python para um
    evento Server-Sent Events (SSE).
    """

    return (
        "data: "
        + json.dumps(
            data,
            ensure_ascii=False,
        )
        + "\n\n"
    )


# ============================================================
# HOME
# ============================================================

@bp.route("/")
def index():
    area = TutorCore.normalize_area(
        request.args.get("area", "ads")
    )
    return render_template(
        "index.html",
        max_history_messages=MAX_HISTORY_MESSAGES,
        area=area,
        area_label="ADS" if area == "ads" else "TI",
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@bp.route(
    "/health",
    methods=["GET"],
)
def health():
    """
    Verifica se:
    - o Flask está respondendo;
    - o SQLite está acessível.
    """

    connection = None

    try:
        connection = get_db_connection()

        connection.execute(
            "SELECT 1"
        ).fetchone()

        return jsonify(
            {
                "ok": True,
                "service": "APEX",
                "database": "ok",
            }
        ), 200

    except sqlite3.Error as exc:

        Observability.exception(
            current_app.logger,
            "health_check_failed",
            error_type=type(exc).__name__,
        )

        return jsonify(
            {
                "ok": False,
                "service": "APEX",
                "database": "error",
            }
        ), 503

    finally:

        if connection is not None:
            connection.close()


# ============================================================
# SESSÃO DE APRENDIZAGEM
# ============================================================

def _resolve_session_request():
    data = request.get_json(silent=True) or {}
    area = TutorCore.normalize_area(data.get("area", request.args.get("area", "ads")))
    context = StudentContext.resolve(area)
    return data, context


def _with_learning_focus(session, context):
    """Projeta o checkpoint pedagógico sem criar estado paralelo no navegador."""
    state = LearnerState.get(
        context["area"],
        student_id=context["student_id"],
    )
    action = TeachingPolicy.choose_action(state)
    next_step_by_action = {
        "explicar": "Leia somente este passo e responda à tarefa apresentada.",
        "verificar": "Explique com suas palavras o que você compreendeu.",
        "testar": "Responda à tarefa atual sem consultar a solução.",
        "corrigir": "Observe o recorte menor e faça uma nova tentativa.",
        "consolidar": "Aplique a mesma ideia na nova tarefa.",
        "revisar": "Recupere de memória e responda à revisão.",
        "avancar": "Percurso atual concluído.",
    }
    if action == "avancar":
        next_concept_id = Curriculum.next_concept_id(
            state.get("current_concept_id")
        )
        next_concept = ConceptCatalog.resolve(
            context["area"],
            next_concept_id,
        )
        if next_concept:
            next_step_by_action["avancar"] = (
                "Envie continuar para iniciar "
                + next_concept["canonical_name"]
                + "."
            )
    return {
        **session,
        "learning_focus": {
            "concept_id": state.get("current_concept_id"),
            "concept": state.get("current_concept"),
            "stage": state.get("stage"),
            "teaching_action": action,
            "next_step": next_step_by_action.get(
                action,
                "Continue a partir do passo atual.",
            ),
        },
    }


@bp.route("/api/session", methods=["GET"])
def session_status():
    if not verify_auth():
        return _auth_failure_response()

    _, context = _resolve_session_request()
    _bind_observability_context(context)
    session = LearningSessionLifecycle.get(
        context["area"],
        student_id=context["student_id"],
        session_id=context["session_id"],
    )
    session = _with_learning_focus(session, context)
    return jsonify({"ok": True, "session": session}), 200


@bp.route("/api/dashboard", methods=["GET"])
def dashboard_status():
    """Projeta a tela inicial a partir do estado autoritativo do servidor."""
    if not verify_auth():
        return _auth_failure_response()

    _, context = _resolve_session_request()
    _bind_observability_context(context)
    session = LearningSessionLifecycle.get(
        context["area"],
        student_id=context["student_id"],
        session_id=context["session_id"],
    )
    session = _with_learning_focus(session, context)
    progress = ConceptProgress.list_all(
        context["area"],
        student_id=context["student_id"],
    )
    due_reviews = ReviewQueue.due(
        context["area"],
        student_id=context["student_id"],
    )
    selectable = ConceptCatalog.list_selectable(context["area"])
    started = [item for item in progress if item.get("updated_at")]
    mastered = [
        item
        for item in started
        if float(item.get("mastery") or 0.0) >= 0.80
    ]
    difficulties = [
        item
        for item in started
        if int(item.get("difficulty_count") or 0) > 0
    ]
    mean_mastery = (
        sum(float(item.get("mastery") or 0.0) for item in started)
        / len(started)
        if started
        else 0.0
    )

    return jsonify(
        {
            "ok": True,
            "area": context["area"],
            "area_label": "ADS" if context["area"] == "ads" else "TI",
            "session": session,
            "selectable_concepts": selectable,
            "progress": progress,
            "due_reviews": due_reviews,
            "difficulties": difficulties,
            "summary": {
                "started": len(started),
                "mastered": len(mastered),
                "due_reviews": len(due_reviews),
                "mean_mastery": round(mean_mastery, 4),
            },
        }
    ), 200


@bp.route("/api/study/start", methods=["POST"])
def start_study():
    """Inicia ou reinicia um conteúdo escolhido na tela inicial."""
    if not verify_auth():
        return _auth_failure_response()

    data, context = _resolve_session_request()
    _bind_observability_context(context)
    concept = ConceptCatalog.resolve(
        context["area"],
        data.get("concept_id"),
        selectable_only=True,
    )
    if concept is None:
        return jsonify({"error": "conteúdo inválido"}), 400

    runtime = LearningSessionLifecycle.get(
        context["area"],
        student_id=context["student_id"],
        session_id=context["session_id"],
    )
    if runtime.get("status") != LearningSessionLifecycle.STUDYING:
        return jsonify(
            {
                "error": "Retome ou conclua a sessão atual antes de iniciar outro conteúdo.",
                "code": "session_not_studying",
            }
        ), 409

    owner = f"study-control-{uuid4().hex}"
    acquired = LearningTurnLease.acquire(
        context["area"],
        owner,
        student_id=context["student_id"],
    )
    if not acquired:
        return jsonify(
            {
                "error": "Há um turno em processamento. Aguarde antes de iniciar o conteúdo.",
                "code": "turn_in_progress",
            }
        ), 409

    try:
        runtime = LearningSessionLifecycle.get(
            context["area"],
            student_id=context["student_id"],
            session_id=context["session_id"],
        )
        if runtime.get("status") != LearningSessionLifecycle.STUDYING:
            return jsonify(
                {
                    "error": "A sessão mudou. Retome ou conclua a sessão atual.",
                    "code": "session_not_studying",
                }
            ), 409
        state = ConceptActivation.activate(
            context["area"],
            concept["concept_id"],
            student_id=context["student_id"],
            restart=data.get("restart") is True,
        )
        runtime = LearningSessionLifecycle.get(
            context["area"],
            student_id=context["student_id"],
            session_id=context["session_id"],
        )
        runtime = _with_learning_focus(runtime, context)
    finally:
        LearningTurnLease.release(
            context["area"],
            owner,
            student_id=context["student_id"],
        )

    Observability.event(
        current_app.logger,
        "home_study_started",
        concept_id=concept["concept_id"],
        restart=data.get("restart") is True,
    )
    return jsonify(
        {"ok": True, "state": state, "session": runtime}
    ), 200


@bp.route("/api/review/start", methods=["POST"])
def start_review():
    """Ativa uma revisão manual ou a próxima revisão programada."""
    if not verify_auth():
        return _auth_failure_response()

    data, context = _resolve_session_request()
    _bind_observability_context(context)
    runtime = LearningSessionLifecycle.get(
        context["area"],
        student_id=context["student_id"],
        session_id=context["session_id"],
    )
    if runtime.get("status") != LearningSessionLifecycle.STUDYING:
        return jsonify(
            {
                "error": "Retome ou conclua a sessão atual antes de iniciar outra revisão.",
                "code": "session_not_studying",
            }
        ), 409

    requested = data.get("concept_id")
    concept = (
        ConceptCatalog.resolve(context["area"], requested)
        if requested
        else None
    )
    if requested and concept is None:
        return jsonify({"error": "conteúdo inválido"}), 400

    owner = f"review-control-{uuid4().hex}"
    acquired = LearningTurnLease.acquire(
        context["area"],
        owner,
        student_id=context["student_id"],
    )
    if not acquired:
        return jsonify(
            {
                "error": "Há um turno em processamento. Aguarde antes de iniciar a revisão.",
                "code": "turn_in_progress",
            }
        ), 409

    try:
        runtime = LearningSessionLifecycle.get(
            context["area"],
            student_id=context["student_id"],
            session_id=context["session_id"],
        )
        if runtime.get("status") != LearningSessionLifecycle.STUDYING:
            return jsonify(
                {
                    "error": "A sessão mudou. Retome ou conclua a sessão atual.",
                    "code": "session_not_studying",
                }
            ), 409
        if concept is None:
            state = ReviewLifecycle.activate_due(
                context["area"],
                student_id=context["student_id"],
            )
            if state is None:
                current = LearnerState.get(
                    context["area"],
                    student_id=context["student_id"],
                )
                if not current.get("current_concept_id"):
                    return jsonify(
                        {"error": "nenhum conteúdo disponível para revisão"}
                    ), 409
                state = LearnerState.update(
                    context["area"],
                    stage="reencontrar",
                    student_id=context["student_id"],
                )
        else:
            progress = ConceptProgress.get(
                context["area"],
                concept["concept_id"],
                student_id=context["student_id"],
            )
            if progress is None or not progress.get("updated_at"):
                return jsonify(
                    {"error": "esse conteúdo ainda não possui progresso para revisar"}
                ), 409
            state = LearnerState.update(
                context["area"],
                current_concept_id=concept["concept_id"],
                stage="reencontrar",
                last_evidence=progress.get("last_evidence") or "",
                difficulty_count=progress.get("difficulty_count", 0),
                mastery=progress.get("mastery", 0.0),
                student_id=context["student_id"],
            )

        runtime = LearningSessionLifecycle.get(
            context["area"],
            student_id=context["student_id"],
            session_id=context["session_id"],
        )
        runtime = _with_learning_focus(runtime, context)
    finally:
        LearningTurnLease.release(
            context["area"],
            owner,
            student_id=context["student_id"],
        )

    Observability.event(
        current_app.logger,
        "home_review_started",
        concept_id=state.get("current_concept_id"),
        scheduled=concept is None,
    )
    return jsonify(
        {"ok": True, "state": state, "session": runtime}
    ), 200


@bp.route("/api/session/pause", methods=["POST"])
def pause_session():
    if not verify_auth():
        return _auth_failure_response()

    _, context = _resolve_session_request()
    _bind_observability_context(context)
    owner = f"session-control-{uuid4().hex}"
    acquired = LearningTurnLease.acquire(
        context["area"],
        owner,
        student_id=context["student_id"],
    )
    if not acquired:
        return jsonify(
            {
                "error": "Há um turno em processamento. Aguarde antes de pausar.",
                "code": "turn_in_progress",
            }
        ), 409

    try:
        session = LearningSessionLifecycle.pause(
            context["area"],
            student_id=context["student_id"],
            session_id=context["session_id"],
        )
        session = _with_learning_focus(session, context)
    except SessionLifecycleError as exc:
        return jsonify({"error": str(exc)}), 409
    finally:
        LearningTurnLease.release(
            context["area"],
            owner,
            student_id=context["student_id"],
        )

    Observability.event(
        current_app.logger,
        "session_transition",
        action="pause",
        status=session.get("status"),
        duplicate=bool(session.get("duplicate")),
    )
    return jsonify({"ok": True, "session": session}), 200


@bp.route("/api/session/resume", methods=["POST"])
def resume_session():
    if not verify_auth():
        return _auth_failure_response()

    data, context = _resolve_session_request()
    _bind_observability_context(context)
    mode = str(data.get("mode", "direct")).strip().lower()
    if mode not in LearningSessionLifecycle.VALID_RESUME_MODES:
        return jsonify({"error": "modo de retomada inválido"}), 400

    owner = f"session-control-{uuid4().hex}"
    acquired = LearningTurnLease.acquire(
        context["area"],
        owner,
        student_id=context["student_id"],
    )
    if not acquired:
        return jsonify(
            {
                "error": "Há um turno em processamento. Aguarde antes de retomar.",
                "code": "turn_in_progress",
            }
        ), 409

    try:
        session = LearningSessionLifecycle.resume(
            context["area"],
            mode=mode,
            student_id=context["student_id"],
            session_id=context["session_id"],
        )
        session = _with_learning_focus(session, context)
    except SessionLifecycleError as exc:
        return jsonify({"error": str(exc)}), 409
    finally:
        LearningTurnLease.release(
            context["area"],
            owner,
            student_id=context["student_id"],
        )

    Observability.event(
        current_app.logger,
        "session_transition",
        action="resume",
        resume_mode=mode,
        status=session.get("status"),
        duplicate=bool(session.get("duplicate")),
    )
    return jsonify({"ok": True, "session": session}), 200


# ============================================================
# CHAT
# ============================================================

@bp.route(
    "/chat/stream",
    methods=["POST"],
)
def chat_stream():

    if not verify_auth():
        return _auth_failure_response()

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    user_message = str(
        data.get(
            "message",
            "",
        )
    ).strip()

    turn_id = str(
        data.get(
            "turn_id",
            "",
        )
    ).strip() or None

    if (
        turn_id is not None
        and len(turn_id) > 128
    ):
        return jsonify(
            {
                "error":
                    "turn_id inválido"
            }
        ), 400

    area = TutorCore.normalize_area(
        data.get(
            "area",
            "ads",
        )
    )

    student_context = StudentContext.resolve(area)
    student_id = student_context["student_id"]
    session_id = student_context["session_id"]
    _bind_observability_context(
        student_context,
        turn_id=turn_id,
    )
    session_runtime = LearningSessionLifecycle.get(
        area,
        student_id=student_id,
        session_id=session_id,
    )
    request_id = getattr(g, "apex_request_id", None)

    if session_runtime.get("status") == LearningSessionLifecycle.PAUSED:
        replay_allowed = False
        if turn_id:
            existing = LearningHistory.find(
                turn_id,
                student_id=student_id,
            )
            replay_allowed = bool(
                existing
                and existing.get("area") == area
                and existing.get("user_message") == user_message
                and existing.get("assistant_message")
            )

        if not replay_allowed:
            return jsonify(
                {
                    "error": "Sessão pausada",
                    "code": "session_paused",
                }
            ), 409

    if not user_message:
        return jsonify(
            {
                "error":
                    "Mensagem obrigatória"
            }
        ), 400

    if (
        len(user_message)
        > MAX_USER_MESSAGE_CHARS
    ):
        return jsonify(
            {
                "error":
                    "Mensagem muito longa. "
                    "Reduza o texto e tente novamente."
            }
        ), 400

    def find_confirmed_response():
        existing_turn = LearningHistory.find(
            turn_id,
            student_id=student_id,
        )

        if existing_turn is None:
            return None

        if (
            existing_turn["area"] != area
            or existing_turn["user_message"]
            != user_message
        ):
            raise ValueError(
                "turn_id reutilizado "
                "com conteúdo diferente"
            )

        return existing_turn.get(
            "assistant_message"
        )

    @stream_with_context
    def generate():

        # O streaming pode continuar depois do teardown inicial do Flask.
        # Reata explicitamente o mesmo request_id ao contexto operacional.
        Observability.begin_request(request_id)
        _bind_observability_context(
            student_context,
            turn_id=turn_id,
        )
        turn_started_at = time.monotonic()
        lease_owner = turn_id or uuid4().hex
        lease_acquired = False

        try:

            previous_response = (
                find_confirmed_response()
            )

            if previous_response:
                Observability.event(
                    current_app.logger,
                    "learning_turn_replay",
                    latency_ms=Observability.elapsed_ms(turn_started_at),
                )
                yield sse(
                    {
                        "token": previous_response
                    }
                )
                yield sse(
                    {
                        "done": True
                    }
                )
                return

            if not GROQ_API_KEY:

                Observability.event(
                    current_app.logger,
                    "learning_turn_blocked",
                    reason="llm_not_configured",
                    latency_ms=Observability.elapsed_ms(turn_started_at),
                )
                yield sse(
                    {
                        "error":
                            "Chave GROQ_API_KEY "
                            "não configurada"
                    }
                )

                return

            lease_acquired = (
                LearningTurnLease.acquire(
                    area,
                    lease_owner,
                    student_id=student_id,
                )
            )

            if not lease_acquired:
                Observability.event(
                    current_app.logger,
                    "learning_turn_blocked",
                    reason="lease_busy",
                    latency_ms=Observability.elapsed_ms(turn_started_at),
                )
                yield sse(
                    {
                        "error":
                            "Já existe um turno "
                            "em processamento nesta área. "
                            "Aguarde a conclusão e "
                            "tente novamente."
                    }
                )
                return

            current_session = LearningSessionLifecycle.get(
                area,
                student_id=student_id,
                session_id=session_id,
            )
            # O estado lido antes da lease pode ter mudado em outro request.
            session_runtime = current_session
            if current_session.get("status") == LearningSessionLifecycle.PAUSED:
                Observability.event(
                    current_app.logger,
                    "learning_turn_blocked",
                    reason="session_paused",
                    latency_ms=Observability.elapsed_ms(turn_started_at),
                )
                yield sse(
                    {
                        "error": "Sessão pausada",
                        "code": "session_paused",
                    }
                )
                return

            # O primeiro turno pode ter sido confirmado entre
            # a consulta inicial e a aquisição da reserva.
            previous_response = (
                find_confirmed_response()
            )

            if previous_response:
                Observability.event(
                    current_app.logger,
                    "learning_turn_replay",
                    latency_ms=Observability.elapsed_ms(turn_started_at),
                )
                yield sse(
                    {
                        "token": previous_response
                    }
                )
                yield sse(
                    {
                        "done": True
                    }
                )
                return

            llm = LLMGateway(
                api_key=GROQ_API_KEY,
                model=GROQ_MODEL,
                timeout_seconds=AI_DIALOG_TIMEOUT_SECONDS,
                max_retries=LLM_MAX_RETRIES,
                max_tokens_by_purpose=LLM_MAX_TOKENS_BY_PURPOSE,
                logger=current_app.logger,
            )

            learner_state = LearnerState.get(
                area,
                student_id=student_id,
            )
            initial_stage = learner_state.get("stage")
            learning_intent = LearningIntent.detect(user_message, area=area)
            progression_target = None
            advance_request = (
                learning_intent.get("kind") == "advance"
                and learner_state.get("stage") == "concluido"
            )
            if advance_request:
                progression_target = Curriculum.next_concept_id(
                    learner_state.get("current_concept_id")
                )
            if (
                session_runtime.get("status") == LearningSessionLifecycle.REVIEWING
                or advance_request
            ):
                tracking_request = None
            else:
                tracking_request = ConceptTracker.build_tracking_request(
                    user_message, learner_state, area
                )
            identification_messages = None
            identified_concept = ConceptTracker.identify_locally(
                user_message,
                area=area,
            )
            if progression_target:
                identified_concept = progression_target
            if learning_intent.get("restart") and not identified_concept:
                identified_concept = learner_state.get("current_concept_id")
            if tracking_request and not identified_concept:
                identification_messages = ConceptTracker.build_identification_messages(
                    tracking_request
                )

            identification_content = None
            if identification_messages:
                try:
                    identification_content = llm.complete_text(
                        identification_messages,
                        purpose=LLMGateway.PURPOSE_CONCEPT_IDENTIFICATION,
                    )
                except LLMProviderError as exc:
                    Observability.exception(
                        current_app.logger,
                        "concept_identification_failed",
                        error_type=type(exc).__name__,
                    )

            if identification_content and not identified_concept:
                identified_concept = ConceptTracker.parse_identification_response(
                    identification_content,
                    area=area,
                )

            learner_state = ProcessLearningTurn.preview_activation(
                area,
                learner_state,
                identified_concept,
                student_id=student_id,
                restart=learning_intent.get("restart", False),
            )

            history = LearningHistory.get_messages(
                area,
                concept_id=learner_state.get(
                    "current_concept_id"
                ),
                student_id=student_id,
            )
            if learning_intent.get("restart"):
                history = []
            else:
                history = LearningIntent.history_since_latest_restart(history)

            evidence_evaluation = None
            if not tracking_request:
                source_turn = LearningHistory.latest_confirmed_turn(
                    area,
                    concept_id=learner_state.get("current_concept_id"),
                    student_id=student_id,
                    session_id=session_id,
                )
                task_context = None
                if source_turn is not None:
                    task_context = LearningTask.find_by_source_turn(
                        source_turn["turn_id"],
                        student_id=student_id,
                        session_id=session_id,
                    )

                if session_runtime.get("status") == LearningSessionLifecycle.REVIEWING:
                    bound_review_task = session_runtime.get("review_task_id")
                    if (
                        not bound_review_task
                        or not isinstance(task_context, dict)
                        or task_context.get("task_id") != bound_review_task
                    ):
                        task_context = None

                evidence_evaluation = EvidenceEvaluator.build_evaluation(
                    user_message,
                    history,
                    learner_state,
                    task_context=task_context,
                )

            semantic_evidence = (
                EvidenceEvaluator.evaluate_objective_task(evidence_evaluation)
                if evidence_evaluation
                else None
            )

            evidence_messages = None
            if evidence_evaluation and semantic_evidence is None:
                evidence_messages = EvidenceEvaluator.build_evaluation_messages(
                    evidence_evaluation
                )

            evidence_content = None
            if evidence_messages:
                try:
                    evidence_content = llm.complete_text(
                        evidence_messages,
                        purpose=LLMGateway.PURPOSE_EVIDENCE_EVALUATION,
                    )
                except LLMProviderError as exc:
                    Observability.exception(
                        current_app.logger,
                        "evidence_evaluation_failed",
                        error_type=type(exc).__name__,
                    )

            if evidence_content and semantic_evidence is None:
                semantic_evidence = EvidenceEvaluator.parse_evaluation_response(
                    evidence_content
                )

            if evidence_evaluation and semantic_evidence is None:
                Observability.event(
                    current_app.logger,
                    "evidence_evaluation_unavailable",
                    source_turn_id=evidence_evaluation.get("source_turn_id"),
                )
                yield sse(
                    {
                        "error": (
                            "Não foi possível avaliar sua resposta com segurança. "
                            "Seu progresso não foi alterado; envie a mesma resposta novamente."
                        )
                    }
                )
                return

            turn_result = ProcessLearningTurn.preview_turn(
                area,
                user_message,
                identified_concept,
                semantic_evidence,
                student_id=student_id,
                session_id=session_id,
                evidence_context=evidence_evaluation,
                restart=learning_intent.get("restart", False),
            )
            learner_state = turn_result["learner_state"]
            teaching_action = turn_result["teaching_action"]
            teaching_contract = TurnTeachingContract.build(
                learner_state,
                teaching_action,
                review_mode=(
                    session_runtime.get("status")
                    == LearningSessionLifecycle.REVIEWING
                    or learner_state.get("stage") == "reencontrar"
                    or teaching_action == "revisar"
                ),
                evidence_outcome=EvidenceEvaluator.feedback_outcome(
                    semantic_evidence
                ),
            )

            messages = (
                TutorCore.build_messages(
                    user_message,
                    history,
                    area=area,
                    learner_state=learner_state,
                    teaching_action=teaching_action,
                    teaching_contract=teaching_contract,
                )
            )

            if (
                learner_state.get("current_concept_id")
                in TurnTeachingContract.CONTROLLED_CONCEPTS
            ):
                # A fatia curricular atual é inteiramente controlada: tarefa,
                # feedback e progressão têm respostas seguras definidas pelo
                # contrato. Não delegar sua redação à LLM impede variações que
                # criariam tarefas sem uma rubrica local correspondente.
                assistant_message = teaching_contract.safe_response
            else:
                assistant_parts = []
                for token in llm.stream_text(
                    messages,
                    purpose=LLMGateway.PURPOSE_TUTOR_RESPONSE,
                ):
                    # Nenhum token não validado atravessa esta fronteira.
                    assistant_parts.append(token)
                assistant_message = "".join(assistant_parts)

            if not assistant_message.strip():
                raise RuntimeError(
                    "Resposta vazia recebida do tutor"
                )

            validation = TutorResponseValidator.validate_or_fallback(
                assistant_message,
                teaching_contract,
            )
            assistant_message = validation["response"]
            task_prompt = TaskSpec.extract(assistant_message)

            committed_result = ProcessLearningTurn.commit_turn(
                area,
                user_message,
                identified_concept,
                semantic_evidence,
                turn_id=turn_id,
                assistant_message=assistant_message,
                student_id=student_id,
                session_id=session_id,
                evidence_context=evidence_evaluation,
                teaching_action=teaching_action,
                observed_assistance_level=validation["assistance_level"],
                task_prompt=task_prompt,
                restart=learning_intent.get("restart", False),
            )

            final_state = committed_result.get("learner_state", {})
            Observability.event(
                current_app.logger,
                "learning_turn_completed",
                latency_ms=Observability.elapsed_ms(turn_started_at),
                stage_before=initial_stage,
                stage_after=final_state.get("stage"),
                teaching_action=committed_result.get("teaching_action"),
                evidence_outcome=(
                    semantic_evidence.get("outcome")
                    if isinstance(semantic_evidence, dict)
                    else None
                ),
                mastery=final_state.get("mastery"),
                duplicate=bool(committed_result.get("duplicate")),
                pedagogical_fallback=bool(validation.get("fallback_used")),
            )

            # A tela recebe apenas conteúdo validado e já confirmado no banco.
            for chunk in TutorResponseValidator.chunks(assistant_message):
                yield sse({"token": chunk})

            yield sse(
                {
                    "done": True
                }
            )

        except Exception as exc:

            Observability.exception(
                current_app.logger,
                "learning_turn_failed",
                error_type=type(exc).__name__,
                latency_ms=Observability.elapsed_ms(turn_started_at),
            )

            yield sse(
                {
                    "error":
                        "Falha temporária "
                        "ao consultar o tutor."
                }
            )

        finally:
            if lease_acquired:
                try:
                    LearningTurnLease.release(
                        area,
                        lease_owner,
                        student_id=student_id,
                    )
                except Exception as exc:
                    Observability.exception(
                        current_app.logger,
                        "turn_lease_release_failed",
                        error_type=type(exc).__name__,
                    )
            Observability.clear()

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":
                "no-cache",

            "X-Accel-Buffering":
                "no",
        },
    )


# ============================================================
# PRIVACIDADE / CICLO DE VIDA DOS DADOS
# ============================================================

@bp.route("/api/privacy/export", methods=["GET"])
def privacy_export():
    if not verify_auth():
        return _auth_failure_response()

    context = StudentContext.resolve("ads")
    _bind_observability_context(context)

    try:
        payload = DataLifecycle.export_student(context["student_id"])
    except DataLifecycleError as exc:
        return jsonify({"error": str(exc)}), 404

    body = DataLifecycle.to_json_bytes(payload)
    Observability.event(
        current_app.logger,
        "privacy_export_completed",
        export_format_version=DataLifecycle.EXPORT_FORMAT_VERSION,
        size_bytes=len(body),
    )

    response = Response(
        body,
        status=200,
        mimetype="application/json",
    )
    response.headers["Content-Disposition"] = (
        "attachment; filename=apex-student-export.json"
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.route("/api/privacy/data", methods=["DELETE"])
def privacy_delete():
    if not verify_auth():
        return _auth_failure_response()

    data = request.get_json(silent=True) or {}
    confirmation = str(data.get("confirmation", "")).strip()
    if confirmation != DataLifecycle.DELETE_CONFIRMATION:
        return jsonify(
            {
                "error": "Confirmação explícita obrigatória.",
                "code": "confirmation_required",
            }
        ), 400

    context = StudentContext.resolve("ads")
    _bind_observability_context(context)
    student_id = context["student_id"]

    try:
        result = DataLifecycle.delete_student(student_id)
    except DataLifecycleError as exc:
        return jsonify({"error": str(exc)}), 404

    Observability.event(
        current_app.logger,
        "privacy_delete_completed",
        receipt_id=result["receipt_id"],
        policy_version=result["policy_version"],
    )

    return jsonify(
        {
            "ok": True,
            "receipt_id": result["receipt_id"],
            "message": "Dados do aluno excluídos.",
        }
    ), 200


# ============================================================
# NOTAS
# ============================================================

@bp.route(
    "/api/notes",
    methods=["POST"],
)
def save_note():

    if not verify_auth():
        return _auth_failure_response()

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    text = str(
        data.get(
            "text",
            "",
        )
    ).strip()

    area = TutorCore.normalize_area(
        data.get(
            "area",
            "ads",
        )
    )

    student_context = StudentContext.resolve(area)
    student_id = student_context["student_id"]
    _bind_observability_context(student_context)

    if not text:

        return jsonify(
            {
                "error":
                    "Texto da nota "
                    "é obrigatório"
            }
        ), 400

    if len(text) > MAX_NOTE_CHARS:
        return jsonify(
            {
                "error":
                    "Texto da nota excede "
                    f"o limite de {MAX_NOTE_CHARS} caracteres."
            }
        ), 400

    connection = get_db_connection()

    try:

        cursor = connection.execute(
            """
            INSERT INTO notes (
                student_id,
                text,
                area
            )
            VALUES (?, ?, ?)
            """,
            (
                student_id,
                text,
                area,
            ),
        )

        connection.commit()

        note_id = cursor.lastrowid

    except sqlite3.Error as exc:

        Observability.exception(
            current_app.logger,
            "note_save_failed",
            error_type=type(exc).__name__,
        )

        return jsonify(
            {
                "error":
                    "Não foi possível "
                    "salvar a nota"
            }
        ), 500

    finally:

        connection.close()

    return jsonify(
        {
            "ok": True,
            "id": note_id,
        }
    )


# ============================================================
# WSGI / EXECUÇÃO LOCAL
# ============================================================

# Compatibilidade com gunicorn backend.app:app e com os testes existentes.
# Criar este objeto NÃO abre nem migra o SQLite.
app = create_app()


if __name__ == "__main__":
    with app.app_context():
        init_database()
        bootstrap_access_control()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=(
            APP_ENV
            == "development"
        ),
    )
