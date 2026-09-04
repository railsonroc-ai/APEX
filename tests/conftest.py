import atexit
import os
from pathlib import Path
import shutil
import tempfile


# O bootstrap de testes acontece antes da coleta dos módulos. Nunca permita
# que pytest herde APEX_DATA_DIR de desenvolvimento/produção.
_PYTEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="APEX_PYTEST_"))
os.environ["APP_ENV"] = "test"
os.environ["APEX_DATA_DIR"] = str(_PYTEST_DATA_DIR)


def _cleanup_pytest_data():
    shutil.rmtree(_PYTEST_DATA_DIR, ignore_errors=True)


atexit.register(_cleanup_pytest_data)

# Inicialização explícita do banco de teste. Importar backend.app deixou de
# ter esse efeito colateral no v15.
from backend.database import init_database  # noqa: E402

init_database()
