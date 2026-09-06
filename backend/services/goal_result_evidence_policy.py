"""Deterministic evidence policy for the APEX 'resultado esperado' microconcept.

The policy is deliberately narrow: it only upgrades a PARTIAL evaluation when
(1) the active task explicitly asks for the expected result,
(2) the learner obeys the required ``Resultado:`` format, and
(3) the resulting-state answer preserves the concrete object anchor from the
activity (e.g. mochila, louça, documento, celular).

It does not change unrelated partial assessments.
"""
from __future__ import annotations

from copy import deepcopy
import re
import unicodedata
from typing import Any

POLICY_ID = "APEX_GOAL_RESULT_EVIDENCE_POLICY_V3"

_PARTIAL = {
    "partial", "partially_correct", "partially correct", "parcial",
    "parcialmente_correto", "parcialmente correto",
}
_STOP = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da",
    "dos", "das", "para", "pra", "por", "com", "sem", "em", "no", "na",
    "nos", "nas", "ao", "aos", "e", "ou", "que", "se", "ser", "estar",
    "atividade", "tarefa", "resultado", "esperado", "escreva", "somente",
    "comecando", "começando", "comece", "responda", "atual", "objetivo",
    "sequencia", "sequência", "organizar", "lavar", "salvar", "carregar",
}
_CONTEXT_KEYS = (
    "task_prompt", "tutor_message", "task", "current_task", "prompt",
    "instruction", "question", "exercise", "atividade", "tarefa",
)
_ANSWER_KEYS = ("student_answer", "answer", "user_message", "response", "resposta")


def _fold(text: Any) -> str:
    raw = str(text or "")
    raw = "".join(
        ch for ch in unicodedata.normalize("NFKD", raw)
        if not unicodedata.combining(ch)
    )
    return raw.casefold().strip()


def _norm_verdict(value: Any) -> str:
    return _fold(value).replace("-", "_")


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _fold(text))


def _stem(token: str) -> str:
    # Enough for the controlled Portuguese task family: organizar/organizada,
    # salvar/salvo, carregar/carregando etc. Object nouns remain unchanged.
    t = token
    for suffix in (
        "amentos", "imentos", "amento", "imento", "adas", "ados", "ando",
        "endo", "indo", "ada", "ado", "idas", "idos", "ida", "ido",
        "ar", "er", "ir",
    ):
        if len(t) >= len(suffix) + 4 and t.endswith(suffix):
            return t[:-len(suffix)]
    return t


def _collect_context_text(task_prompt: Any, evidence_context: Any) -> str:
    parts: list[str] = []
    if isinstance(task_prompt, str) and task_prompt.strip():
        parts.append(task_prompt)
    if isinstance(evidence_context, dict):
        for key in _CONTEXT_KEYS:
            value = evidence_context.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value)
    return "\n".join(parts)


def _collect_answer(user_message: Any, evidence_context: Any) -> str:
    if isinstance(evidence_context, dict):
        for key in _ANSWER_KEYS:
            value = evidence_context.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return str(user_message or "").strip()


def _is_goal_result_task(task_text: str) -> bool:
    folded = _fold(task_text)
    return "resultado esperado" in folded


def _activity_phrase(task_text: str) -> str:
    folded = _fold(task_text)
    # Prefer the explicit activity after "resultado esperado de ...".
    match = re.search(
        r"resultado esperado\s+de\s+(.+?)(?:,|\.|\n|\bcomecando\b|\bcomece\b|$)",
        folded,
    )
    if match:
        return match.group(1).strip()
    match = re.search(r"para a atividade\s+(.+?)(?:,|\.|\n|$)", folded)
    return match.group(1).strip() if match else folded


def _primary_object_anchor(task_text: str) -> str | None:
    phrase = _activity_phrase(task_text)
    tokens = _tokens(phrase)
    if not tokens:
        return None

    # Controlled activities are normally "<verbo no infinitivo> [det.] <objeto>".
    # Skip the leading infinitive verb, then determiners/prepositions/instruction words.
    start = 1 if tokens and tokens[0].endswith(("ar", "er", "ir")) else 0
    for token in tokens[start:]:
        if token in _STOP or len(token) < 3:
            continue
        return _stem(token)

    # Fallback: first meaningful content token.
    for token in tokens:
        if token not in _STOP and len(token) >= 3:
            return _stem(token)
    return None


def _valid_result_answer(task_text: str, answer: str) -> bool:
    if not _is_goal_result_task(task_text):
        return False
    match = re.match(r"^\s*resultado\s*:\s*(.+?)\s*$", _fold(answer), flags=re.S)
    if not match:
        return False
    body = match.group(1).strip()
    if len(body) < 3:
        return False
    anchor = _primary_object_anchor(task_text)
    if not anchor:
        return False
    answer_stems = {_stem(tok) for tok in _tokens(body) if len(tok) >= 3}
    return anchor in answer_stems


def normalize_goal_result_evidence(
    semantic_evidence: Any,
    *,
    task_prompt: Any = None,
    evidence_context: Any = None,
    user_message: Any = None,
) -> Any:
    """Upgrade only a false PARTIAL on an explicit expected-result task."""
    if not isinstance(semantic_evidence, dict):
        return semantic_evidence

    outcome = semantic_evidence.get("outcome")
    if _norm_verdict(outcome) not in _PARTIAL:
        return semantic_evidence

    task_text = _collect_context_text(task_prompt, evidence_context)
    answer = _collect_answer(user_message, evidence_context)
    if not _valid_result_answer(task_text, answer):
        return semantic_evidence

    out = deepcopy(semantic_evidence)
    out["outcome"] = "demonstrated"
    out["policy_adjustment"] = POLICY_ID
    out["missing_essential_criteria"] = []
    previous = str(out.get("evidence") or "").strip()
    note = (
        "Critério essencial satisfeito: a resposta identifica o estado final do "
        "objeto da atividade no formato solicitado, sem exigir consequências posteriores."
    )
    out["evidence"] = f"{previous} {note}".strip()
    return out
