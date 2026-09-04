import json
import re
import subprocess
from pathlib import Path


def test_clean_text_preserves_programming_syntax():
    source = Path(
        "backend/static/js/chat-engine.js"
    ).read_text()

    match = re.search(
        r"function cleanText\(text\) \{.*?\n  \}",
        source,
        re.DOTALL,
    )

    assert match is not None

    cases = [
        "lista[0]",
        "const a = [1, 2, 3];",
        "if (arr[i] > 0) {}",
        "x = matrix[row][col]",
        r'print("Olá\nMundo")',
    ]

    script = (
        match.group(0)
        + "\n"
        + "const cases = "
        + json.dumps(cases, ensure_ascii=False)
        + ";\n"
        + "console.log(JSON.stringify(cases.map(cleanText)));"
    )

    result = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(result.stdout) == cases
