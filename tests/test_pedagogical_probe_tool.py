import importlib.util
from pathlib import Path


MODULE_PATH = Path("tools/apex_pedagogical_probe.py")
spec = importlib.util.spec_from_file_location("apex_pedagogical_probe", MODULE_PATH)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_extract_task_reads_single_task():
    text = "Correto.\n\nTarefa: escreva somente o resultado esperado de salvar um documento."
    assert probe.extract_task(text) == "escreva somente o resultado esperado de salvar um documento."


def test_extract_task_rejects_multiple_tasks():
    text = "Tarefa: uma.\n\nTarefa: duas."
    assert probe.extract_task(text) is None


def test_feedback_outcome_maps_correct():
    assert probe.feedback_outcome("Correto.\n\nTarefa: próxima") == "demonstrated"


def test_feedback_outcome_maps_partial():
    assert probe.feedback_outcome("Parcialmente correto.\n\nTarefa: tente novamente") == "partial"


def test_classify_goal_result_tasks():
    assert probe.classify_task(
        "escreva somente o resultado esperado de salvar um documento."
    ) == "goal_document_saved"
    assert probe.classify_task(
        "escreva somente o resultado esperado de lavar a louça."
    ) == "goal_dishes_clean"
    assert probe.classify_task(
        "escreva somente o resultado esperado de organizar uma mochila para a aula."
    ) == "goal_backpack_organized"


def test_correct_result_answers_do_not_depend_on_result_label():
    for kind in (
        "goal_document_saved",
        "goal_dishes_clean",
        "goal_backpack_organized",
        "goal_teeth_clean_review",
    ):
        assert not probe.fold_text(probe.correct_answer(kind)).startswith("resultado")


def test_parse_sse_collects_tokens_and_done():
    raw = (
        'data: {"token":"Correto."}\n\n'
        'data: {"token":"\\n\\nTarefa: próxima"}\n\n'
        'data: {"done":true}\n\n'
    )
    parsed = probe.parse_sse(raw)
    assert parsed["text"] == "Correto.\n\nTarefa: próxima"
    assert parsed["done"] is True
    assert parsed["errors"] == []


def test_parse_sse_collects_error():
    raw = 'data: {"error":"Sessão pausada","code":"session_paused"}\n\n'
    parsed = probe.parse_sse(raw)
    assert parsed["errors"] == ["Sessão pausada"]
    assert parsed["done"] is False
