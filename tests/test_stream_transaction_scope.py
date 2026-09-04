import ast
from pathlib import Path


def transaction_blocks():
    source = Path("backend/app.py").read_text()
    tree = ast.parse(source)

    blocks = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue

        for item in node.items:
            expression = item.context_expr

            if (
                isinstance(expression, ast.Call)
                and isinstance(expression.func, ast.Name)
                and expression.func.id == "transaction"
            ):
                blocks.append(node)

    return source, blocks


def test_database_transaction_does_not_wrap_llm_calls():
    source, blocks = transaction_blocks()

    for block in blocks:
        fragment = ast.get_source_segment(
            source,
            block,
        ) or ""

        assert "Groq(" not in fragment
        assert ".completions.create(" not in fragment


def test_database_transaction_does_not_wrap_sse_streaming():
    _, blocks = transaction_blocks()

    for block in blocks:
        assert not any(
            isinstance(node, (ast.Yield, ast.YieldFrom))
            for node in ast.walk(block)
        )
