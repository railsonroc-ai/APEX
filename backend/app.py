import json
import sqlite3

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

    history = data.get(
        "history",
        [],
    )

    area = TutorCore.normalize_area(
        data.get(
            "area",
            "ads",
        )
    )

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

    @stream_with_context
    def generate():

        try:

            if not GROQ_API_KEY:

                yield sse(
                    {
                        "error":
                            "Chave GROQ_API_KEY "
                            "não configurada"
                    }
                )

                return

            client = Groq(
                api_key=GROQ_API_KEY,
                timeout=AI_DIALOG_TIMEOUT_SECONDS,
            )

            learner_state = LearnerState.get(area)
            signals = LearnerSignals.detect(user_message)
            state_changes = LearnerStateTransition.from_signals(learner_state, signals)
            if state_changes:
                learner_state = LearnerState.update(area, **state_changes)
            teaching_action = TeachingPolicy.choose_action(learner_state)

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

            for chunk in response:

                if (
                    chunk.choices
                    and
                    chunk
                    .choices[0]
                    .delta
                    .content
                ):

                    yield sse(
                        {
                            "token":
                                chunk
                                .choices[0]
                                .delta
                                .content
                        }
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

    if not text:

        return jsonify(
            {
                "error":
                    "Texto da nota "
                    "é obrigatório"
            }
        ), 400

    text = text[:4000]

    connection = get_db_connection()

    try:

        cursor = connection.execute(
            """
            INSERT INTO notes (
                text,
                area
            )
            VALUES (?, ?)
            """,
            (
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