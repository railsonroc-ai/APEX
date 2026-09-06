from dataclasses import dataclass

from backend.services.assistance_policy import AssistancePolicy
from backend.services.task_policy import TaskPolicy
from backend.services.goal_result_tasks import GoalResultTasks
from backend.services.input_process_output_tasks import InputProcessOutputTasks
from backend.services.structured_sequence_tasks import StructuredSequenceTasks
from backend.services.portugol_skeleton_tasks import PortugolSkeletonTasks
from backend.services.portugol_write_tasks import PortugolWriteTasks
from backend.services.portugol_read_tasks import PortugolReadTasks
from backend.services.variable_storage_tasks import VariableStorageTasks
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
    INPUT_PROCESS_OUTPUT = "ads.algorithms.input_process_output"
    STRUCTURED_SEQUENCE = "ads.algorithms.structured_sequence"
    PORTUGOL_SKELETON = "ads.algorithms.portugol_skeleton"
    PORTUGOL_WRITE = "ads.algorithms.portugol_write"
    PORTUGOL_READ = "ads.algorithms.portugol_read"
    VARIABLE_STORAGE = "ads.algorithms.variable_storage"
    CONTROLLED_CONCEPTS = {
        ORDERED_STEPS,
        GOAL_RESULT,
        INPUT_PROCESS_OUTPUT,
        STRUCTURED_SEQUENCE,
        PORTUGOL_SKELETON,
        PORTUGOL_WRITE,
        PORTUGOL_READ,
        VARIABLE_STORAGE,
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
    IPO_FUTURE_FORBIDDEN = (
        "variável", "variavel", "operador", "condicional", "decisão", "decisao",
        "repetição", "repeticao", "laço", "laco", "função", "funcao", "lista",
        "portugol", "python", "sintaxe", "código", "codigo", "programação",
        "programacao", "fluxograma", "pseudocódigo", "pseudocodigo", "tipo de dado",
        "classe", "objeto", "api", "banco de dados",
    )
    STRUCTURED_FUTURE_FORBIDDEN = (
        "variável", "variavel", "operador", "condicional", "decisão", "decisao",
        "repetição", "repeticao", "laço", "laco", "função", "funcao", "lista",
        "portugol", "python", "sintaxe", "código", "codigo", "programação",
        "programacao", "fluxograma", "pseudocódigo", "pseudocodigo", "tipo de dado",
        "escreva", "algoritmo", "var", "classe", "objeto", "api",
        "banco de dados",
    )
    PORTUGOL_FUTURE_FORBIDDEN = (
        "variável", "variavel", "var", "inteiro", "real", "caractere", "cadeia",
        "lógico", "logico", "leia", "escreva", "operador", "condicional",
        "decisão", "decisao", "se", "então", "entao", "senão", "senao",
        "repetição", "repeticao", "enquanto", "para", "repita", "função",
        "funcao", "procedimento", "lista", "python", "classe", "objeto", "api",
        "banco de dados",
    )
    PORTUGOL_WRITE_FUTURE_FORBIDDEN = (
        "leia", "escreval", "variável", "variavel", "var", "inteiro", "real",
        "caractere", "cadeia", "lógico", "logico", "operador", "condicional",
        "decisão", "decisao", "se", "então", "entao", "senão", "senao",
        "repetição", "repeticao", "enquanto", "repita", "função",
        "funcao", "procedimento", "lista", "python", "classe", "objeto", "api",
        "banco de dados",
    )
    PORTUGOL_READ_FUTURE_FORBIDDEN = (
        "escreval", "variável", "variavel", "var", "inteiro", "real",
        "caractere", "cadeia", "lógico", "logico", "operador", "condicional",
        "decisão", "decisao", "se", "então", "entao", "senão", "senao",
        "repetição", "repeticao", "enquanto", "repita", "função",
        "funcao", "procedimento", "lista", "vetor", "matriz", "python",
        "classe", "objeto", "api", "banco de dados",
    )
    VARIABLE_STORAGE_FUTURE_FORBIDDEN = (
        "declaração", "declaracao", "var", "inteiro", "real", "caractere",
        "cadeia", "lógico", "logico", "tipo de dado", "leia", "escreva",
        "escreval", "atribuição", "atribuicao", "operador", "condicional",
        "decisão", "decisao", "senão", "senao",
        "repetição", "repeticao", "repita", "função",
        "funcao", "procedimento", "lista", "vetor", "matriz", "python",
        "classe", "objeto", "api", "banco de dados",
    )

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
    def _ipo_task(cls, mastery):
        return InputProcessOutputTasks.prompt_for_mastery(mastery)

    @classmethod
    def _structured_task(cls, mastery):
        return StructuredSequenceTasks.prompt_for_mastery(mastery)

    @classmethod
    def _portugol_task(cls, mastery):
        return PortugolSkeletonTasks.prompt_for_mastery(mastery)

    @classmethod
    def _portugol_write_task(cls, mastery):
        return PortugolWriteTasks.prompt_for_mastery(mastery)

    @classmethod
    def _portugol_read_task(cls, mastery):
        return PortugolReadTasks.prompt_for_mastery(mastery)

    @classmethod
    def _variable_storage_task(cls, mastery):
        return VariableStorageTasks.prompt_for_mastery(mastery)

    @classmethod
    def _ipo_forbidden(cls, mastery):
        if mastery < 0.20:
            return ("processamento", "saída", "saida", *cls.IPO_FUTURE_FORBIDDEN)
        if mastery < 0.40:
            return ("saída", "saida", *cls.IPO_FUTURE_FORBIDDEN)
        return cls.IPO_FUTURE_FORBIDDEN

    @classmethod
    def _structured_forbidden(cls, mastery):
        if mastery < 0.20:
            return ("início", "inicio", "fim", *cls.STRUCTURED_FUTURE_FORBIDDEN)
        return cls.STRUCTURED_FUTURE_FORBIDDEN

    @classmethod
    def _portugol_forbidden(cls, mastery):
        if mastery < 0.20:
            return ("início", "inicio", "fimalgoritmo", *cls.PORTUGOL_FUTURE_FORBIDDEN)
        if mastery < 0.40:
            return ("fimalgoritmo", *cls.PORTUGOL_FUTURE_FORBIDDEN)
        return cls.PORTUGOL_FUTURE_FORBIDDEN

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
                    "em atividades realmente diferentes. Envie continuar quando estiver "
                    "pronto para iniciar a próxima microcompetência."
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

        if concept_id == cls.INPUT_PROCESS_OUTPUT:
            mastery = cls._normalized_mastery(state)
            focus = InputProcessOutputTasks.focus_for_mastery(mastery)
            if review_mode:
                safe = InputProcessOutputTasks.review_prompt()
            elif evidence_outcome in {"insufficient", "unverified"}:
                safe = cls._ipo_task(mastery)
            elif teaching_action == "corrigir" and difficulty < 2:
                safe = (
                    f"Retome apenas a ideia de {focus}: observe qual parte da situação "
                    "a tarefa está pedindo.\n\n" + cls._ipo_task(mastery)
                )
            elif teaching_action == "corrigir":
                safe = (
                    f"Vamos separar somente {focus} nesta tentativa.\n\n"
                    + cls._ipo_task(mastery)
                )
            elif teaching_action == "avancar":
                safe = (
                    "Você concluiu entrada, processamento e saída com evidências em "
                    "atividades realmente diferentes. Esta fatia do percurso está concluída. "
                    "Envie continuar quando estiver pronto para representar essa lógica de "
                    "forma estruturada."
                )
            elif teaching_action in {"testar", "verificar", "consolidar"}:
                if mastery < 0.40 and focus == "processamento":
                    safe = (
                        "Agora uma novidade: processamento é o que acontece com o que a "
                        "atividade recebeu.\n\n" + cls._ipo_task(mastery)
                    )
                elif mastery < 0.60 and focus == "saída":
                    safe = (
                        "Agora uma novidade: saída é o que a atividade entrega no final.\n\n"
                        + cls._ipo_task(mastery)
                    )
                elif mastery >= 0.60:
                    safe = (
                        "Agora reúna as três ideias que você já viu, sem acrescentar uma "
                        "nova.\n\n" + cls._ipo_task(mastery)
                    )
                else:
                    safe = cls._ipo_task(mastery)
            else:
                safe = (
                    "Entrada é o que uma atividade recebe para começar. Pense somente no "
                    "que chega antes de qualquer mudança.\n\n" + cls._ipo_task(mastery)
                )
            safe = cls._prepend_feedback(safe, feedback)
            return cls(
                concept_id=concept_id,
                focus=focus,
                objective=(
                    "reconhecer entrada, processamento e saída em situações concretas, "
                    "uma ideia nova por vez"
                ),
                representation="situação cotidiana concreta, sem código",
                forbidden_terms=cls._ipo_forbidden(mastery),
                allow_code=False,
                max_chars=800,
                max_questions=1,
                task_required=task_required,
                assistance_ceiling=ceiling,
                review_mode=review_mode,
                feedback_text=feedback,
                safe_response=safe,
            )

        if concept_id == cls.STRUCTURED_SEQUENCE:
            mastery = cls._normalized_mastery(state)
            focus = StructuredSequenceTasks.focus_for_mastery(mastery)
            if review_mode:
                safe = StructuredSequenceTasks.review_prompt()
            elif evidence_outcome in {"insufficient", "unverified"}:
                safe = cls._structured_task(mastery)
            elif teaching_action == "corrigir" and difficulty < 2:
                if mastery < 0.20:
                    hint = "Use os números apenas para tornar visível qual passo vem antes do outro."
                elif mastery < 0.40:
                    hint = "INÍCIO fica antes dos passos e FIM fica depois deles."
                else:
                    hint = "Leia a estrutura na mesma direção em que a atividade acontece."
                safe = hint + "\n\n" + cls._structured_task(mastery)
            elif teaching_action == "corrigir":
                safe = (
                    "Retome somente a forma de representar a sequência.\n\n"
                    + cls._structured_task(mastery)
                )
            elif teaching_action == "avancar":
                safe = (
                    "Você concluiu representação estruturada de uma sequência com evidências "
                    "em atividades diferentes. Envie continuar quando estiver pronto para "
                    "iniciar a próxima microcompetência."
                )
            elif teaching_action in {"testar", "verificar", "consolidar"}:
                safe = cls._structured_task(mastery)
            else:
                safe = (
                    "Você já sabe pensar na ordem da lógica. Agora vamos apenas tornar essa "
                    "ordem visível: cada passo recebe uma posição explícita.\n\n"
                    + cls._structured_task(mastery)
                )
            safe = cls._prepend_feedback(safe, feedback)
            return cls(
                concept_id=concept_id,
                focus=focus,
                objective=(
                    "transformar uma lógica já compreendida em representação estruturada, "
                    "sem introduzir sintaxe de programação"
                ),
                representation="passos estruturados, ainda sem código",
                forbidden_terms=cls._structured_forbidden(mastery),
                allow_code=False,
                max_chars=850,
                max_questions=1,
                task_required=task_required,
                assistance_ceiling=ceiling,
                review_mode=review_mode,
                feedback_text=feedback,
                safe_response=safe,
            )

        if concept_id == cls.PORTUGOL_SKELETON:
            mastery = cls._normalized_mastery(state)
            focus = PortugolSkeletonTasks.focus_for_mastery(mastery)
            if review_mode:
                safe = PortugolSkeletonTasks.review_prompt()
            elif evidence_outcome in {"insufficient", "unverified"}:
                safe = cls._portugol_task(mastery)
            elif teaching_action == "corrigir" and difficulty < 2:
                if mastery < 0.20:
                    hint = "A primeira palavra identifica que a estrutura é um algoritmo."
                elif mastery < 0.40:
                    hint = "A palavra pedida marca exatamente onde os passos começam."
                elif mastery < 0.60:
                    hint = "A palavra pedida encerra a estrutura inteira."
                else:
                    hint = "Mantenha as três palavras na mesma ordem em que a estrutura abre, começa e encerra."
                safe = hint + "\n\n" + cls._portugol_task(mastery)
            elif teaching_action == "corrigir":
                safe = (
                    "Retome somente a palavra estrutural pedida neste turno.\n\n"
                    + cls._portugol_task(mastery)
                )
            elif teaching_action == "avancar":
                safe = (
                    "Você concluiu a estrutura mínima do Portugol com evidências em "
                    "atividades diferentes. Envie continuar quando estiver pronto. A próxima "
                    "microcompetência virá em seguida."
                )
            elif teaching_action in {"testar", "verificar", "consolidar"}:
                if mastery < 0.20:
                    safe = cls._portugol_task(mastery)
                elif mastery < 0.40:
                    safe = (
                        "Agora uma novidade: inicio marca onde os passos começam.\n\n"
                        + cls._portugol_task(mastery)
                    )
                elif mastery < 0.60:
                    safe = (
                        "Agora uma novidade: fimalgoritmo marca onde a estrutura termina.\n\n"
                        + cls._portugol_task(mastery)
                    )
                else:
                    safe = (
                        "Agora reúna somente as três palavras já estudadas, sem acrescentar "
                        "nenhum comando novo.\n\n" + cls._portugol_task(mastery)
                    )
            else:
                safe = (
                    "Você já sabe representar uma sequência. Agora vamos trocar somente a "
                    "primeira marca por uma palavra do Portugol: algoritmo identifica o "
                    "cabeçalho da estrutura.\n\n" + cls._portugol_task(mastery)
                )
            safe = cls._prepend_feedback(safe, feedback)
            return cls(
                concept_id=concept_id,
                focus=focus,
                objective=(
                    "reconhecer e ordenar algoritmo, inicio e fimalgoritmo, uma palavra nova "
                    "por vez, sem introduzir comandos internos"
                ),
                representation="sintaxe mínima de Portugol, limitada à estrutura externa",
                forbidden_terms=cls._portugol_forbidden(mastery),
                allow_code=True,
                max_chars=850,
                max_questions=1,
                task_required=task_required,
                assistance_ceiling=ceiling,
                review_mode=review_mode,
                feedback_text=feedback,
                safe_response=safe,
            )

        if concept_id == cls.PORTUGOL_WRITE:
            mastery = cls._normalized_mastery(state)
            focus = PortugolWriteTasks.focus_for_mastery(mastery)
            if review_mode:
                safe = PortugolWriteTasks.review_prompt()
            elif evidence_outcome in {"insufficient", "unverified"}:
                safe = cls._portugol_write_task(mastery)
            elif teaching_action == "corrigir" and difficulty < 2:
                if mastery < 0.20:
                    hint = "A palavra que falta é o comando usado para mostrar algo na tela."
                elif mastery < 0.40:
                    hint = "Observe somente o texto colocado dentro do comando."
                elif mastery < 0.60:
                    hint = "A linha fica entre inicio e fimalgoritmo, usando o comando já estudado."
                else:
                    hint = "Mantenha a estrutura conhecida e coloque escreva entre inicio e fimalgoritmo."
                safe = hint + "\n\n" + cls._portugol_write_task(mastery)
            elif teaching_action == "corrigir":
                safe = (
                    "Retome somente o uso de escreva para produzir a saída pedida.\n\n"
                    + cls._portugol_write_task(mastery)
                )
            elif teaching_action == "avancar":
                safe = (
                    "Você concluiu saída simples com escreva com evidências em atividades "
                    "diferentes. Envie continuar quando estiver pronto para a próxima "
                    "microcompetência."
                )
            elif teaching_action in {"testar", "verificar", "consolidar"}:
                if mastery < 0.20:
                    safe = cls._portugol_write_task(mastery)
                elif mastery < 0.40:
                    safe = (
                        "O mesmo comando agora em outro contexto: o texto colocado em escreva "
                        "é o que aparece na tela.\n\n" + cls._portugol_write_task(mastery)
                    )
                elif mastery < 0.60:
                    safe = (
                        "Agora use o mesmo escreva dentro da estrutura que você já conhece.\n\n"
                        + cls._portugol_write_task(mastery)
                    )
                else:
                    safe = (
                        "Agora integre somente o mesmo escreva à estrutura já conhecida.\n\n"
                        + cls._portugol_write_task(mastery)
                    )
            else:
                safe = (
                    'Agora uma novidade: escreva mostra na tela o texto colocado entre aspas. '
                    'Exemplo: escreva("Olá").\n\n' + cls._portugol_write_task(mastery)
                )
            safe = cls._prepend_feedback(safe, feedback)
            return cls(
                concept_id=concept_id,
                focus=focus,
                objective=(
                    "usar escreva para produzir uma saída simples, reutilizando somente a "
                    "estrutura mínima já dominada"
                ),
                representation="sintaxe de Portugol limitada ao comando escreva com texto fixo",
                forbidden_terms=cls.PORTUGOL_WRITE_FUTURE_FORBIDDEN,
                allow_code=True,
                max_chars=900,
                max_questions=1,
                task_required=task_required,
                assistance_ceiling=ceiling,
                review_mode=review_mode,
                feedback_text=feedback,
                safe_response=safe,
            )

        if concept_id == cls.PORTUGOL_READ:
            mastery = cls._normalized_mastery(state)
            focus = PortugolReadTasks.focus_for_mastery(mastery)
            if review_mode:
                safe = PortugolReadTasks.review_prompt()
            elif evidence_outcome in {"insufficient", "unverified"}:
                safe = cls._portugol_read_task(mastery)
            elif teaching_action == "corrigir" and difficulty < 2:
                if mastery < 0.20:
                    hint = "A palavra pedida é o comando associado ao recebimento de uma entrada."
                elif mastery < 0.40:
                    hint = "Pense no sentido do fluxo: receber informação é entrada, não saída."
                elif mastery < 0.60:
                    hint = "A entrada acontece antes do comando de saída que você já conhece."
                else:
                    hint = "Mantenha a ordem conhecida e coloque leia depois de inicio e antes de escreva."
                safe = hint + "\n\n" + cls._portugol_read_task(mastery)
            elif teaching_action == "corrigir":
                safe = (
                    "Retome somente o papel e a posição de leia como entrada.\n\n"
                    + cls._portugol_read_task(mastery)
                )
            elif teaching_action == "avancar":
                safe = (
                    "Você concluiu entrada simples com leia com evidências em atividades "
                    "diferentes. Envie continuar quando estiver pronto para a próxima "
                    "microcompetência."
                )
            elif teaching_action in {"testar", "verificar", "consolidar"}:
                if mastery < 0.20:
                    safe = cls._portugol_read_task(mastery)
                elif mastery < 0.40:
                    safe = (
                        "Agora relacione o mesmo comando ao conceito de entrada que você já domina.\n\n"
                        + cls._portugol_read_task(mastery)
                    )
                elif mastery < 0.60:
                    safe = (
                        "Agora posicione o mesmo leia antes da saída já conhecida.\n\n"
                        + cls._portugol_read_task(mastery)
                    )
                else:
                    safe = (
                        "Agora integre somente leia à ordem da estrutura já conhecida; o interior "
                        "do comando ficará para a próxima etapa.\n\n" + cls._portugol_read_task(mastery)
                    )
            else:
                safe = (
                    "Você já usa escreva para produzir uma saída. Agora uma novidade: leia indica "
                    "que o algoritmo recebe uma entrada. Nesta etapa, vamos aprender somente o "
                    "papel e a posição de leia.\n\n" + cls._portugol_read_task(mastery)
                )
            safe = cls._prepend_feedback(safe, feedback)
            return cls(
                concept_id=concept_id,
                focus=focus,
                objective=(
                    "reconhecer e posicionar leia como comando de entrada, reutilizando somente "
                    "a estrutura e o escreva já dominados"
                ),
                representation=(
                    "sintaxe de Portugol limitada ao comando leia como marcador de entrada, "
                    "sem preencher seu conteúdo interno"
                ),
                forbidden_terms=cls.PORTUGOL_READ_FUTURE_FORBIDDEN,
                allow_code=True,
                max_chars=950,
                max_questions=1,
                task_required=task_required,
                assistance_ceiling=ceiling,
                review_mode=review_mode,
                feedback_text=feedback,
                safe_response=safe,
            )

        if concept_id == cls.VARIABLE_STORAGE:
            mastery = cls._normalized_mastery(state)
            focus = VariableStorageTasks.focus_for_mastery(mastery)
            if review_mode:
                safe = VariableStorageTasks.review_prompt()
            elif evidence_outcome in {"insufficient", "unverified"}:
                safe = cls._variable_storage_task(mastery)
            elif teaching_action == "corrigir" and difficulty < 2:
                if mastery < 0.20:
                    hint = "Pense em um lugar identificado por um nome que mantém um valor."
                elif mastery < 0.40:
                    hint = "Separe duas coisas: o nome identifica o lugar; o valor é o conteúdo guardado."
                elif mastery < 0.60:
                    hint = "O conteúdo pode mudar sem trocar o nome do lugar."
                else:
                    hint = "Procure o nome que permanece e o último valor que ficou guardado."
                safe = hint + "\n\n" + cls._variable_storage_task(mastery)
            elif teaching_action == "corrigir":
                safe = (
                    "Retome somente esta ideia: uma variável é um lugar com nome que guarda um valor.\n\n"
                    + cls._variable_storage_task(mastery)
                )
            elif teaching_action == "avancar":
                safe = (
                    "Você concluiu variável como armazenamento nomeado com evidências em "
                    "atividades diferentes. Esta fatia do percurso está concluída."
                )
            elif teaching_action in {"testar", "verificar", "consolidar"}:
                if mastery < 0.20:
                    safe = cls._variable_storage_task(mastery)
                elif mastery < 0.40:
                    safe = (
                        "Agora separe o nome do lugar e o valor que está dentro dele.\n\n"
                        + cls._variable_storage_task(mastery)
                    )
                elif mastery < 0.60:
                    safe = (
                        "Agora observe que o valor pode mudar enquanto o nome permanece.\n\n"
                        + cls._variable_storage_task(mastery)
                    )
                else:
                    safe = (
                        "Agora identifique juntos o nome que permanece e o valor atual.\n\n"
                        + cls._variable_storage_task(mastery)
                    )
            else:
                safe = (
                    "Agora uma novidade: pense em uma caixa com etiqueta. A etiqueta dá um nome "
                    "ao lugar e o conteúdo é o valor guardado. Em programação, uma variável "
                    "cumpre essa ideia: um lugar identificado por nome que mantém um valor. "
                    "Ainda não vamos escrever a forma completa disso.\n\n"
                    + cls._variable_storage_task(mastery)
                )
            safe = cls._prepend_feedback(safe, feedback)
            return cls(
                concept_id=concept_id,
                focus=focus,
                objective=(
                    "compreender variável como um lugar identificado por nome que guarda um valor, "
                    "distinguindo nome, conteúdo e valor atual"
                ),
                representation="analogia concreta e linguagem natural, sem sintaxe de declaração",
                forbidden_terms=cls.VARIABLE_STORAGE_FUTURE_FORBIDDEN,
                allow_code=False,
                max_chars=950,
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
