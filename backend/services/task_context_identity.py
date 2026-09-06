from backend.concepts import normalize_alias
from backend.services.goal_result_tasks import GoalResultTasks
from backend.services.input_process_output_tasks import InputProcessOutputTasks
from backend.services.structured_sequence_tasks import StructuredSequenceTasks
from backend.services.portugol_skeleton_tasks import PortugolSkeletonTasks
from backend.services.portugol_write_tasks import PortugolWriteTasks
from backend.services.portugol_read_tasks import PortugolReadTasks
from backend.services.variable_storage_tasks import VariableStorageTasks
from backend.services.integer_declaration_tasks import IntegerDeclarationTasks
from backend.services.read_variable_tasks import ReadVariableTasks


class TaskContextIdentity:
    """Resolve a identidade semântica estável da atividade avaliada.

    `learning_tasks.task_id` identifica uma emissão concreta e é aleatório. Para
    domínio, precisamos saber se duas evidências vieram de atividades realmente
    diferentes. Conceitos controlados são resolvidos para IDs canônicos de tarefa.
    """

    ORDERED_STEPS = "ads.algorithms.ordered_steps"
    GOAL_RESULT = "ads.algorithms.goal_result"
    INPUT_PROCESS_OUTPUT = "ads.algorithms.input_process_output"
    STRUCTURED_SEQUENCE = "ads.algorithms.structured_sequence"
    PORTUGOL_SKELETON = "ads.algorithms.portugol_skeleton"
    PORTUGOL_WRITE = "ads.algorithms.portugol_write"
    PORTUGOL_READ = "ads.algorithms.portugol_read"
    VARIABLE_STORAGE = "ads.algorithms.variable_storage"
    INTEGER_DECLARATION = "ads.algorithms.integer_declaration"
    READ_VARIABLE = "ads.algorithms.read_variable"

    CONTROLLED_CONCEPTS = {
        ORDERED_STEPS,
        GOAL_RESULT,
        INPUT_PROCESS_OUTPUT,
        STRUCTURED_SEQUENCE,
        PORTUGOL_SKELETON,
        PORTUGOL_WRITE,
        PORTUGOL_READ,
        VARIABLE_STORAGE,
        INTEGER_DECLARATION,
        READ_VARIABLE,
    }

    ORDERED_CONTEXTS = (
        (
            "ordered_hand_washing",
            ("secar as maos", "abrir a torneira", "lavar as maos"),
        ),
        (
            "ordered_save_file",
            ("guardar um arquivo", "tres passos"),
        ),
        (
            "ordered_send_message",
            ("clicar em enviar", "escrever a mensagem", "abrir a conversa"),
        ),
        (
            "ordered_drink_water",
            ("guardar o copo", "pegar o copo", "beber a agua"),
        ),
    )

    @classmethod
    def requires_explicit_context(cls, concept_id):
        return concept_id in cls.CONTROLLED_CONCEPTS

    @classmethod
    def for_prompt(cls, concept_id, prompt):
        normalized = normalize_alias(prompt) or ""
        if not normalized or not isinstance(concept_id, str):
            return None

        if concept_id == cls.GOAL_RESULT:
            definition = GoalResultTasks.definition_for_prompt(prompt)
            return definition.get("task_id") if definition else None

        if concept_id == cls.INPUT_PROCESS_OUTPUT:
            definition = InputProcessOutputTasks.definition_for_prompt(prompt)
            return definition.get("task_id") if definition else None

        if concept_id == cls.STRUCTURED_SEQUENCE:
            definition = StructuredSequenceTasks.definition_for_prompt(prompt)
            return definition.get("task_id") if definition else None

        if concept_id == cls.PORTUGOL_SKELETON:
            definition = PortugolSkeletonTasks.definition_for_prompt(prompt)
            return definition.get("task_id") if definition else None

        if concept_id == cls.PORTUGOL_WRITE:
            definition = PortugolWriteTasks.definition_for_prompt(prompt)
            return definition.get("task_id") if definition else None

        if concept_id == cls.PORTUGOL_READ:
            definition = PortugolReadTasks.definition_for_prompt(prompt)
            return definition.get("task_id") if definition else None

        if concept_id == cls.VARIABLE_STORAGE:
            definition = VariableStorageTasks.definition_for_prompt(prompt)
            return definition.get("task_id") if definition else None

        if concept_id == cls.INTEGER_DECLARATION:
            definition = IntegerDeclarationTasks.definition_for_prompt(prompt)
            return definition.get("task_id") if definition else None

        if concept_id == cls.READ_VARIABLE:
            definition = ReadVariableTasks.definition_for_prompt(prompt)
            return definition.get("task_id") if definition else None

        if concept_id == cls.ORDERED_STEPS:
            for context_id, markers in cls.ORDERED_CONTEXTS:
                if all(marker in normalized for marker in markers):
                    return context_id

        return None

    @classmethod
    def for_evidence_event(cls, event):
        if not isinstance(event, dict):
            return None
        return cls.for_prompt(
            event.get("concept_id"),
            event.get("tutor_message"),
        )
