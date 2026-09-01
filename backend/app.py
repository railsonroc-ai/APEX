import os
import json
import secrets
import sqlite3

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    Response,
    stream_with_context,
)

from dotenv import load_dotenv
from groq import Groq

from backend.services.tutor_core import TutorCore


load_dotenv()


# ============================================================
# CAMINHOS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PROJECT_ROOT = os.path.dirname(
    BASE_DIR
)


def resolve_data_dir():
    """
    Define onde os dados persistentes do APEX serão armazenados.

    Se APEX_DATA_DIR estiver configurado:
    - caminho absoluto: usa diretamente;
    - caminho relativo: resolve a partir da raiz do projeto.

    Se não estiver configurado:
    - usa /data na raiz do projeto.
    """

    configured_path = os.getenv(
        "APEX_DATA_DIR",
        "./data",
    ).strip()

    if os.path.isabs(configured_path):
        return os.path.abspath(
            configured_path
        )

    return os.path.abspath(
        os.path.join(
            PROJECT_ROOT,
            configured_path,
        )
    )


DATA_DIR = resolve_data_dir()

DATABASE_PATH = os.path.join(
    DATA_DIR,
    "apex.db",
)


# ============================================================
# FLASK
# ============================================================

app = Flask(
    __name__,
    template_folder=os.path.join(
        BASE_DIR,
        "templates",
    ),
    static_folder=os.path.join(
        BASE_DIR,
        "static",
    ),
)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "dev-secret-key",
)

app.config["MAX_CONTENT_LENGTH"] = (
    32 * 1024
)


# ============================================================
# LIMITES
# ============================================================

MAX_USER_MESSAGE_CHARS = 4000


# ============================================================
# AMBIENTE / SEGURANÇA
# ============================================================

APP_ENV = os.getenv(
    "APP_ENV",
    "development",
)

APEX_ACCESS_KEY = os.getenv(
    "APEX_ACCESS_KEY",
    "",
)


def verify_auth():
    """
    Valida a chave enviada pelo navegador.

    Em desenvolvimento:
    - se APEX_ACCESS_KEY estiver vazia,
      permite acesso.

    Em produção:
    - a chave é obrigatória.
    """

    if (
        APP_ENV == "production"
        and not APEX_ACCESS_KEY
    ):
        return False

    if not APEX_ACCESS_KEY:
        return True

    client_key = request.headers.get(
        "X-Apex-Key",
        "",
    )

    return secrets.compare_digest(
        client_key,
        APEX_ACCESS_KEY,
    )


# ============================================================
# BANCO DE DADOS
# ============================================================

def get_db_connection():
    """
    Abre uma nova conexão SQLite.

    Cada conexão recebe:
    - espera de até 10 segundos por locks;
    - foreign keys habilitadas.
    """

    os.makedirs(
        DATA_DIR,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=10,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA busy_timeout = 10000"
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def init_database():
    """
    Inicializa e configura o banco.

    WAL permite melhor convivência entre
    leituras e gravações concorrentes.
    """

    connection = get_db_connection()

    try:
        connection.execute(
            "PRAGMA journal_mode = WAL"
        )

        connection.execute(
            "PRAGMA synchronous = NORMAL"
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                area TEXT NOT NULL,
                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.commit()

    finally:
        connection.close()


init_database()


# ============================================================
# SSE
# ============================================================

def sse(data):
    """
    Converte um objeto Python para um evento SSE.
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
        "index.html"
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
    Health check usado pelo deploy.

    Verifica:
    - Flask;
    - acesso ao SQLite.
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
                "error": "Não autorizado"
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

            api_key = os.getenv(
                "GROQ_API_KEY"
            )

            if not api_key:

                yield sse(
                    {
                        "error":
                            "Chave GROQ_API_KEY "
                            "não configurada"
                    }
                )

                return

            client = Groq(
                api_key=api_key
            )

            messages = (
                TutorCore.build_messages(
                    user_message,
                    history,
                    area=area,
                )
            )

            response = (
                client
                .chat
                .completions
                .create(
                    messages=messages,
                    model=os.getenv(
                        "GROQ_MODEL",
                        "groq/compound",
                    ),
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
        debug=True,
    )