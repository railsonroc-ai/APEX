class Curriculum:
    """Percurso mínimo executável; cresce por fatias testadas, não por prompt."""

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

    ENTRY_CONCEPTS = {
        "ads.algorithms": ORDERED_STEPS,
    }

    NEXT_CONCEPTS = {
        ORDERED_STEPS: GOAL_RESULT,
        GOAL_RESULT: INPUT_PROCESS_OUTPUT,
        INPUT_PROCESS_OUTPUT: STRUCTURED_SEQUENCE,
        STRUCTURED_SEQUENCE: PORTUGOL_SKELETON,
        PORTUGOL_SKELETON: PORTUGOL_WRITE,
        PORTUGOL_WRITE: PORTUGOL_READ,
        PORTUGOL_READ: VARIABLE_STORAGE,
        VARIABLE_STORAGE: INTEGER_DECLARATION,
        INTEGER_DECLARATION: READ_VARIABLE,
    }

    PREREQUISITES = {
        ORDERED_STEPS: (),
        GOAL_RESULT: (ORDERED_STEPS,),
        INPUT_PROCESS_OUTPUT: (GOAL_RESULT,),
        STRUCTURED_SEQUENCE: (INPUT_PROCESS_OUTPUT,),
        PORTUGOL_SKELETON: (STRUCTURED_SEQUENCE,),
        PORTUGOL_WRITE: (PORTUGOL_SKELETON,),
        PORTUGOL_READ: (PORTUGOL_WRITE,),
        VARIABLE_STORAGE: (PORTUGOL_READ,),
        INTEGER_DECLARATION: (VARIABLE_STORAGE,),
        READ_VARIABLE: (INTEGER_DECLARATION,),
    }

    @classmethod
    def entry_concept_id(cls, concept_id):
        if not isinstance(concept_id, str):
            return concept_id
        normalized = concept_id.strip()
        return cls.ENTRY_CONCEPTS.get(normalized, normalized)

    @classmethod
    def next_concept_id(cls, concept_id):
        if not isinstance(concept_id, str):
            return None
        return cls.NEXT_CONCEPTS.get(concept_id.strip())

    @classmethod
    def prerequisites_for(cls, concept_id):
        if not isinstance(concept_id, str):
            return ()
        return cls.PREREQUISITES.get(concept_id.strip(), ())

    @classmethod
    def allows_progression(cls, completed_concept_id, target_concept_id):
        return (
            isinstance(completed_concept_id, str)
            and isinstance(target_concept_id, str)
            and cls.next_concept_id(completed_concept_id)
            == target_concept_id.strip()
            and completed_concept_id.strip()
            in cls.prerequisites_for(target_concept_id)
        )
