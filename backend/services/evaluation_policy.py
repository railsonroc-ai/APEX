"""Conservative semantic-evaluation guard for APEX.

V2 intentionally patches only real evaluator callables defined in the module
that installs it. It never patches imported classes such as LearningHistory,
RubricAssessment, LearnerState, or identity/ledger services.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
import inspect
from pathlib import Path
from typing import Any

CONTRACT_MARKER = "[APEX_PEDAGOGICAL_EVALUATION_CONTRACT_V2]"
_PARTIAL_VALUES = {
    "partial", "partially_correct", "partially correct", "parcial",
    "parcialmente_correto", "parcialmente correto",
}
_MISSING_KEYS = (
    "missing_essential_criteria",
    "missing_criteria",
    "missing_criterion",
    "essential_missing",
    "lacunas_essenciais",
    "criterios_essenciais_ausentes",
    "criterio_essencial_ausente",
)
_VERDICT_KEYS = (
    "outcome", "verdict", "status", "classification", "evaluation", "result",
    "resultado", "classificacao",
)


def load_evaluation_contract() -> str:
    path = Path(__file__).resolve().parents[1] / "prompts" / "evaluation_contract.txt"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return text if CONTRACT_MARKER in text else ""


def _is_empty_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _norm(value: Any) -> str:
    return str(value).strip().casefold().replace("-", "_")


def postprocess_evaluation_result(value: Any) -> Any:
    """Enforce the partial invariant only when the evaluator emits audit data.

    Safety rule: a legacy partial result that does not expose any missing-criteria
    field is left unchanged. This avoids inventing correctness from an old schema.
    """
    if not isinstance(value, dict):
        return value

    out = deepcopy(value)
    verdict_key = next((k for k in _VERDICT_KEYS if k in out), None)
    if verdict_key is None or _norm(out.get(verdict_key)) not in _PARTIAL_VALUES:
        return out

    missing_key = next((k for k in _MISSING_KEYS if k in out), None)
    if missing_key is None:
        # Legacy/incomplete evidence remains auditable and unchanged.
        return out

    if not _is_empty_missing(out.get(missing_key)):
        return out

    old = out.get(verdict_key)
    if verdict_key == "outcome":
        out[verdict_key] = "demonstrated"
    elif isinstance(old, str) and old.strip().casefold() in {
        "parcial", "parcialmente correto", "parcialmente_correto"
    }:
        out[verdict_key] = "correto"
    else:
        out[verdict_key] = "correct"
    out.setdefault("policy_adjustment", "partial_without_missing_essential_criterion")
    return out


def _wrap_evaluator_callable(fn):
    if getattr(fn, "_apex_eval_v2_wrapped", False):
        return fn

    if inspect.iscoroutinefunction(fn):
        @wraps(fn)
        async def wrapped(*args, **kwargs):
            return postprocess_evaluation_result(await fn(*args, **kwargs))
    else:
        @wraps(fn)
        def wrapped(*args, **kwargs):
            return postprocess_evaluation_result(fn(*args, **kwargs))

    wrapped._apex_eval_v2_wrapped = True
    return wrapped


def _is_evaluator_method_name(name: str) -> bool:
    lowered = name.casefold()
    return lowered in {
        "build_evaluation", "evaluate", "evaluate_answer", "assess", "assess_answer",
        "grade", "grade_answer", "classify", "classify_answer", "check_answer",
    } or lowered.startswith("evaluate_") or lowered.startswith("assess_")


def install_evaluator_policy(module_globals: dict[str, Any]) -> dict[str, int]:
    """Patch only evaluator functions/classes defined by this exact module."""
    module_name = str(module_globals.get("__name__") or "")
    patched = 0

    # Module-level functions: only real Python functions defined here, never classes.
    for name, obj in list(module_globals.items()):
        if not _is_evaluator_method_name(name):
            continue
        if not inspect.isfunction(obj):
            continue
        if getattr(obj, "__module__", None) != module_name:
            continue
        new_obj = _wrap_evaluator_callable(obj)
        if new_obj is not obj:
            module_globals[name] = new_obj
            patched += 1

    # Classes: only classes defined in this module; imported ledgers/history are excluded.
    for obj in list(module_globals.values()):
        if not isinstance(obj, type):
            continue
        if getattr(obj, "__module__", None) != module_name:
            continue
        class_name = obj.__name__.casefold()
        if not any(tok in class_name for tok in ("evaluator", "evaluation", "assessor", "assessment", "grader")):
            continue
        for name, raw in list(vars(obj).items()):
            if not _is_evaluator_method_name(name):
                continue
            descriptor = None
            if isinstance(raw, staticmethod):
                descriptor = staticmethod
                fn = raw.__func__
            elif isinstance(raw, classmethod):
                descriptor = classmethod
                fn = raw.__func__
            elif inspect.isfunction(raw):
                fn = raw
            else:
                continue
            new_fn = _wrap_evaluator_callable(fn)
            if new_fn is fn:
                continue
            setattr(obj, name, descriptor(new_fn) if descriptor else new_fn)
            patched += 1

    return {"evaluation": patched}
