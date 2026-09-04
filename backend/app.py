import json
import sqlite3
from uuid import uuid4

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    Response,
    stream_with_context,
)

from groq import Groq

from backend.config import (
    APP_ENV,
    TEMPLATE_DIR,
    STATIC_DIR,
    SECRET_KEY,
    GROQ_API_KEY,
    GROQ_MODEL,
    AI_DIALOG_TIMEOUT_SECONDS,
    MAX_CONTENT_LENGTH,
    MAX_USER_MESSAGE_CHARS,
    MAX_NOTE_CHARS,
    MAX_HISTORY_MESSAGES,
)

from backend.database import (
    get_db_connection,
    init_database,
)

from backend.security import verify_auth

from backend.services.tutor_core import TutorCore
from backend.services.learner_state import LearnerState
from backend.services.teaching_policy import TeachingPolicy
from backend.services.learner_signals import LearnerSignals
from backend.services.learner_state_transition import LearnerStateTransition
from backend.services.learning_history import LearningHistory
from backend.services.learning_task import LearningTask
from backend.services.learning_turn_lease import LearningTurnLease
from backend.services.concept_tracker import ConceptTracker
from backend.services.evidence_evaluator import EvidenceEvaluator
from backend.services.concept_progress import ConceptProgress
from backend.services.review_scheduler import ReviewScheduler
from backend.services.concept_activation import ConceptActivation
from backend.services.review_lifecycle import ReviewLifecycle
from backend.services.process_learning_turn import ProcessLearningTurn
from backend.services.student_context import StudentContext


# ============================================================
# FLASK
# ============================================================

app = Flask(
    __name__,
    template_folder=str(TEMPLATE_DIR),
    static_folder=str(STATIC_DIR),
)

app.config["SECRET_KEY"] = SECRET_KEY

app.config["MAX_CONTENT_LENGTH"] = (
    MAX_CONTENT_LENGTH
)


# ============================================================
# BANCO DE DADOS
# ============================================================

init_database()


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

@app.route("/")
def index():
    return render_template(
        "index.html",
        max_history_messages=MAX_HISTORY_MESSAGES,
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route(
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

    except sqlite3.Error:

        app.logger.exception(
            "Falha no health check"
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
# CHAT
# ============================================================

@app.route(
    "/chat/stream",
    methods=["POST"],
)
def chat_stream():

    if not verify_auth():
        return jsonify(
            {
                "error":
                    "Não autorizado"
            }
        ), 401

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

        lease_owner = turn_id or uuid4().hex
        lease_acquired = False

        try:

            previous_response = (
                find_confirmed_response()
            )

            if previous_response:
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

            # O primeiro turno pode ter sido confirmado entre
            # a consulta inicial e a aquisição da reserva.
            previous_response = (
                find_confirmed_response()
            )

            if previous_response:
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

            client = Groq(
                api_key=GROQ_API_KEY,
                timeout=AI_DIALOG_TIMEOUT_SECONDS,
            )

            learner_state = LearnerState.get(
                area,
                student_id=student_id,
            )
            tracking_request = ConceptTracker.build_tracking_request(
                user_message, learner_state, area
            )
            identification_messages = None
            if tracking_request:
                identification_messages = ConceptTracker.build_identification_messages(
                    tracking_request
                )

            identification_response = None
            if identification_messages:
                try:
                    identification_response = client.chat.completions.create(
                        messages=identification_messages,
                        model=GROQ_MODEL,
                        stream=False,
                    )
                except Exception:
                    app.logger.exception(
                        "Falha na identificacao semantica do conceito"
                    )

            identified_concept = None
            if identification_response:
                try:
                    content = identification_response.choices[0].message.content
                    identified_concept = ConceptTracker.parse_identification_response(
                        content,
                        area=area,
                    )
                except (AttributeError, IndexError, TypeError):
                    identified_concept = None

            learner_state = ProcessLearningTurn.preview_activation(
                area,
                learner_state,
                identified_concept,
                student_id=student_id,
            )

            history = LearningHistory.get_messages(
                area,
                concept_id=learner_state.get(
                    "current_concept_id"
                ),
                student_id=student_id,
            )

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

                evidence_evaluation = EvidenceEvaluator.build_evaluation(
                    user_message,
                    history,
                    learner_state,
                    task_context=task_context,
                )

            evidence_messages = None
            if evidence_evaluation:
                evidence_messages = EvidenceEvaluator.build_evaluation_messages(
                    evidence_evaluation
                )

            evidence_response = None
            if evidence_messages:
                try:
                    evidence_response = client.chat.completions.create(
                        messages=evidence_messages,
                        model=GROQ_MODEL,
                        stream=False,
                    )
                except Exception:
                    app.logger.exception(
                        "Falha na avaliacao semantica da evidencia"
                    )

            semantic_evidence = None
            if evidence_response:
                try:
                    content = evidence_response.choices[0].message.content
                    semantic_evidence = EvidenceEvaluator.parse_evaluation_response(
                        content
                    )
                except (AttributeError, IndexError, TypeError):
                    semantic_evidence = None

            turn_result = ProcessLearningTurn.preview_turn(
                area,
                user_message,
                identified_concept,
                semantic_evidence,
                student_id=student_id,
                session_id=session_id,
                evidence_context=evidence_evaluation,
            )
            learner_state = turn_result["learner_state"]
            teaching_action = turn_result["teaching_action"]

            messages = (
                TutorCore.build_messages(
                    user_message,
                    history,
                    area=area,
                    learner_state=learner_state,
                    teaching_action=teaching_action,
                )
            )

            response = (
                client
                .chat
                .completions
                .create(
                    messages=messages,
                    model=GROQ_MODEL,
                    stream=True,
                )
            )

            assistant_parts = []

            for chunk in response:

                if (
                    chunk.choices
                    and
                    chunk
                    .choices[0]
                    .delta
                    .content
                ):

                    token = (
                        chunk
                        .choices[0]
                        .delta
                        .content
                    )

                    assistant_parts.append(
                        token
                    )

                    yield sse(
                        {
                            "token": token
                        }
                    )

            assistant_message = "".join(
                assistant_parts
            )

            if not assistant_message.strip():
                raise RuntimeError(
                    "Resposta vazia recebida do tutor"
                )

            ProcessLearningTurn.commit_turn(
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
            )

            yield sse(
                {
                    "done": True
                }
            )

        except Exception:

            app.logger.exception(
                "Falha no streaming Groq"
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
                except Exception:
                    app.logger.exception(
                        "Falha ao liberar reserva do turno"
                    )

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
# NOTAS
# ============================================================

@app.route(
    "/api/notes",
    methods=["POST"],
)
def save_note():

    if not verify_auth():

        return jsonify(
            {
                "error":
                    "Não autorizado"
            }
        ), 401

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

    except sqlite3.Error:

        app.logger.exception(
            "Falha ao salvar nota"
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
# EXECUÇÃO LOCAL
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=(
            APP_ENV
            == "development"
        ),
    )
