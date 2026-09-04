import ast
from pathlib import Path


def test_app_does_not_import_groq_sdk_directly():
    source = Path("backend/app.py").read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name != "groq" for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module != "groq"


def test_app_does_not_call_provider_completions_directly():
    source = Path("backend/app.py").read_text()
    assert ".chat.completions.create(" not in source
    assert ".completions.create(" not in source
    assert "LLMGateway(" in source


def test_gateway_is_only_runtime_module_that_imports_groq_sdk():
    backend = Path("backend")
    offenders = []

    for path in backend.rglob("*.py"):
        if path == backend / "services" / "llm_gateway.py":
            continue
        source = path.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name == "groq" for alias in node.names):
                    offenders.append(str(path))
            elif isinstance(node, ast.ImportFrom) and node.module == "groq":
                offenders.append(str(path))

    assert offenders == []
