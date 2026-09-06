import re

from backend.concepts import normalize_alias
from backend.services.rubric_policy import RubricPolicy
from backend.services.goal_result_tasks import GoalResultTasks
from backend.services.input_process_output_tasks import InputProcessOutputTasks
from backend.services.structured_sequence_tasks import StructuredSequenceTasks
from backend.services.portugol_skeleton_tasks import PortugolSkeletonTasks
from backend.services.portugol_write_tasks import PortugolWriteTasks
from backend.services.portugol_read_tasks import PortugolReadTasks


class ObjectiveTaskEvaluator:
    """Avalia tarefas fechadas sem depender de julgamento probabilístico.

    O avaliador só assume uma tarefa quando reconhece simultaneamente o
    conceito e o enunciado persistido. Respostas a tarefas abertas continuam
    seguindo para o avaliador semântico.
    """

    ORDERED_STEPS = "ads.algorithms.ordered_steps"
    GOAL_RESULT = "ads.algorithms.goal_result"
    INPUT_PROCESS_OUTPUT = "ads.algorithms.input_process_output"
    STRUCTURED_SEQUENCE = "ads.algorithms.structured_sequence"
    PORTUGOL_SKELETON = "ads.algorithms.portugol_skeleton"
    PORTUGOL_WRITE = "ads.algorithms.portugol_write"
    PORTUGOL_READ = "ads.algorithms.portugol_read"
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

    @classmethod
    def _structured_sequence_definition(cls, evaluation):
        if not isinstance(evaluation, dict):
            return None
        if evaluation.get("concept_id") != cls.STRUCTURED_SEQUENCE:
            return None
        return StructuredSequenceTasks.definition_for_prompt(
            evaluation.get("tutor_message")
        )

    @classmethod
    def _portugol_skeleton_definition(cls, evaluation):
        if not isinstance(evaluation, dict):
            return None
        if evaluation.get("concept_id") != cls.PORTUGOL_SKELETON:
            return None
        return PortugolSkeletonTasks.definition_for_prompt(
            evaluation.get("tutor_message")
        )

    @classmethod
    def _portugol_write_definition(cls, evaluation):
        if not isinstance(evaluation, dict):
            return None
        if evaluation.get("concept_id") != cls.PORTUGOL_WRITE:
            return None
        return PortugolWriteTasks.definition_for_prompt(
            evaluation.get("tutor_message")
        )

    @classmethod
    def _portugol_read_definition(cls, evaluation):
        if not isinstance(evaluation, dict):
            return None
        if evaluation.get("concept_id") != cls.PORTUGOL_READ:
            return None
        return PortugolReadTasks.definition_for_prompt(
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

    @staticmethod
    def _group_positions(answer, groups):
        positions = []
        missing = []
        for index, group in enumerate(groups, start=1):
            hits = [answer.find(marker) for marker in group]
            hits = [hit for hit in hits if hit >= 0]
            if not hits:
                positions.append(None)
                missing.append(f"passo {index}")
            else:
                positions.append(min(hits))
        return positions, missing

    @classmethod
    def _evaluate_structured_sequence(cls, evaluation, definition):
        normalized = normalize_alias(evaluation.get("student_answer")) or ""
        kind = definition.get("kind")

        if kind == "missing_step":
            groups = definition["essential_groups"]
            matched = [any(marker in normalized for marker in group) for group in groups]
            if all(matched):
                return cls._evidence(
                    {
                        RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                        RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.MET,
                        RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.MET,
                    },
                    definition["success"],
                    missing_essential_criteria=[],
                )
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.NOT_MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.NOT_MET,
                },
                "Ainda falta identificar o passo ausente da sequência.",
                missing_essential_criteria=["identificar o passo ausente"],
            )

        groups = definition.get("ordered_groups") or ()
        positions, missing = cls._group_positions(normalized, groups)
        complete = not missing
        ordered = complete and positions == sorted(positions)
        structural_missing = list(missing)

        if kind == "numbered_order":
            number_positions = [
                re.search(rf"\b{number}\b", normalized)
                for number in (1, 2, 3)
            ]
            if any(match is None for match in number_positions):
                structural_missing.append("usar 1, 2 e 3 para explicitar a estrutura")
                numbered_ok = False
            else:
                nums = [match.start() for match in number_positions]
                numbered_ok = (
                    nums == sorted(nums)
                    and complete
                    and all(nums[i] < positions[i] for i in range(3))
                )
                if not numbered_ok:
                    structural_missing.append("associar 1, 2 e 3 aos passos na ordem correta")
            structure_ok = numbered_ok
        else:
            start = normalized.find("inicio")
            end = normalized.rfind("fim")
            structure_ok = (
                start >= 0
                and end >= 0
                and start < end
                and complete
                and start < positions[0]
                and end > positions[-1]
            )
            if start < 0:
                structural_missing.append("marcar INÍCIO antes dos passos")
            if end < 0:
                structural_missing.append("marcar FIM depois dos passos")
            if start >= 0 and end >= 0 and not structure_ok:
                structural_missing.append("manter INÍCIO antes e FIM depois da sequência")

        if complete and ordered and structure_ok:
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.MET,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.MET,
                },
                definition["success"],
                missing_essential_criteria=[],
            )

        if complete or any(position is not None for position in positions):
            if complete and not ordered:
                structural_missing.append("manter os passos na ordem lógica")
            structural_missing = list(dict.fromkeys(structural_missing))
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.PARTIAL,
                },
                "A representação contém parte da lógica, mas falta um critério estrutural essencial.",
                missing_essential_criteria=structural_missing,
            )

        return cls._evidence(
            {
                RubricPolicy.TASK_RESPONSE: RubricPolicy.NOT_MET,
                RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.NOT_MET,
            },
            "A resposta ainda não representa a sequência pedida.",
            missing_essential_criteria=structural_missing or ["representar os passos pedidos"],
        )

    @classmethod
    def _evaluate_portugol_skeleton(cls, evaluation, definition):
        normalized = normalize_alias(evaluation.get("student_answer")) or ""
        kind = definition.get("kind")

        if kind == "single_keyword":
            required = definition["required_keyword"]
            if re.search(rf"\b{re.escape(required)}\b", normalized):
                return cls._evidence(
                    {
                        RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                        RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.MET,
                        RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.MET,
                    },
                    definition["success"],
                    missing_essential_criteria=[],
                )
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.NOT_MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.NOT_MET,
                },
                "A resposta ainda não identifica a palavra estrutural pedida.",
                missing_essential_criteria=[f"identificar {required}"],
            )

        keywords = tuple(definition.get("ordered_keywords") or ())
        positions = []
        missing = []
        for keyword in keywords:
            match = re.search(rf"\b{re.escape(keyword)}\b", normalized)
            if match is None:
                positions.append(None)
                missing.append(f"incluir {keyword}")
            else:
                positions.append(match.start())

        if not missing and positions == sorted(positions):
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.MET,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.MET,
                },
                definition["success"],
                missing_essential_criteria=[],
            )

        if not missing:
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.NOT_MET,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.PARTIAL,
                },
                "As três palavras aparecem, mas a ordem estrutural está incorreta.",
                missing_essential_criteria=[
                    "manter algoritmo antes de inicio e fimalgoritmo depois de inicio"
                ],
            )

        if any(position is not None for position in positions):
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.PARTIAL,
                },
                "A estrutura está parcialmente representada, mas falta palavra essencial.",
                missing_essential_criteria=missing,
            )

        return cls._evidence(
            {
                RubricPolicy.TASK_RESPONSE: RubricPolicy.NOT_MET,
                RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.NOT_MET,
            },
            "A resposta ainda não representa a estrutura mínima pedida.",
            missing_essential_criteria=missing,
        )

    @staticmethod
    def _has_write_call(answer, expected_text):
        raw = str(answer or "").casefold()
        match = re.search(
            r"\bescreva\s*\(\s*([\"'])([^\"']+)\1\s*\)",
            raw,
            flags=re.IGNORECASE,
        )
        if match is None:
            return False
        expected = normalize_alias(expected_text) or ""
        actual = normalize_alias(match.group(2)) or ""
        return bool(expected) and actual == expected

    @classmethod
    def _evaluate_portugol_write(cls, evaluation, definition):
        normalized = normalize_alias(evaluation.get("student_answer")) or ""
        kind = definition.get("kind")

        if kind == "single_keyword":
            required = definition["required_keyword"]
            if re.search(rf"\b{re.escape(required)}\b", normalized):
                return cls._evidence(
                    {
                        RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                        RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.MET,
                        RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.MET,
                    },
                    definition["success"],
                    missing_essential_criteria=[],
                )
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.NOT_MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.NOT_MET,
                },
                "A resposta ainda não identifica o comando pedido.",
                missing_essential_criteria=["identificar escreva"],
            )

        if kind == "expected_output":
            expected = normalize_alias(definition.get("expected_output")) or ""
            if normalized == expected:
                return cls._evidence(
                    {
                        RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                        RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.MET,
                        RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.MET,
                    },
                    definition["success"],
                    missing_essential_criteria=[],
                )
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.NOT_MET,
                },
                "A saída indicada não corresponde ao texto mostrado pelo comando.",
                missing_essential_criteria=["identificar o texto exibido"],
            )

        expected_text = definition.get("expected_text") or ""
        write_ok = cls._has_write_call(evaluation.get("student_answer"), expected_text)

        if kind == "write_line":
            if write_ok:
                return cls._evidence(
                    {
                        RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                        RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.MET,
                        RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.MET,
                    },
                    definition["success"],
                    missing_essential_criteria=[],
                )
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.PARTIAL,
                },
                "A linha ainda não usa escreva com o texto pedido entre aspas.",
                missing_essential_criteria=["formar escreva com o texto pedido entre aspas"],
            )

        keywords = tuple(definition.get("ordered_keywords") or ())
        positions = []
        for keyword in keywords:
            match = re.search(rf"\b{re.escape(keyword)}\b", normalized)
            positions.append(None if match is None else match.start())
        complete = all(position is not None for position in positions)
        ordered = complete and positions == sorted(positions)

        if write_ok and ordered:
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.MET,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.MET,
                },
                definition["success"],
                missing_essential_criteria=[],
            )

        missing = []
        if not write_ok:
            missing.append("usar escreva com o texto pedido entre aspas")
        if not complete:
            missing.append("incluir algoritmo, inicio, escreva e fimalgoritmo")
        elif not ordered:
            missing.append("manter escreva entre inicio e fimalgoritmo")
        return cls._evidence(
            {
                RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.PARTIAL,
            },
            "A integração ainda não mantém todos os critérios essenciais da estrutura.",
            missing_essential_criteria=missing,
        )

    @classmethod
    def _evaluate_portugol_read(cls, evaluation, definition):
        normalized = normalize_alias(evaluation.get("student_answer")) or ""
        kind = definition.get("kind")

        if kind == "single_keyword":
            required = definition["required_keyword"]
            if normalized == required:
                return cls._evidence(
                    {
                        RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                        RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.MET,
                        RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.MET,
                    },
                    definition["success"],
                    missing_essential_criteria=[],
                )
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.NOT_MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.NOT_MET,
                },
                "A resposta ainda não identifica leia como o comando pedido.",
                missing_essential_criteria=["identificar leia"],
            )

        if kind == "role_choice":
            expected = normalize_alias(definition.get("expected_role")) or ""
            if normalized == expected:
                return cls._evidence(
                    {
                        RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                        RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.MET,
                        RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.MET,
                    },
                    definition["success"],
                    missing_essential_criteria=[],
                )
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.NOT_MET,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.PARTIAL,
                },
                "O papel indicado para leia ainda não corresponde à entrada.",
                missing_essential_criteria=["relacionar leia à entrada"],
            )

        keywords = tuple(definition.get("ordered_keywords") or ())
        positions = []
        missing = []
        for keyword in keywords:
            match = re.search(rf"\b{re.escape(keyword)}\b", normalized)
            if match is None:
                positions.append(None)
                missing.append(f"incluir {keyword}")
            else:
                positions.append(match.start())
        complete = not missing
        ordered = complete and positions == sorted(positions)

        if complete and ordered:
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.MET,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.MET,
                },
                definition["success"],
                missing_essential_criteria=[],
            )

        if complete and not ordered:
            missing.append("manter algoritmo, inicio, leia, escreva e fimalgoritmo nessa ordem")
        return cls._evidence(
            {
                RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.PARTIAL,
            },
            "A sequência ainda não posiciona leia corretamente na estrutura conhecida.",
            missing_essential_criteria=missing or ["posicionar leia antes de escreva"],
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
            structured_definition = cls._structured_sequence_definition(evaluation)
            if structured_definition is not None:
                return cls._evaluate_structured_sequence(
                    evaluation,
                    structured_definition,
                )
            portugol_definition = cls._portugol_skeleton_definition(evaluation)
            if portugol_definition is not None:
                return cls._evaluate_portugol_skeleton(
                    evaluation,
                    portugol_definition,
                )
            write_definition = cls._portugol_write_definition(evaluation)
            if write_definition is not None:
                return cls._evaluate_portugol_write(
                    evaluation,
                    write_definition,
                )
            read_definition = cls._portugol_read_definition(evaluation)
            if read_definition is not None:
                return cls._evaluate_portugol_read(
                    evaluation,
                    read_definition,
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
