import sqlite3

from flask import g

from backend.identity import DEFAULT_STUDENT_ID
from backend.services.access_control import AccessControl


def _set_open_context():
    g.apex_student_id = DEFAULT_STUDENT_ID
    g.apex_credential_id = "single-user-open"
    g.apex_auth_source = "single-user-open"
    g.apex_rate_limited = False


def bootstrap_access_control():
    """Prepara o aluno padrao sem exigir credencial de acesso.

    O APEX 1.0 e um produto individual. O bootstrap apenas garante que o
    aluno/sessoes padrao existam; nenhuma senha, API key ou prompt de acesso
    e provisionado para o uso normal.
    """

    return AccessControl.ensure_student_runtime(DEFAULT_STUDENT_ID)


def verify_auth():
    """Mantem a fronteira de identidade aberta para o aluno padrao.

    As rotas existentes continuam chamando ``verify_auth`` para preservar o
    contrato interno, mas o APEX individual nao exige autenticacao do usuario.
    Nenhum header ``X-Apex-Key`` e lido e nenhum rate limit de credencial e
    aplicado nesta fronteira.
    """

    try:
        AccessControl.ensure_student_runtime(DEFAULT_STUDENT_ID)
    except sqlite3.Error:
        return False

    _set_open_context()
    return True
