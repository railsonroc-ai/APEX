import secrets

from flask import request

from backend.config import (
    APP_ENV,
    APEX_ACCESS_KEY,
)


def verify_auth():
    """
    Valida a chave enviada pelo navegador.

    Desenvolvimento:
    - se APEX_ACCESS_KEY estiver vazia,
      permite acesso.

    Produção:
    - APEX_ACCESS_KEY é obrigatória.

    Quando existe uma chave configurada,
    compara o cabeçalho X-Apex-Key usando
    comparação resistente a timing attacks.
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