import os
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# CAMINHOS DO PROJETO
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


# ============================================================
# VARIÁVEIS DE AMBIENTE
# ============================================================

load_dotenv(
    PROJECT_ROOT / ".env"
)


APP_ENV = os.getenv(
    "APP_ENV",
    "development",
).strip().lower()


APEX_ACCESS_KEY = os.getenv(
    "APEX_ACCESS_KEY",
    "",
).strip()


SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "",
).strip()


if not SECRET_KEY:

    if APP_ENV == "production":
        raise RuntimeError(
            "SECRET_KEY deve ser configurada "
            "em ambiente de produção."
        )

    SECRET_KEY = "dev-secret-key"


GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY",
    "",
).strip()


GROQ_MODEL = (
    os.getenv(
        "GROQ_MODEL",
        "groq/compound",
    ).strip()
    or "groq/compound"
)


# ============================================================
# DADOS
# ============================================================

def resolve_data_dir():
    """
    Resolve o diretório persistente do APEX.

    Caminho absoluto:
    - utilizado diretamente.

    Caminho relativo:
    - resolvido a partir da raiz do projeto.
    """

    configured_path = os.getenv(
        "APEX_DATA_DIR",
        "./data",
    ).strip()

    path = Path(configured_path)

    if path.is_absolute():
        return path.resolve()

    return (
        PROJECT_ROOT
        / path
    ).resolve()


DATA_DIR = resolve_data_dir()

DATABASE_PATH = (
    DATA_DIR
    / "apex.db"
)


# ============================================================
# LIMITES HTTP / CHAT
# ============================================================

# A requisição contém:
# - mensagem atual;
# - histórico recente;
# - metadados JSON.
#
# O limite continua pequeno o bastante para proteger a API,
# mas permite transportar com segurança o contexto válido
# utilizado pelo TutorCore.
MAX_CONTENT_LENGTH = (
    128 * 1024
)

MAX_USER_MESSAGE_CHARS = 4000

MAX_HISTORY_MESSAGES = 8


# ============================================================
# SQLITE
# ============================================================

SQLITE_TIMEOUT_SECONDS = 10

SQLITE_BUSY_TIMEOUT_MS = 10000