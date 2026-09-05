class Curriculum:
    """Percurso mínimo executável; cresce por fatias testadas, não por prompt."""

    ENTRY_CONCEPTS = {
        "ads.algorithms": "ads.algorithms.ordered_steps",
    }

    @classmethod
    def entry_concept_id(cls, concept_id):
        if not isinstance(concept_id, str):
            return concept_id
        normalized = concept_id.strip()
        return cls.ENTRY_CONCEPTS.get(normalized, normalized)
