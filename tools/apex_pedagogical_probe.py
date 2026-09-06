#!/usr/bin/env python3
"""APEX Pedagogical Probe.

Executa cenários E2E por HTTP contra uma instância APEX isolada, usando o
mesmo código do repositório e um banco SQLite temporário. O progresso real do
aluno não é tocado.

Uso:
    python3 tools/apex_pedagogical_probe.py

O relatório completo é gravado em logs/apex_pedagogical_probe_latest.json.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
import unicodedata
from urllib import error, parse, request
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "logs" / "apex_pedagogical_probe_latest.json"
DEFAULT_TIMEOUT = 25.0

FEEDBACK_TO_OUTCOME = (
    ("correto.", "demonstrated"),
    ("parcialmente correto.", "partial"),
    ("ainda não está correto.", "misconception"),
    ("ainda nao esta correto.", "misconception"),
    ("ainda não há evidência suficiente.", "insufficient"),
    ("ainda nao ha evidencia suficiente.", "insufficient"),
    ("não foi possível confirmar ainda.", "unverified"),
    ("nao foi possivel confirmar ainda.", "unverified"),
)

TASK_RE = re.compile(
    r"(?ims)^\s*(?:tarefa|desafio|sua vez)\s*:\s*(.+?)(?=\n\s*\n|\Z)"
)


def fold_text(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def extract_task(text: str) -> str | None:
    matches = [" ".join(match.split()) for match in TASK_RE.findall(text or "")]
    matches = [match for match in matches if match]
    return matches[0] if len(matches) == 1 else None


def feedback_outcome(text: str) -> str | None:
    folded = fold_text(text)
    for prefix, outcome in FEEDBACK_TO_OUTCOME:
        if folded.startswith(fold_text(prefix)):
            return outcome
    return None


def classify_task(prompt: str | None) -> str | None:
    folded = fold_text(prompt)
    if not folded:
        return None

    if all(marker in folded for marker in ("mostra ola na tela", "palavra que falta")):
        return "write_keyword_hello"
    if all(marker in folded for marker in ("escreva", "pronto", "aparece na tela", "texto exibido")):
        return "write_predict_ready"
    if all(marker in folded for marker in ("unica linha", "inicio", "fimalgoritmo", "concluido", "entre aspas")):
        return "write_line_done"
    if all(marker in folded for marker in ("algoritmo chamado", "mostre ok na tela", "inicio", "escreva", "fimalgoritmo")):
        return "write_program_ok"
    if all(marker in folded for marker in ("de memoria", "mostra", "revisao", "na tela")):
        return "write_review_message"

    if all(marker in folded for marker in ("primeira linha", "rotina", "palavra que falta")):
        return "portugol_keyword_algoritmo"
    if all(marker in folded for marker in ("algoritmo", "rotina", "passos comecam")):
        return "portugol_keyword_inicio"
    if all(marker in folded for marker in ("algoritmo", "rotina", "inicio", "encerra essa estrutura")):
        return "portugol_keyword_fimalgoritmo"
    if all(marker in folded for marker in ("tres lacunas", "rotina", "tres palavras-chave")):
        return "portugol_skeleton_integration"
    if all(marker in folded for marker in ("tres lacunas", "estudo", "tres palavras-chave")):
        return "portugol_skeleton_review"

    # As tarefas estruturadas reutilizam situações antigas; por isso precisam
    # ser reconhecidas antes dos classificadores mais amplos de ordered/IPO.
    if all(marker in folded for marker in ("pegar o pao", "colocar o pao", "retirar a torrada", "1", "2", "3")):
        return "structured_toast_numbered"
    if all(marker in folded for marker in ("pegar o copo", "beber a agua", "guardar o copo", "inicio", "fim")):
        return "structured_water_boundaries"
    if all(marker in folded for marker in ("inicio", "abrir a conversa", "clicar em enviar", "qual passo", "fim")):
        return "structured_message_missing_step"
    if all(marker in folded for marker in ("cafeteira", "agua", "po de cafe", "inicio", "fim", "receber", "preparar", "entregar")):
        return "structured_coffee_flow"
    if all(marker in folded for marker in ("receber pao", "aquecer o pao", "entregar torrada", "inicio", "fim")):
        return "structured_review_toaster"

    if all(marker in folded for marker in ("secar as maos", "abrir a torneira", "lavar as maos")):
        return "ordered_hand_washing"
    if "guardar um arquivo" in folded and "tres passos" in folded:
        return "ordered_save_file"
    if all(marker in folded for marker in ("clicar em enviar", "escrever a mensagem", "abrir a conversa")):
        return "ordered_message"
    if all(marker in folded for marker in ("guardar o copo", "pegar o copo", "beber a agua")):
        return "ordered_cup"
    if "carregar o celular" in folded and "resultado esperado" in folded:
        return "goal_phone_charge"
    if "resultado esperado de salvar um documento" in folded:
        return "goal_document_saved"
    if "resultado esperado de lavar a louca" in folded:
        return "goal_dishes_clean"
    if "resultado esperado de organizar uma mochila" in folded:
        return "goal_backpack_organized"
    if "resultado esperado de escovar os dentes" in folded:
        return "goal_teeth_clean_review"
    if all(marker in folded for marker in ("liquidificador", "banana", "leite", "entrada")):
        return "ipo_blender_input"
    if all(marker in folded for marker in ("maquina de lavar", "roupas", "processamento")):
        return "ipo_washing_processing"
    if all(marker in folded for marker in ("calculadora", "2", "3", "5", "saida")):
        return "ipo_calculator_output"
    if all(marker in folded for marker in ("cafeteira", "agua", "po de cafe", "cafe pronto")):
        return "ipo_coffee_mapping"
    if all(marker in folded for marker in ("torradeira", "pao", "torrada")):
        return "ipo_review_mapping"
    return "unknown"


def correct_answer(kind: str) -> str:
    answers = {
        "ordered_hand_washing": "abrir a torneira; lavar as mãos; secar as mãos",
        "ordered_save_file": "abrir o menu Arquivo; selecionar Salvar; escolher a pasta e confirmar",
        "ordered_message": "abrir a conversa; escrever a mensagem; clicar em Enviar",
        "ordered_cup": "pegar o copo; beber a água; guardar o copo",
        "goal_phone_charge": "A",
        "goal_document_saved": "documento salvo.",
        "goal_dishes_clean": "louça limpa.",
        "goal_backpack_organized": "mochila organizada para a aula.",
        "goal_teeth_clean_review": "dentes limpos.",
        "ipo_blender_input": "banana e leite.",
        "ipo_washing_processing": "lavar as roupas.",
        "ipo_calculator_output": "5.",
        "ipo_coffee_mapping": "água e pó de café; preparar a bebida; café pronto.",
        "ipo_review_mapping": "pão; aquecer; torrada.",
        "structured_toast_numbered": "1 pegar o pão; 2 colocar o pão na torradeira; 3 retirar a torrada.",
        "structured_water_boundaries": "INÍCIO; pegar o copo; beber a água; guardar o copo; FIM.",
        "structured_message_missing_step": "escrever a mensagem.",
        "structured_coffee_flow": "INÍCIO; receber água e pó de café; preparar a bebida; entregar café pronto; FIM.",
        "structured_review_toaster": "INÍCIO; receber pão; aquecer o pão; entregar torrada; FIM.",
        "portugol_keyword_algoritmo": "algoritmo",
        "portugol_keyword_inicio": "inicio",
        "portugol_keyword_fimalgoritmo": "fimalgoritmo",
        "portugol_skeleton_integration": "algoritmo; inicio; fimalgoritmo",
        "portugol_skeleton_review": "algoritmo; inicio; fimalgoritmo",
        "write_keyword_hello": "escreva",
        "write_predict_ready": "Pronto",
        "write_line_done": 'escreva("Concluído")',
        "write_program_ok": 'algoritmo "saida"; inicio; escreva("OK"); fimalgoritmo',
        "write_review_message": 'escreva("Revisão")',
    }
    if kind not in answers:
        raise RuntimeError(f"tarefa não reconhecida pelo probe: {kind}")
    return answers[kind]


def parse_sse(raw: str) -> dict:
    tokens: list[str] = []
    errors: list[str] = []
    done = False
    events: list[dict] = []
    for line in (raw or "").splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload:
            continue
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            errors.append(f"SSE inválido: {payload[:120]}")
            continue
        if not isinstance(event, dict):
            continue
        events.append(event)
        token = event.get("token")
        if isinstance(token, str):
            tokens.append(token)
        if event.get("done") is True:
            done = True
        message = event.get("error")
        if isinstance(message, str) and message.strip():
            errors.append(message.strip())
    return {
        "text": "".join(tokens),
        "done": done,
        "errors": errors,
        "events": events,
    }


class HttpResult:
    def __init__(self, status: int, body: bytes, headers=None):
        self.status = int(status)
        self.body = body
        self.headers = headers or {}

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self):
        return json.loads(self.text())


class ApexHttp:
    def __init__(self, base_url: str, timeout: float = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _call(self, method: str, path: str, payload=None) -> HttpResult:
        url = self.base_url + path
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                return HttpResult(response.status, response.read(), response.headers)
        except error.HTTPError as exc:
            return HttpResult(exc.code, exc.read(), exc.headers)

    def get(self, path: str) -> HttpResult:
        return self._call("GET", path)

    def post(self, path: str, payload: dict) -> HttpResult:
        return self._call("POST", path, payload)

    def chat(self, message: str, *, turn_id: str, area: str = "ads") -> dict:
        result = self.post(
            "/chat/stream",
            {"message": message, "area": area, "turn_id": turn_id},
        )
        if result.status != 200:
            try:
                error_payload = result.json()
            except Exception:
                error_payload = {"error": result.text()}
            return {
                "status": result.status,
                "text": "",
                "done": False,
                "errors": [str(error_payload.get("error") or error_payload)],
                "events": [],
            }
        parsed = parse_sse(result.text())
        parsed["status"] = result.status
        return parsed

    def export(self) -> dict:
        result = self.get("/api/privacy/export")
        if result.status != 200:
            raise RuntimeError(
                f"export falhou: HTTP {result.status}: {result.text()[:240]}"
            )
        return result.json()


class Sidecar:
    def __init__(self, root: Path, timeout: float = DEFAULT_TIMEOUT):
        self.root = root
        self.timeout = timeout
        self.temp = None
        self.process = None
        self.log_handle = None
        self.log_path = None
        self.port = None
        self.client = None

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="apex-pedagogical-probe-")
        temp_path = Path(self.temp.name)
        data_dir = temp_path / "data"
        self.log_path = temp_path / "server.log"
        self.port = self._free_port()

        env = os.environ.copy()
        env.update(
            {
                "APEX_DATA_DIR": str(data_dir),
                "APP_ENV": "development",
                "SECRET_KEY": "apex-pedagogical-probe",
                # Os conceitos cobertos pelo probe são controlados e não chamam
                # a LLM. A chave sentinela apenas atravessa o guard HTTP.
                "GROQ_API_KEY": env.get("GROQ_API_KEY") or "probe-controlled-only",
                "APEX_PROBE_PORT": str(self.port),
                "PYTHONUNBUFFERED": "1",
            }
        )
        code = (
            "import os; "
            "from backend.database import init_database; "
            "from backend.security import bootstrap_access_control; "
            "init_database(); bootstrap_access_control(); "
            "from backend.app import app; "
            "app.run(host='127.0.0.1', port=int(os.environ['APEX_PROBE_PORT']), "
            "debug=False, use_reloader=False, threaded=True)"
        )
        self.log_handle = self.log_path.open("wb")
        self.process = subprocess.Popen(
            [sys.executable, "-c", code],
            cwd=self.root,
            env=env,
            stdout=self.log_handle,
            stderr=subprocess.STDOUT,
        )
        self.client = ApexHttp(f"http://127.0.0.1:{self.port}", timeout=self.timeout)

        deadline = time.monotonic() + self.timeout
        last_error = None
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                break
            try:
                health = self.client.get("/health")
                if health.status == 200 and health.json().get("ok") is True:
                    return self
            except Exception as exc:  # servidor ainda subindo
                last_error = exc
            time.sleep(0.12)

        log_tail = self.read_log_tail()
        raise RuntimeError(
            "sidecar APEX não iniciou"
            + (f": {last_error}" if last_error else "")
            + (f"\n{log_tail}" if log_tail else "")
        )

    def read_log_tail(self, max_chars: int = 6000) -> str:
        if self.log_handle is not None:
            self.log_handle.flush()
        if self.log_path is None or not self.log_path.exists():
            return ""
        text = self.log_path.read_text(encoding="utf-8", errors="replace")
        return text[-max_chars:]

    def __exit__(self, exc_type, exc, tb):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.log_handle is not None:
            self.log_handle.close()
        if self.temp is not None:
            self.temp.cleanup()


class ProbeReport:
    def __init__(self):
        self.started_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        self.checks: list[dict] = []
        self.scenarios: list[dict] = []
        self.metrics: dict = {}

    def check(self, check_id: str, ok: bool, detail: str, *, severity="fail"):
        status = "PASS" if ok else ("WARN" if severity == "warn" else "FAIL")
        self.checks.append(
            {"id": check_id, "status": status, "detail": detail}
        )
        return ok

    def warn(self, check_id: str, detail: str):
        self.check(check_id, False, detail, severity="warn")

    @property
    def failures(self):
        return [item for item in self.checks if item["status"] == "FAIL"]

    @property
    def warnings(self):
        return [item for item in self.checks if item["status"] == "WARN"]

    @property
    def passes(self):
        return [item for item in self.checks if item["status"] == "PASS"]

    def as_dict(self):
        return {
            "tool": "apex_pedagogical_probe",
            "version": 1,
            "started_at": self.started_at,
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "summary": {
                "pass": len(self.passes),
                "fail": len(self.failures),
                "warn": len(self.warnings),
            },
            "metrics": self.metrics,
            "checks": self.checks,
            "scenarios": self.scenarios,
        }


def dataset(export: dict, name: str) -> list[dict]:
    data = export.get("datasets") if isinstance(export, dict) else None
    if not isinstance(data, dict):
        return []
    rows = data.get(name)
    return rows if isinstance(rows, list) else []


def row_for_turn(export: dict, table: str, turn_id: str) -> dict | None:
    rows = [row for row in dataset(export, table) if row.get("turn_id") == turn_id]
    return rows[-1] if rows else None


def latest_state(export: dict, area: str = "ads") -> dict | None:
    rows = [row for row in dataset(export, "learner_state") if row.get("area") == area]
    return rows[-1] if rows else None


def task_prompt_for_evidence(export: dict, event: dict) -> str | None:
    turn_id = event.get("turn_id")
    attempt = row_for_turn(export, "learning_attempts", turn_id)
    if not attempt:
        return None
    task_id = attempt.get("task_id")
    if not task_id:
        return None
    for task in dataset(export, "learning_tasks"):
        if task.get("task_id") == task_id:
            return task.get("prompt_text")
    return None


def assert_feedback_persistence(
    report: ProbeReport,
    export: dict,
    turn_id: str,
    assistant_text: str,
    *,
    check_prefix: str,
):
    displayed = feedback_outcome(assistant_text)
    evidence = row_for_turn(export, "evidence_events", turn_id)
    rubric = row_for_turn(export, "rubric_assessments", turn_id)
    mastery = row_for_turn(export, "mastery_assessments", turn_id)

    report.check(
        f"{check_prefix}.evidence_exists",
        evidence is not None,
        f"turno {turn_id}: evidence_event persistido={evidence is not None}",
    )
    if evidence is None:
        return

    persisted = evidence.get("outcome")
    report.check(
        f"{check_prefix}.display_matches_evidence",
        displayed == persisted,
        f"turno {turn_id}: exibido={displayed!r}, evidence={persisted!r}",
    )
    report.check(
        f"{check_prefix}.rubric_matches_evidence",
        rubric is not None and rubric.get("outcome") == persisted,
        f"turno {turn_id}: rubric={None if rubric is None else rubric.get('outcome')!r}, evidence={persisted!r}",
    )
    report.check(
        f"{check_prefix}.mastery_matches_evidence",
        mastery is not None and mastery.get("latest_outcome") == persisted,
        f"turno {turn_id}: mastery.latest={None if mastery is None else mastery.get('latest_outcome')!r}, evidence={persisted!r}",
    )


def start_algorithms(client: ApexHttp, report: ProbeReport, scenario_id: str):
    response = client.post(
        "/api/study/start",
        {"area": "ads", "concept_id": "ads.algorithms", "restart": True},
    )
    ok = response.status == 200
    detail = f"HTTP {response.status}"
    state = None
    if ok:
        payload = response.json()
        state = payload.get("state") or {}
        detail += f", concept={state.get('current_concept_id')}, stage={state.get('stage')}"
        ok = state.get("current_concept_id") == "ads.algorithms.ordered_steps"
    report.check(f"{scenario_id}.study_start", ok, detail)
    if not ok:
        raise RuntimeError("não foi possível iniciar algoritmos no sidecar")


def run_happy_path(report: ProbeReport, timeout: float):
    scenario_id = "happy"
    transcript = []
    with Sidecar(ROOT, timeout=timeout) as sidecar:
        client = sidecar.client
        start_algorithms(client, report, scenario_id)

        first_turn = f"probe-{scenario_id}-{uuid4().hex}"
        first = client.chat("começar", turn_id=first_turn)
        report.check(
            f"{scenario_id}.first_turn",
            first["status"] == 200 and not first["errors"] and extract_task(first["text"]) is not None,
            f"HTTP={first['status']}, errors={first['errors']}, task={extract_task(first['text'])!r}",
        )
        current = first["text"]
        transcript.append({"user": "começar", "assistant": current})

        seen_kinds: list[str] = []
        result_answers_without_label = []
        completed = False

        for index in range(40):
            folded = fold_text(current)
            if "envie continuar" in folded:
                turn_id = f"probe-{scenario_id}-continue-{index}-{uuid4().hex}"
                response = client.chat("continuar", turn_id=turn_id)
                report.check(
                    f"{scenario_id}.advance_{index}",
                    response["status"] == 200 and not response["errors"],
                    f"HTTP={response['status']}, errors={response['errors']}",
                )
                current = response["text"]
                transcript.append({"user": "continuar", "assistant": current})
                continue

            if "esta fatia do percurso esta concluida" in folded:
                completed = True
                break

            prompt = extract_task(current)
            kind = classify_task(prompt)
            report.check(
                f"{scenario_id}.task_recognized_{index}",
                kind not in {None, "unknown"},
                f"tarefa={prompt!r}; tipo={kind!r}",
            )
            if kind in {None, "unknown"}:
                break

            seen_kinds.append(kind)
            answer = correct_answer(kind)
            if kind.startswith("goal_") and kind != "goal_phone_charge":
                result_answers_without_label.append(answer)
                report.check(
                    f"{scenario_id}.no_result_label_{index}",
                    not fold_text(answer).startswith("resultado"),
                    f"resposta usada={answer!r}",
                )

            turn_id = f"probe-{scenario_id}-{index}-{uuid4().hex}"
            response = client.chat(answer, turn_id=turn_id)
            current = response["text"]
            transcript.append({"user": answer, "assistant": current, "turn_id": turn_id})

            report.check(
                f"{scenario_id}.chat_ok_{index}",
                response["status"] == 200 and not response["errors"],
                f"tipo={kind}; HTTP={response['status']}; errors={response['errors']}",
            )
            report.check(
                f"{scenario_id}.correct_feedback_{index}",
                feedback_outcome(current) == "demonstrated",
                f"tipo={kind}; feedback={feedback_outcome(current)!r}; resposta={current[:120]!r}",
            )

            exported = client.export()
            assert_feedback_persistence(
                report,
                exported,
                turn_id,
                current,
                check_prefix=f"{scenario_id}.consistency_{index}",
            )

        exported = client.export()
        state = latest_state(exported) or {}
        report.check(
            f"{scenario_id}.curriculum_slice_completed",
            completed
            and state.get("current_concept_id") == "ads.algorithms.portugol_write"
            and state.get("stage") == "concluido",
            f"completed={completed}, concept={state.get('current_concept_id')}, stage={state.get('stage')}, mastery={state.get('mastery')}",
        )

        goal_tasks = [kind for kind in seen_kinds if kind.startswith("goal_")]
        report.check(
            f"{scenario_id}.semantic_without_format",
            bool(result_answers_without_label)
            and all(not fold_text(item).startswith("resultado") for item in result_answers_without_label),
            f"respostas corretas sem rótulo testadas={result_answers_without_label}",
        )

        future_prompts = [
            row.get("prompt_text") or ""
            for row in dataset(exported, "learning_tasks")
            if row.get("concept_id") == "ads.algorithms.goal_result"
        ]
        forbidden_format = [
            prompt
            for prompt in future_prompts
            if "comecando com resultado" in fold_text(prompt)
        ]
        report.check(
            f"{scenario_id}.prompt_does_not_grade_label",
            not forbidden_format,
            f"prompts com exigência literal encontrados={len(forbidden_format)}",
        )

        demonstrated_goal_events = [
            event
            for event in dataset(exported, "evidence_events")
            if event.get("concept_id") == "ads.algorithms.goal_result"
            and event.get("outcome") == "demonstrated"
            and bool(event.get("applied"))
        ]
        demonstrated_kinds = []
        for event in demonstrated_goal_events:
            kind = classify_task(task_prompt_for_evidence(exported, event))
            if kind not in {None, "unknown"}:
                demonstrated_kinds.append(kind)
        distinct_kinds = sorted(set(demonstrated_kinds))
        completion_claim = any(
            "evidencias" in fold_text(item.get("assistant"))
            and "atividades" in fold_text(item.get("assistant"))
            and "diferentes" in fold_text(item.get("assistant"))
            for item in transcript
        )
        report.check(
            f"{scenario_id}.completion_claim_has_context_diversity",
            (not completion_claim) or len(distinct_kinds) >= 2,
            f"mensagem afirma diversidade={completion_claim}; atividades demonstradas distintas={distinct_kinds}",
        )

        ipo_tasks = [kind for kind in seen_kinds if kind.startswith("ipo_")]
        report.check(
            f"{scenario_id}.ipo_progression_reached",
            {"ipo_blender_input", "ipo_washing_processing", "ipo_calculator_output", "ipo_coffee_mapping"}.issubset(set(ipo_tasks)),
            f"tarefas IPO vistas={ipo_tasks}",
        )
        report.check(
            f"{scenario_id}.ipo_mapping_without_required_labels",
            "ipo_coffee_mapping" in ipo_tasks,
            "o mapeamento final foi respondido sem exigir os rótulos literais entrada/processamento/saída",
        )
        report.metrics["happy_ipo_task_kinds"] = ipo_tasks

        structured_tasks = [kind for kind in seen_kinds if kind.startswith("structured_")]
        report.check(
            f"{scenario_id}.structured_progression_reached",
            {
                "structured_toast_numbered",
                "structured_water_boundaries",
                "structured_message_missing_step",
                "structured_coffee_flow",
            }.issubset(set(structured_tasks)),
            f"tarefas estruturadas vistas={structured_tasks}",
        )
        report.metrics["happy_structured_task_kinds"] = structured_tasks

        portugol_tasks = [kind for kind in seen_kinds if kind.startswith("portugol_")]
        report.check(
            f"{scenario_id}.portugol_skeleton_progression_reached",
            {
                "portugol_keyword_algoritmo",
                "portugol_keyword_inicio",
                "portugol_keyword_fimalgoritmo",
                "portugol_skeleton_integration",
            }.issubset(set(portugol_tasks)),
            f"tarefas de estrutura mínima do Portugol vistas={portugol_tasks}",
        )
        report.metrics["happy_portugol_task_kinds"] = portugol_tasks

        write_tasks = [kind for kind in seen_kinds if kind.startswith("write_")]
        report.check(
            f"{scenario_id}.portugol_write_progression_reached",
            {
                "write_keyword_hello",
                "write_predict_ready",
                "write_line_done",
                "write_program_ok",
            }.issubset(set(write_tasks)),
            f"tarefas de saída com escreva vistas={write_tasks}",
        )
        report.metrics["happy_write_task_kinds"] = write_tasks

        report.metrics["happy_goal_task_kinds"] = goal_tasks
        report.metrics["happy_distinct_demonstrated_goal_tasks"] = distinct_kinds
        report.scenarios.append(
            {
                "id": scenario_id,
                "transcript": transcript,
                "final_state": state,
                "server_log_tail": sidecar.read_log_tail(),
            }
        )


def drive_to_first_task(client: ApexHttp, report: ProbeReport, scenario_id: str):
    start_algorithms(client, report, scenario_id)
    turn_id = f"probe-{scenario_id}-start-{uuid4().hex}"
    response = client.chat("começar", turn_id=turn_id)
    if response["status"] != 200 or response["errors"] or not extract_task(response["text"]):
        raise RuntimeError(f"primeira tarefa indisponível: {response}")
    return response["text"]


def run_reliability_path(report: ProbeReport, timeout: float):
    scenario_id = "reliability"
    transcript = []
    with Sidecar(ROOT, timeout=timeout) as sidecar:
        client = sidecar.client
        current = drive_to_first_task(client, report, scenario_id)
        transcript.append({"user": "começar", "assistant": current})

        before_pause = client.export()
        turn_count_before = len(dataset(before_pause, "learning_turns"))
        pause = client.post("/api/session/pause", {"area": "ads"})
        report.check(
            f"{scenario_id}.pause",
            pause.status == 200 and pause.json().get("ok") is True,
            f"HTTP={pause.status}; body={pause.text()[:160]!r}",
        )

        blocked_id = f"probe-{scenario_id}-blocked-{uuid4().hex}"
        blocked = client.chat("abrir a torneira; lavar as mãos; secar as mãos", turn_id=blocked_id)
        after_block = client.export()
        report.check(
            f"{scenario_id}.paused_chat_blocked",
            blocked["status"] == 409 and bool(blocked["errors"]),
            f"HTTP={blocked['status']}; errors={blocked['errors']}",
        )
        report.check(
            f"{scenario_id}.paused_chat_no_mutation",
            len(dataset(after_block, "learning_turns")) == turn_count_before,
            f"turnos antes={turn_count_before}; depois={len(dataset(after_block, 'learning_turns'))}",
        )

        resume = client.post("/api/session/resume", {"area": "ads", "mode": "direct"})
        report.check(
            f"{scenario_id}.resume_direct",
            resume.status == 200 and resume.json().get("ok") is True,
            f"HTTP={resume.status}; body={resume.text()[:160]!r}",
        )

        prompt = extract_task(current)
        kind = classify_task(prompt)
        answer = correct_answer(kind)
        fixed_turn_id = f"probe-{scenario_id}-idem-{uuid4().hex}"
        first = client.chat(answer, turn_id=fixed_turn_id)
        first_export = client.export()
        second = client.chat(answer, turn_id=fixed_turn_id)
        second_export = client.export()

        same_turn_rows = [
            row
            for row in dataset(second_export, "learning_turns")
            if row.get("turn_id") == fixed_turn_id
        ]
        same_evidence_rows = [
            row
            for row in dataset(second_export, "evidence_events")
            if row.get("turn_id") == fixed_turn_id
        ]
        report.check(
            f"{scenario_id}.idempotent_response",
            first["status"] == 200
            and second["status"] == 200
            and first["text"] == second["text"]
            and not first["errors"]
            and not second["errors"],
            f"primeira={first['text'][:100]!r}; replay={second['text'][:100]!r}; errors={first['errors'] + second['errors']}",
        )
        report.check(
            f"{scenario_id}.idempotent_single_turn",
            len(same_turn_rows) == 1,
            f"registros learning_turns com turn_id={len(same_turn_rows)}",
        )
        report.check(
            f"{scenario_id}.idempotent_single_evidence",
            len(same_evidence_rows) == 1,
            f"registros evidence_events com turn_id={len(same_evidence_rows)}",
        )

        # O mesmo turn_id com conteúdo diferente deve falhar e jamais criar
        # nova evidência. A rota SSE atualmente encapsula o erro em mensagem
        # genérica; o probe registra o comportamento sem exigir texto interno.
        changed = client.chat("resposta diferente", turn_id=fixed_turn_id)
        changed_export = client.export()
        changed_evidence_rows = [
            row
            for row in dataset(changed_export, "evidence_events")
            if row.get("turn_id") == fixed_turn_id
        ]
        report.check(
            f"{scenario_id}.turn_id_reuse_rejected",
            bool(changed["errors"]) and len(changed_evidence_rows) == 1,
            f"HTTP={changed['status']}; errors={changed['errors']}; evidências={len(changed_evidence_rows)}",
        )

        transcript.extend(
            [
                {"user": answer, "assistant": first["text"], "turn_id": fixed_turn_id},
                {"user": answer, "assistant": second["text"], "turn_id": fixed_turn_id, "replay": True},
                {"user": "resposta diferente", "errors": changed["errors"], "turn_id": fixed_turn_id},
            ]
        )
        report.scenarios.append(
            {
                "id": scenario_id,
                "transcript": transcript,
                "server_log_tail": sidecar.read_log_tail(),
            }
        )


def run_adversarial_result_path(report: ProbeReport, timeout: float):
    scenario_id = "adversarial_result"
    transcript = []
    with Sidecar(ROOT, timeout=timeout) as sidecar:
        client = sidecar.client
        start_algorithms(client, report, scenario_id)
        current = client.chat(
            "começar", turn_id=f"probe-{scenario_id}-start-{uuid4().hex}"
        )["text"]

        document_tested = False
        for index in range(18):
            folded = fold_text(current)
            if "envie continuar" in folded:
                current = client.chat(
                    "continuar", turn_id=f"probe-{scenario_id}-continue-{index}-{uuid4().hex}"
                )["text"]
                continue

            prompt = extract_task(current)
            kind = classify_task(prompt)
            if kind in {None, "unknown"}:
                break

            if kind == "goal_document_saved" and not document_tested:
                bad_answer = "primeiro abrir o menu, depois clicar em salvar e escolher a pasta."
                bad_turn = f"probe-{scenario_id}-bad-{uuid4().hex}"
                bad = client.chat(bad_answer, turn_id=bad_turn)
                bad_export = client.export()
                bad_event = row_for_turn(bad_export, "evidence_events", bad_turn)
                report.check(
                    f"{scenario_id}.procedure_not_accepted",
                    feedback_outcome(bad["text"]) != "demonstrated"
                    and bad_event is not None
                    and bad_event.get("outcome") != "demonstrated",
                    f"feedback={feedback_outcome(bad['text'])!r}; persisted={None if bad_event is None else bad_event.get('outcome')!r}; resposta={bad['text'][:140]!r}",
                )
                assert_feedback_persistence(
                    report,
                    bad_export,
                    bad_turn,
                    bad["text"],
                    check_prefix=f"{scenario_id}.procedure_consistency",
                )
                transcript.append({"user": bad_answer, "assistant": bad["text"], "turn_id": bad_turn})
                current = bad["text"]
                document_tested = True
                continue

            answer = correct_answer(kind)
            turn_id = f"probe-{scenario_id}-{index}-{uuid4().hex}"
            response = client.chat(answer, turn_id=turn_id)
            transcript.append({"user": answer, "assistant": response["text"], "turn_id": turn_id})
            current = response["text"]

            if document_tested and kind == "goal_document_saved":
                exported = client.export()
                event = row_for_turn(exported, "evidence_events", turn_id)
                report.check(
                    f"{scenario_id}.recovery_correct_without_label",
                    feedback_outcome(response["text"]) == "demonstrated"
                    and event is not None
                    and event.get("outcome") == "demonstrated"
                    and answer == "documento salvo.",
                    f"feedback={feedback_outcome(response['text'])!r}; persisted={None if event is None else event.get('outcome')!r}; answer={answer!r}",
                )
                break

        report.check(
            f"{scenario_id}.document_scenario_reached",
            document_tested,
            "o probe alcançou a tarefa de salvar documento e executou o caso adversarial",
        )
        report.scenarios.append(
            {
                "id": scenario_id,
                "transcript": transcript,
                "server_log_tail": sidecar.read_log_tail(),
            }
        )


def structural_checks(report: ProbeReport):
    curriculum = (ROOT / "backend" / "services" / "curriculum.py").read_text(
        encoding="utf-8"
    )
    mastery = (ROOT / "backend" / "services" / "mastery_policy.py").read_text(
        encoding="utf-8"
    )

    has_next_after_goal = bool(
        re.search(
            r"GOAL_RESULT\s*:\s*[A-Z_]+",
            curriculum,
        )
    )
    if has_next_after_goal:
        report.check(
            "structural.next_microconcept",
            True,
            "Curriculum define sucessor executável após GOAL_RESULT.",
        )
    else:
        report.warn(
            "structural.next_microconcept",
            "Curriculum ainda não define microcompetência executável após GOAL_RESULT.",
        )

    has_next_after_ipo = bool(
        re.search(
            r"INPUT_PROCESS_OUTPUT\s*:\s*STRUCTURED_SEQUENCE",
            curriculum,
        )
    )
    if has_next_after_ipo:
        report.check(
            "structural.next_after_ipo",
            True,
            "Curriculum define representação estruturada como sucessor executável após IPO.",
        )
    else:
        report.warn(
            "structural.next_after_ipo",
            "Curriculum ainda não define sucessor executável após entrada/processamento/saída.",
        )

    has_next_after_structured = bool(
        re.search(
            r"STRUCTURED_SEQUENCE\s*:\s*PORTUGOL_SKELETON",
            curriculum,
        )
    )
    if has_next_after_structured:
        report.check(
            "structural.next_after_structured_sequence",
            True,
            "Curriculum define estrutura mínima do Portugol como sucessor executável após representação estruturada.",
        )
    else:
        report.warn(
            "structural.next_after_structured_sequence",
            "Curriculum ainda não define sucessor executável após representação estruturada.",
        )

    has_next_after_portugol_skeleton = bool(
        re.search(
            r"PORTUGOL_SKELETON\s*:\s*PORTUGOL_WRITE",
            curriculum,
        )
    )
    if has_next_after_portugol_skeleton:
        report.check(
            "structural.next_after_portugol_skeleton",
            True,
            "Curriculum define saída simples com escreva como sucessor executável após a estrutura mínima do Portugol.",
        )
    else:
        report.warn(
            "structural.next_after_portugol_skeleton",
            "Curriculum ainda não define sucessor executável após a estrutura mínima do Portugol.",
        )

    # MasteryPolicy anuncia diversidade de contexto, mas a versão atual conta
    # explicitamente diversidade de stage. Registrar isso como alerta de design
    # até existir um identificador de contexto/tarefa no portfólio de domínio.
    folded_mastery = fold_text(mastery)
    has_context_field = any(
        token in folded_mastery
        for token in (
            "task_kind",
            "task_id",
            "source_turn_id",
            "context_id",
            "activity_id",
        )
    )
    if has_context_field:
        report.check(
            "structural.mastery_context_diversity",
            True,
            "MasteryPolicy referencia identidade de tarefa/contexto no portfólio.",
        )
    else:
        report.warn(
            "structural.mastery_context_diversity",
            "MasteryPolicy mede diversidade de stage, mas não referencia identidade de tarefa/contexto; a garantia de 'atividades diferentes' não é estruturalmente explícita.",
        )


def write_report(report: ProbeReport) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = report.as_dict()
    REPORT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return REPORT_PATH


def print_summary(report: ProbeReport, report_path: Path):
    print("=== APEX PEDAGOGICAL PROBE ===")
    print(f"PASS: {len(report.passes)}")
    print(f"FAIL: {len(report.failures)}")
    print(f"WARN: {len(report.warnings)}")
    print()
    if report.failures:
        print("FALHAS:")
        for item in report.failures:
            print(f"- {item['id']}: {item['detail']}")
        print()
    if report.warnings:
        print("ALERTAS:")
        for item in report.warnings:
            print(f"- {item['id']}: {item['detail']}")
        print()
    print(f"RELATÓRIO: {report_path}")
    print("APEX PEDAGOGICAL PROBE: " + ("FAIL" if report.failures else "OK"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audita pedagogia e consistência do APEX por HTTP em uma instância "
            "isolada, sem alterar o progresso real."
        )
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="timeout por operação/boot em segundos (padrão: 25)",
    )
    parser.add_argument(
        "--only",
        choices=("all", "happy", "reliability", "adversarial"),
        default="all",
        help="executa somente um grupo de cenários",
    )
    args = parser.parse_args(argv)

    report = ProbeReport()
    try:
        structural_checks(report)
        if args.only in {"all", "happy"}:
            run_happy_path(report, args.timeout)
        if args.only in {"all", "reliability"}:
            run_reliability_path(report, args.timeout)
        if args.only in {"all", "adversarial"}:
            run_adversarial_result_path(report, args.timeout)
    except Exception as exc:
        report.check("probe.internal_error", False, f"{type(exc).__name__}: {exc}")

    report_path = write_report(report)
    print_summary(report, report_path)
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
