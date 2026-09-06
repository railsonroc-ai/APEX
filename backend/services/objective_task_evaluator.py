import re

from backend.concepts import normalize_alias
from backend.services.rubric_policy import RubricPolicy
from backend.services.goal_result_tasks import GoalResultTasks
from backend.services.input_process_output_tasks import InputProcessOutputTasks


class ObjectiveTaskEvaluator:
    """Avalia tarefas fechadas sem depender de julgamento probabilístico.

    O avaliador só assume uma tarefa quando reconhece simultaneamente o
    conceito e o enunciado persistido. Respostas a tarefas abertas continuam
    seguindo para o avaliador semântico.
    """

    ORDERED_STEPS = "ads.algorithms.ordered_steps"
    GOAL_RESULT = "ads.algorithms.goal_result"
    INPUT_PROCESS_OUTPUT = "ads.algorithms.input_process_output"
    HAND_WASHING_MARKERS = (
        "abrir a torneira",
        "lavar as maos",
        "secar as maos",
    )
    CORRECT_NUMERIC_ORDER = ("2", "3", "1")
    ACTION_PATTERNS = (
        re.compile(r"\babr\w*(?:\s+a)?(?:\s+torneira)?\b"),
        re.compile(r"\blav\w*(?:\s+(?:as|minhas|suas))?(?:\s+maos)?\b"),
        re.compile(r"\bsec\w*(?:\s+(?:as|minhas|suas))?(?:\s+maos)?\b"),
    )

    # Exercícios controlados da primeira microcompetência. Mesmo quando o
    # enunciado pede uma descrição, a rubrica esperada é conhecida pelo
    # servidor e não deve depender da disponibilidade ou do formato da LLM.
    ORDERED_TASKS = (
        {
            "prompt_markers": HAND_WASHING_MARKERS,
            "patterns": ACTION_PATTERNS,
            "numeric_order": ("2", "3", "1"),
            "success": "Ordenou corretamente abrir, lavar e secar.",
        },
        {
            "prompt_markers": ("guardar um arquivo", "tres passos"),
            "patterns": (
                re.compile(r"\babr\w*\b.*\b(?:menu|arquivo)\b"),
                re.compile(r"\b(?:selecion\w*|escolh\w*|clic\w*)\b.*\bsalv\w*\b"),
                re.compile(r"\bescolh\w*\b.*\b(?:local|pasta)\b.*\bconfirm\w*\b"),
            ),
            "numeric_order": None,
            "success": "Descreveu três passos válidos e ordenados para salvar um arquivo.",
        },
        {
            "prompt_markers": ("clicar em enviar", "escrever a mensagem", "abrir a conversa"),
            "patterns": (
                re.compile(r"\babr\w*\b.*\bconvers\w*\b"),
                re.compile(r"\b(?:escrev\w*|digit\w*)\b.*\bmensag\w*\b"),
                re.compile(r"(?:\bclic\w*\b.*\benvi\w*\b|\benvi\w*\b.*\bmensag\w*\b)"),
            ),
            "numeric_order": ("3", "2", "1"),
            "success": "Ordenou corretamente abrir, escrever e enviar.",
        },
        {
            "prompt_markers": ("guardar o copo", "pegar o copo", "beber a agua"),
            "patterns": (
                re.compile(r"\bpeg\w*\b.*\bcopo\b"),
                re.compile(r"\bbeb\w*\b.*\bagua\b"),
                re.compile(r"\bguard\w*\b.*\bcopo\b"),
            ),
            "numeric_order": ("2", "3", "1"),
            "success": "Ordenou corretamente pegar, beber e guardar.",
        },
    )

    @classmethod
    def _is_hand_washing_order_task(cls, evaluation):
        if not isinstance(evaluation, dict):
            return False
        if evaluation.get("concept_id") != cls.ORDERED_STEPS:
            return False
        prompt = normalize_alias(evaluation.get("tutor_message")) or ""
        return all(marker in prompt for marker in cls.HAND_WASHING_MARKERS)

    @classmethod
    def _task_definition(cls, evaluation):
        if not isinstance(evaluation, dict):
            return None
        if evaluation.get("concept_id") != cls.ORDERED_STEPS:
            return None
        prompt = normalize_alias(evaluation.get("tutor_message")) or ""
        for definition in cls.ORDERED_TASKS:
            if all(marker in prompt for marker in definition["prompt_markers"]):
                return definition
        return None

    @classmethod
    def _goal_result_definition(cls, evaluation):
        if not isinstance(evaluation, dict):
            return None
        if evaluation.get("concept_id") != cls.GOAL_RESULT:
            return None
        return GoalResultTasks.definition_for_prompt(
            evaluation.get("tutor_message")
        )

    @classmethod
    def _input_process_output_definition(cls, evaluation):
        if not isinstance(evaluation, dict):
            return None
        if evaluation.get("concept_id") != cls.INPUT_PROCESS_OUTPUT:
            return None
        return InputProcessOutputTasks.definition_for_prompt(
            evaluation.get("tutor_message")
        )

    @staticmethod
    def _mapping_roles_are_correct(answer, definition):
        roles = definition.get("mapping_roles")
        if not isinstance(roles, dict):
            return True

        normalized = normalize_alias(answer) or ""
        labels = ("entrada", "processamento", "saida")
        label_positions = {
            label: normalized.find(label)
            for label in labels
            if normalized.find(label) >= 0
        }

        if len(label_positions) == 3:
            ordered_labels = sorted(label_positions, key=label_positions.get)
            segments = {}
            for index, label in enumerate(ordered_labels):
                start = label_positions[label] + len(label)
                end = (
                    label_positions[ordered_labels[index + 1]]
                    if index + 1 < len(ordered_labels)
                    else len(normalized)
                )
                segments[label] = normalized[start:end]
            return all(
                all(any(marker in segments[label] for marker in group) for group in groups)
                for label, groups in roles.items()
            )

        # Sem rótulos obrigatórios, aceita uma relação escrita na ordem natural:
        # entrada -> processamento -> saída. Assim o formato não vira objetivo,
        # mas uma mera coleção dos termos fora de relação não é suficiente.
        positions = []
        for label in labels:
            groups = roles[label]
            role_positions = []
            for group in groups:
                hits = [normalized.find(marker) for marker in group]
                hits = [hit for hit in hits if hit >= 0]
                if not hits:
                    return False
                role_positions.append(min(hits))
            positions.append(min(role_positions))
        return positions == sorted(positions) and len(set(positions)) == len(positions)

    @classmethod
    def _evaluate_input_process_output(cls, evaluation, definition):
        answer = normalize_alias(evaluation.get("student_answer")) or ""
        criteria = definition["essential_criteria"]
        groups_met = [
            any(marker in answer for marker in criterion["markers"])
            for criterion in criteria
        ]
        missing = [
            criterion["label"]
            for criterion, met in zip(criteria, groups_met)
            if not met
        ]

        mapping_ok = True
        if definition.get("kind") == "mapping" and all(groups_met):
            mapping_ok = cls._mapping_roles_are_correct(answer, definition)
            if not mapping_ok:
                missing = ["relacionar corretamente entrada, processamento e saída"]

        if all(groups_met) and mapping_ok:
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.MET,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.MET,
                },
                definition["success"],
                missing_essential_criteria=[],
            )

        if any(groups_met):
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.PARTIAL,
                },
                "Reconheceu parte da situação, mas ainda falta uma relação essencial.",
                missing_essential_criteria=missing,
            )

        return cls._evidence(
            {
                RubricPolicy.TASK_RESPONSE: RubricPolicy.NOT_MET,
                RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.NOT_MET,
            },
            "A resposta ainda não identifica o componente pedido nessa situação.",
            missing_essential_criteria=missing,
        )

    @classmethod
    def _submitted_order(cls, answer):
        normalized = normalize_alias(answer) or ""
        numbers = tuple(re.findall(r"\b[123]\b", normalized))
        if len(numbers) == 3 and set(numbers) == {"1", "2", "3"}:
            return numbers

        positions = []
        for pattern in cls.ACTION_PATTERNS:
            match = pattern.search(normalized)
            if match is None:
                return None
            positions.append(match.start())

        if len(set(positions)) != len(positions):
            return None
        original_item_numbers = cls.CORRECT_NUMERIC_ORDER
        return tuple(
            original_item_numbers[index]
            for index in sorted(range(len(positions)), key=positions.__getitem__)
        )

    @staticmethod
    def _matches_order(answer, definition):
        normalized = normalize_alias(answer) or ""
        numbers = tuple(re.findall(r"\b[123]\b", normalized))
        expected_numbers = definition["numeric_order"]
        if expected_numbers and len(numbers) == 3 and set(numbers) == {"1", "2", "3"}:
            return numbers == expected_numbers, True

        positions = []
        for pattern in definition["patterns"]:
            match = pattern.search(normalized)
            if match is None:
                return False, False
            positions.append(match.start())

        if len(set(positions)) != len(positions):
            return False, False
        return positions == sorted(positions), True

    @staticmethod
    def _evidence(criteria, evidence, *, missing_essential_criteria=None):
        normalized = RubricPolicy.normalize_payload({"criteria": criteria})
        result = {
            "outcome": normalized["outcome"],
            "confidence": 1.0,
            "evidence": evidence,
            "criteria": normalized["criteria"],
            "rubric_complete": True,
            "outcome_source": "rubric",
            "source": "deterministic_task",
        }
        if missing_essential_criteria is not None:
            result["missing_essential_criteria"] = list(
                missing_essential_criteria
            )
        return result

    @classmethod
    def _evaluate_goal_result(cls, evaluation, definition):
        answer = normalize_alias(evaluation.get("student_answer")) or ""
        essential_criteria = definition["essential_criteria"]
        groups_met = [
            any(marker in answer for marker in criterion["markers"])
            for criterion in essential_criteria
        ]
        missing = [
            criterion["label"]
            for criterion, met in zip(essential_criteria, groups_met)
            if not met
        ]

        if definition["kind"] == "choice":
            choice = re.fullmatch(r"(?:opcao |alternativa )?([abc])", answer)
            if choice:
                if choice.group(1) == "a":
                    groups_met = [True] * len(groups_met)
                    missing = []
                else:
                    return cls._evidence(
                        {
                            RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                            RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.NOT_MET,
                            RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.PARTIAL,
                        },
                        "Escolheu uma situação que não corresponde ao resultado pedido.",
                    )

        # O microconceito avaliado é o estado final desejado, não a reprodução
        # literal de um rótulo como "Resultado:". Formato só pode afetar domínio
        # quando o próprio formato for o objeto explícito de aprendizagem.
        procedural_actions = (
            "abrir", "clicar", "selecionar", "pegar", "guardar",
            "escolher", "confirmar", "digitar", "escrever",
        )
        sequence_words = (
            "primeiro", "depois", "em seguida", "por ultimo",
        )
        action_hits = sum(marker in answer for marker in procedural_actions)
        lists_steps = (
            action_hits >= 2
            or (action_hits >= 1 and any(marker in answer for marker in sequence_words))
        )

        if definition["kind"] == "result" and lists_steps:
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.NOT_MET,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.PARTIAL,
                },
                "Listou ações em vez de descrever somente a situação final desejada.",
                missing_essential_criteria=[
                    "descrever somente a situação final, sem listar os passos"
                ],
            )

        if all(groups_met):
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.MET,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.MET,
                },
                definition["success"],
                missing_essential_criteria=[],
            )

        if any(groups_met):
            # PARTIAL nesta família significa falta conceitual real e, portanto,
            # sempre precisa apontar pelo menos um critério essencial ausente.
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.PARTIAL,
                },
                "Indicou parte do resultado, mas falta um critério essencial da tarefa.",
                missing_essential_criteria=missing,
            )

        return cls._evidence(
            {
                RubricPolicy.TASK_RESPONSE: RubricPolicy.NOT_MET,
                RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.NOT_MET,
            },
            "A resposta não descreveu o resultado final solicitado.",
            missing_essential_criteria=missing,
        )

    @classmethod
    def evaluate(cls, evaluation):
        definition = cls._task_definition(evaluation)
        if definition is None:
            goal_definition = cls._goal_result_definition(evaluation)
            if goal_definition is not None:
                return cls._evaluate_goal_result(evaluation, goal_definition)
            ipo_definition = cls._input_process_output_definition(evaluation)
            if ipo_definition is not None:
                return cls._evaluate_input_process_output(
                    evaluation,
                    ipo_definition,
                )
            return None

        correct, complete = cls._matches_order(
            evaluation.get("student_answer"),
            definition,
        )
        if correct:
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.MET,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.MET,
                },
                definition["success"],
            )

        if complete:
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.NOT_MET,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.PARTIAL,
                },
                "Incluiu os três passos, mas em ordem incorreta.",
            )

        return cls._evidence(
            {
                RubricPolicy.TASK_RESPONSE: RubricPolicy.NOT_MET,
                RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.NOT_MET,
            },
            "A resposta não apresentou os três passos pedidos em uma ordem avaliável.",
        )

# APEX_PEDAGOGICAL_EVAL_FIX_V2
# Conservative evaluator-only compatibility hook.
try:
    from backend.services.evaluation_policy import install_evaluator_policy as _apex_install_eval_v2
except ImportError:
    try:
        from services.evaluation_policy import install_evaluator_policy as _apex_install_eval_v2
    except ImportError:
        _apex_install_eval_v2 = None
if _apex_install_eval_v2 is not None:
    _apex_install_eval_v2(globals())

