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


def resolve_log_level():
    value = os.getenv(
        "APEX_LOG_LEVEL",
        "INFO",
    ).strip().upper()

    allowed = {
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    }

    if value not in allowed:
        raise RuntimeError(
            "APEX_LOG_LEVEL deve ser um de: "
            + ", ".join(sorted(allowed))
        )

    return value


LOG_LEVEL = resolve_log_level()


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
# TIMEOUT DA IA
# ============================================================

def resolve_ai_dialog_timeout():
    """
    Resolve o tempo máximo, em segundos,
    permitido para chamadas ao provedor de IA.
    """

    raw_value = os.getenv(
        "AI_DIALOG_TIMEOUT_SECONDS",
        "45",
    ).strip()

    try:
        timeout = float(
            raw_value
        )

    except ValueError as exc:
        raise RuntimeError(
            "AI_DIALOG_TIMEOUT_SECONDS "
            "deve ser um número válido."
        ) from exc

    if timeout <= 0:
        raise RuntimeError(
            "AI_DIALOG_TIMEOUT_SECONDS "
            "deve ser maior que zero."
        )

    return timeout


AI_DIALOG_TIMEOUT_SECONDS = (
    resolve_ai_dialog_timeout()
)


def _resolve_positive_int_env(name, default, *, maximum=8192):
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} deve ser um inteiro válido.") from exc
    if value <= 0 or value > maximum:
        raise RuntimeError(
            f"{name} deve estar entre 1 e {maximum}."
        )
    return value


def _resolve_non_negative_int_env(name, default, *, maximum=5):
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} deve ser um inteiro válido.") from exc
    if value < 0 or value > maximum:
        raise RuntimeError(
            f"{name} deve estar entre 0 e {maximum}."
        )
    return value


LLM_MAX_RETRIES = _resolve_non_negative_int_env(
    "LLM_MAX_RETRIES",
    1,
)

LLM_IDENTIFICATION_MAX_TOKENS = _resolve_positive_int_env(
    "LLM_IDENTIFICATION_MAX_TOKENS",
    160,
)

LLM_EVIDENCE_MAX_TOKENS = _resolve_positive_int_env(
    "LLM_EVIDENCE_MAX_TOKENS",
    480,
)

LLM_TUTOR_MAX_TOKENS = _resolve_positive_int_env(
    "LLM_TUTOR_MAX_TOKENS",
    1200,
)

LLM_MAX_TOKENS_BY_PURPOSE = {
    "concept_identification": LLM_IDENTIFICATION_MAX_TOKENS,
    "evidence_evaluation": LLM_EVIDENCE_MAX_TOKENS,
    "tutor_response": LLM_TUTOR_MAX_TOKENS,
}


# A reserva do turno cobre, sem manter uma transação SQLite
# aberta, a avaliação/identificação e o streaming da resposta.
# A folga também permite que uma reserva abandonada expire.
TURN_LEASE_SECONDS = max(
    180,
    int(
        AI_DIALOG_TIMEOUT_SECONDS
        * 3
    ),
)


# ============================================================
# PRIVACIDADE / RETENCAO
# ============================================================

PRIVACY_RETENTION_DAYS = _resolve_positive_int_env(
    "PRIVACY_RETENTION_DAYS",
    365,
    maximum=3650,
)

if PRIVACY_RETENTION_DAYS < 30:
    raise RuntimeError(
        "PRIVACY_RETENTION_DAYS deve ser pelo menos 30."
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
# - metadados JSON.
#
# O limite continua pequeno o bastante para proteger a API,
# e permite transportar com segurança a mensagem atual.
MAX_CONTENT_LENGTH = (
    128 * 1024
)

MAX_USER_MESSAGE_CHARS = 4000
MAX_NOTE_CHARS = 4000

MAX_HISTORY_MESSAGES = 8


# ============================================================
# SQLITE
# ============================================================

SQLITE_TIMEOUT_SECONDS = 10

SQLITE_BUSY_TIMEOUT_MS = 10000
