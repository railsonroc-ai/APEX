from dataclasses import dataclass

from backend.services.assistance_policy import AssistancePolicy
from backend.services.task_policy import TaskPolicy
from backend.services.goal_result_tasks import GoalResultTasks
from backend.services.concept_catalog import ConceptCatalog


@dataclass(frozen=True)
class TurnTeachingContract:
    concept_id: str | None
    focus: str
    objective: str
    representation: str
    forbidden_terms: tuple[str, ...]
    allow_code: bool
    max_chars: int
    max_questions: int
    task_required: bool
    assistance_ceiling: str
    review_mode: bool
    feedback_text: str | None
    safe_response: str | None

    ORDERED_STEPS = "ads.algorithms.ordered_steps"
    GOAL_RESULT = "ads.algorithms.goal_result"
    CONTROLLED_CONCEPTS = {
        ORDERED_STEPS,
        GOAL_RESULT,
    }
    ORDERED_STEPS_FORBIDDEN = (
        "entrada", "processamento", "saída", "saida", "variável", "variavel",
        "operador", "condicional", "decisão", "decisao", "repetição",
        "repeticao", "laço", "laco", "função", "funcao", "lista",
        "portugol", "python", "sintaxe", "código", "codigo", "programação",
        "programacao", "fluxograma", "pseudocódigo", "pseudocodigo", "tipo de dado",
        "classe", "objeto", "api", "banco de dados",
    )
    GOAL_RESULT_FORBIDDEN = ORDERED_STEPS_FORBIDDEN

    FEEDBACK_BY_OUTCOME = {
        "demonstrated": "Correto.",
        "partial": "Parcialmente correto.",
        "misconception": "Ainda não está correto.",
        "insufficient": "Ainda não há evidência suficiente.",
        "unverified": "Não foi possível confirmar ainda.",
    }

    @classmethod
    def _feedback(cls, outcome):
        return cls.FEEDBACK_BY_OUTCOME.get(outcome)

    @staticmethod
    def _prepend_feedback(response, feedback):
        return f"{feedback}\n\n{response}" if feedback else response

    @staticmethod
    def _normalized_mastery(state):
        try:
            return min(1.0, max(0.0, float(state.get("mastery", 0.0))))
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _ordered_task(cls, mastery):
        if mastery < 0.2:
            return (
                "Tarefa: coloque estes passos na ordem correta: secar as mãos; "
                "abrir a torneira; lavar as mãos."
            )
        if mastery < 0.4:
            return (
                "Tarefa: descreva como guardar um arquivo usando exatamente três passos "
                "na ordem em que precisam acontecer."
            )
        if mastery < 0.6:
            return (
                "Tarefa: coloque em ordem: clicar em Enviar; escrever a mensagem; "
                "abrir a conversa."
            )
        return (
            "Tarefa: coloque em ordem: guardar o copo; pegar o copo; beber a água."
        )

    @classmethod
    def _goal_result_task(cls, mastery):
        return GoalResultTasks.prompt_for_mastery(mastery)

    @classmethod
    def build(
        cls,
        learner_state,
        teaching_action,
        *,
        review_mode=False,
        evidence_outcome=None,
    ):
        state = learner_state if isinstance(learner_state, dict) else {}
        concept_id = state.get("current_concept_id")
        review_mode = bool(
            review_mode
            or state.get("stage") == "reencontrar"
            or teaching_action == "revisar"
        )
        ceiling = AssistancePolicy.level_for_action(teaching_action)
        difficulty = state.get("difficulty_count", 0)
        try:
            difficulty = max(0, int(difficulty))
        except (TypeError, ValueError):
            difficulty = 0
        if teaching_action == "corrigir" and difficulty < 2:
            ceiling = "guided"
        task_required = TaskPolicy.is_assessable_action(teaching_action)
        feedback = cls._feedback(evidence_outcome)

        if concept_id == cls.ORDERED_STEPS:
            mastery = cls._normalized_mastery(state)
            if review_mode:
                safe = (
                    "Tarefa: de memória, descreva uma atividade cotidiana "
                    "em três passos na ordem em que precisa acontecer."
                )
            elif evidence_outcome in {"insufficient", "unverified"}:
                safe = cls._ordered_task(mastery)
            elif teaching_action == "corrigir" and difficulty < 2:
                safe = (
                    "Pense em apenas o começo: antes de lavar as mãos, é preciso "
                    "possibilitar que a água saia.\n\n"
                    "Tarefa: entre abrir a torneira e lavar as mãos, qual acontece primeiro?"
                )
            elif teaching_action == "corrigir":
                safe = (
                    "Correção completa: a ordem é abrir a torneira, lavar as mãos e secar "
                    "as mãos.\n\n"
                    "Tarefa: coloque em ordem: guardar o copo; pegar o copo; beber a água."
                )
            elif teaching_action == "avancar":
                safe = (
                    "Você concluiu esta microcompetência com evidências em mais de uma "
                    "atividade. Envie continuar quando estiver pronto para iniciar "
                    "objetivo e resultado de uma sequência."
                )
            elif teaching_action in {"testar", "verificar", "consolidar"}:
                safe = cls._ordered_task(mastery)
            else:
                safe = (
                    "Um algoritmo pode ser entendido primeiro como uma sequência de passos "
                    "colocados na ordem necessária para alcançar um resultado. Pense em escovar "
                    "os dentes: trocar a ordem dos passos pode mudar o que acontece.\n\n"
                    "Tarefa: coloque estes passos na ordem correta: secar as mãos; abrir a "
                    "torneira; lavar as mãos."
                )
            safe = cls._prepend_feedback(safe, feedback)
            return cls(
                concept_id=concept_id,
                focus="sequência ordenada de passos",
                objective="reconhecer que uma atividade tem passos e que a ordem importa",
                representation="situação cotidiana concreta, sem código",
                forbidden_terms=cls.ORDERED_STEPS_FORBIDDEN,
                allow_code=False,
                max_chars=750,
                max_questions=1,
                task_required=task_required,
                assistance_ceiling=ceiling,
                review_mode=review_mode,
                feedback_text=feedback,
                safe_response=safe,
            )

        if concept_id == cls.GOAL_RESULT:
            mastery = cls._normalized_mastery(state)
            if review_mode:
                safe = GoalResultTasks.review_prompt()
            elif evidence_outcome in {"insufficient", "unverified"}:
                safe = cls._goal_result_task(mastery)
            elif teaching_action == "corrigir" and difficulty < 2:
                safe = (
                    "Pense apenas em como a situação precisa ficar quando a atividade "
                    "terminar, sem listar os passos.\n\n"
                    + cls._goal_result_task(mastery)
                )
            elif teaching_action == "corrigir":
                safe = (
                    "Correção completa: resultado é a situação final desejada, não uma "
                    "lista de ações.\n\n"
                    + cls._goal_result_task(mastery)
                )
            elif teaching_action == "avancar":
                safe = (
                    "Você concluiu objetivo e resultado de uma sequência com evidências "
                    "em atividades diferentes. A próxima microcompetência ainda não está "
                    "disponível nesta versão do percurso."
                )
            elif teaching_action in {"testar", "verificar", "consolidar"}:
                safe = cls._goal_result_task(mastery)
            else:
                safe = (
                    "Antes de escolher os passos, é preciso saber como a situação deve "
                    "ficar no final. Esse estado final é o resultado esperado. Ao carregar "
                    "um celular, por exemplo, o resultado é o aparelho conectado e "
                    "recebendo carga.\n\n"
                    + cls._goal_result_task(mastery)
                )
            safe = cls._prepend_feedback(safe, feedback)
            return cls(
                concept_id=concept_id,
                focus="objetivo e resultado de uma sequência",
                objective=(
                    "distinguir o resultado final desejado dos passos usados para alcançá-lo"
                ),
                representation="situação cotidiana concreta, sem código",
                forbidden_terms=cls.GOAL_RESULT_FORBIDDEN,
                allow_code=False,
                max_chars=750,
                max_questions=1,
                task_required=task_required,
                assistance_ceiling=ceiling,
                review_mode=review_mode,
                feedback_text=feedback,
                safe_response=safe,
            )

        definition = ConceptCatalog.resolve(
            state.get("area", "ads"),
            concept_id,
        )
        safe_focus = (
            definition.get("canonical_name")
            if definition
            else "pedido atual"
        )
        if review_mode:
            safe = (
                f"Tarefa: de memória, explique com suas palavras o ponto "
                f"principal de {safe_focus}."
            )
        elif task_required:
            safe = (
                f"Tarefa: explique com suas palavras o ponto principal de "
                f"{safe_focus} trabalhado até aqui."
            )
        else:
            safe = "Vamos continuar a partir do que você já demonstrou até aqui."
        safe = cls._prepend_feedback(safe, feedback)
        return cls(
            concept_id=concept_id,
            focus=safe_focus,
            objective="executar somente a ação pedagógica decidida pelo servidor",
            representation="explicação curta e concreta antes de ampliar abstrações",
            forbidden_terms=(),
            allow_code=True,
            max_chars=1600,
            max_questions=1,
            task_required=task_required,
            assistance_ceiling=ceiling,
            review_mode=review_mode,
            feedback_text=feedback,
            safe_response=safe,
        )

    def as_prompt(self):
        forbidden = ", ".join(self.forbidden_terms) or "nenhum termo específico"
        return (
            "CONTRATO EXECUTÁVEL DESTE TURNO (obrigatório):\n"
            f"- conceito: {self.concept_id or 'não definido'}\n"
            f"- única novidade permitida: {self.focus}\n"
            f"- objetivo: {self.objective}\n"
            f"- representação: {self.representation}\n"
            f"- termos/novidades proibidos: {forbidden}\n"
            f"- código permitido: {'sim' if self.allow_code else 'não'}\n"
            f"- limite: {self.max_chars} caracteres e {self.max_questions} pergunta\n"
            f"- tarefa única obrigatória: {'sim' if self.task_required else 'não'}\n"
            f"- teto de assistência: {self.assistance_ceiling}\n"
            f"- feedback obrigatório no início: {self.feedback_text or 'nenhum'}\n"
            f"- revisão recuperativa: {'sim' if self.review_mode else 'não'}"
        )
