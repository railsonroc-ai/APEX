import secrets
import sqlite3

from flask import g, request

from backend.config import (
    APP_ENV,
    APEX_ACCESS_KEY,
    AUTH_RATE_LIMIT_REQUESTS,
    AUTH_RATE_LIMIT_WINDOW_SECONDS,
)
from backend.identity import DEFAULT_STUDENT_ID
from backend.services.access_control import (
    AccessControl,
    AccessRateLimiter,
)


def _set_auth_context(student_id, credential_id, source):
    g.apex_student_id = student_id
    g.apex_credential_id = credential_id
    g.apex_auth_source = source
    g.apex_rate_limited = False


def bootstrap_access_control():
    """Provisiona a credencial padrao depois das migrations.

    O segredo em texto puro permanece apenas na configuracao do processo; o
    SQLite recebe somente seu hash.
    """

    if not APEX_ACCESS_KEY:
        return None

    return AccessControl.ensure_default_credential(
        APEX_ACCESS_KEY,
        student_id=DEFAULT_STUDENT_ID,
    )


def verify_auth():
    """Autentica a requisicao e vincula a identidade ao request context.

    Desenvolvimento/teste sem chave preservam o modo local historico. Quando
    existe uma chave, credenciais persistidas sao a autoridade principal. A
    comparacao com APEX_ACCESS_KEY permanece como fallback de bootstrap para
    execucao local e rotacao segura da credencial padrao.
    """

    g.apex_rate_limited = False

    if APP_ENV == "production" and not APEX_ACCESS_KEY:
        return False

    if not APEX_ACCESS_KEY:
        try:
            AccessControl.ensure_student_runtime(DEFAULT_STUDENT_ID)
        except sqlite3.Error:
            return False
        _set_auth_context(
            DEFAULT_STUDENT_ID,
            "development-default",
            "development-open",
        )
        return True

    client_key = str(
        request.headers.get(
            "X-Apex-Key",
            "",
        )
    ).strip()

    if not client_key:
        return False

    credential = None

    try:
        credential = AccessControl.authenticate(client_key)
    except sqlite3.Error:
        # A execucao correta aplica migrations antes de atender trafego. O
        # fallback abaixo existe apenas para bootstrap/local e nao mascara uma
        # chave incorreta.
        credential = None

    if credential is not None:
        student_id = credential["student_id"]
        credential_id = credential["credential_id"]
        source = "database"
    elif secrets.compare_digest(client_key, APEX_ACCESS_KEY):
        student_id = DEFAULT_STUDENT_ID
        credential_id = "environment-default"
        source = "environment-fallback"
        try:
            AccessControl.ensure_student_runtime(student_id)
        except sqlite3.Error:
            return False
    else:
        return False

    try:
        allowed = AccessRateLimiter.allow(
            credential_id,
            limit=AUTH_RATE_LIMIT_REQUESTS,
            window_seconds=AUTH_RATE_LIMIT_WINDOW_SECONDS,
        )
    except sqlite3.Error:
        # Falha fechada: se o controle compartilhado nao esta disponivel, nao
        # liberamos uma rota protegida sem conseguir aplicar a quota.
        return False

    if not allowed:
        g.apex_rate_limited = True
        g.apex_retry_after = AUTH_RATE_LIMIT_WINDOW_SECONDS
        return False

    _set_auth_context(
        student_id,
        credential_id,
        source,
    )
    return True
