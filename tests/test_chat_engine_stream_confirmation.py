import re
from pathlib import Path


SOURCE = Path(
    "backend/static/js/chat-engine.js"
).read_text()


def extract_between(start_pattern, end_pattern):
    match = re.search(
        start_pattern + r"(.*?)" + end_pattern,
        SOURCE,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def test_stream_requires_explicit_done_confirmation():
    stream = extract_between(
        r"async function streamChat\(",
        r"// ENVIAR MENSAGEM",
    )

    # done é quem autoriza a finalização normal.
    assert re.search(
        r"onDone:\s*\(\)\s*=>\s*\{"
        r".*?finalizeBotMessage\("
        r".*?finalized\s*=\s*true;",
        stream,
        re.DOTALL,
    )

    # EOF sem done deve ser erro.
    assert re.search(
        r"if\s*\(\s*!finalized"
        r"\s*&&\s*!streamError\s*\)"
        r"\s*\{"
        r".*?streamError\s*=\s*true;"
        r".*?showBotError\(",
        stream,
        re.DOTALL,
    )

    assert (
        "Resposta interrompida antes da confirmação do servidor."
        in stream
    )

    # Só um turno confirmado retorna o texto.
    assert re.search(
        r"if\s*\(\s*finalized"
        r"\s*&&\s*!streamError\s*\)"
        r"\s*\{\s*return fullText;",
        stream,
        re.DOTALL,
    )

    # Falha/EOF sem confirmação retorna null.
    assert "return null;" in stream

    # streamChat não deve mais escrever no histórico.
    assert "addToHistory(" not in stream


def test_history_is_committed_only_after_confirmed_stream():
    send = extract_between(
        r"async function sendMessage\(\)\s*\{",
        r"// LIMPAR CONVERSA",
    )

    assert re.search(
        r"const assistantText\s*="
        r".*?await streamChat\(",
        send,
        re.DOTALL,
    )

    confirmed = re.search(
        r"if\s*\(\s*assistantText\s*!==\s*null\s*\)"
        r"\s*\{(.*?)\n\s*\}",
        send,
        re.DOTALL,
    )

    assert confirmed is not None

    block = confirmed.group(1)

    assert re.search(
        r"addToHistory\(\s*'user'\s*,\s*text\s*\)",
        block,
        re.DOTALL,
    )

    assert re.search(
        r"addToHistory\("
        r"\s*'assistant'\s*,\s*assistantText\s*\)",
        block,
        re.DOTALL,
    )

    # Antes de aguardar o stream não pode haver commit
    # da mensagem atual no histórico.
    before_stream = send.split(
        "const assistantText",
        1,
    )[0]

    assert not re.search(
        r"addToHistory\(\s*'user'\s*,\s*text\s*\)",
        before_stream,
        re.DOTALL,
    )
