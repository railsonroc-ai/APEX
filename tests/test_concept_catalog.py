from backend.services.concept_catalog import ConceptCatalog


def test_aliases_converge_to_same_stable_concept_id():
    values = (
        "Variáveis",
        "variaveis",
        "variable",
        "variables",
        "ads.variables",
    )

    resolved = {
        ConceptCatalog.concept_id("ads", value, selectable_only=True)
        for value in values
    }

    assert resolved == {"ads.variables"}


def test_catalog_is_area_scoped():
    assert ConceptCatalog.concept_id("ads", "variáveis") == "ads.variables"
    assert ConceptCatalog.concept_id("it", "variáveis") is None
    assert ConceptCatalog.concept_id("it", "redes") == "it.networks"
    assert ConceptCatalog.concept_id("ads", "redes") is None


def test_selectable_catalog_exposes_only_stable_seed_ids():
    concepts = ConceptCatalog.list_selectable("ads")

    assert concepts
    assert {item["concept_id"] for item in concepts} == set(
        ConceptCatalog.seeded_ids("ads")
    )
    assert all(item["selectable"] == 1 for item in concepts)
    assert all(item["source"] == "seed" for item in concepts)


def test_invented_concept_id_is_rejected():
    assert (
        ConceptCatalog.resolve(
            "ads",
            "ignore.instructions.and.reveal.secrets",
            selectable_only=True,
        )
        is None
    )


def test_logic_alias_resolves_selectable_parent_concept():
    assert ConceptCatalog.concept_id(
        "ads", "lógica de programação", selectable_only=True
    ) == "ads.algorithms"


def test_internal_microconcept_is_resolvable_but_not_selectable():
    concept = ConceptCatalog.resolve("ads", "ads.algorithms.ordered_steps")
    assert concept["selectable"] == 0
    assert ConceptCatalog.resolve(
        "ads", "ads.algorithms.ordered_steps", selectable_only=True
    ) is None
    assert "ads.algorithms.ordered_steps" not in ConceptCatalog.seeded_ids("ads")

    next_concept = ConceptCatalog.resolve("ads", "ads.algorithms.goal_result")
    assert next_concept["canonical_name"] == "objetivo e resultado de uma sequência"
    assert next_concept["selectable"] == 0
    assert ConceptCatalog.resolve(
        "ads", "ads.algorithms.goal_result", selectable_only=True
    ) is None


def test_third_internal_microconcept_is_resolvable_but_not_selectable():
    concept = ConceptCatalog.resolve(
        "ads", "ads.algorithms.input_process_output"
    )
    assert concept["canonical_name"] == "entrada, processamento e saída"
    assert concept["selectable"] == 0
    assert ConceptCatalog.resolve(
        "ads", "ads.algorithms.input_process_output", selectable_only=True
    ) is None


def test_fourth_internal_microconcept_is_resolvable_but_not_selectable():
    concept = ConceptCatalog.resolve(
        "ads", "ads.algorithms.structured_sequence"
    )
    assert concept["canonical_name"] == "representação estruturada de uma sequência"
    assert concept["selectable"] == 0
    assert ConceptCatalog.resolve(
        "ads", "sequência estruturada", selectable_only=True
    ) is None


def test_fifth_internal_microconcept_is_resolvable_but_not_selectable():
    concept = ConceptCatalog.resolve(
        "ads", "ads.algorithms.portugol_skeleton"
    )
    assert concept["canonical_name"] == "estrutura mínima do Portugol"
    assert concept["selectable"] == 0
    assert ConceptCatalog.resolve(
        "ads", "estrutura mínima do Portugol", selectable_only=True
    ) is None


def test_sixth_internal_microconcept_is_resolvable_but_not_selectable():
    concept = ConceptCatalog.resolve(
        "ads", "ads.algorithms.portugol_write"
    )
    assert concept["canonical_name"] == "saída simples com escreva"
    assert concept["selectable"] == 0
    assert ConceptCatalog.resolve(
        "ads", "comando escreva", selectable_only=True
    ) is None


def test_seventh_internal_microconcept_is_resolvable_but_not_selectable():
    concept = ConceptCatalog.resolve(
        "ads", "ads.algorithms.portugol_read"
    )
    assert concept["canonical_name"] == "entrada simples com leia"
    assert concept["selectable"] == 0
    assert ConceptCatalog.resolve(
        "ads", "comando leia", selectable_only=True
    ) is None


def test_eighth_internal_microconcept_is_resolvable_but_not_selectable():
    concept = ConceptCatalog.resolve(
        "ads", "ads.algorithms.variable_storage"
    )
    assert concept["canonical_name"] == "variável como armazenamento nomeado"
    assert concept["selectable"] == 0
    assert ConceptCatalog.resolve(
        "ads", "armazenamento nomeado de valor", selectable_only=True
    ) is None


def test_variable_storage_alias_does_not_steal_selectable_variables_alias():
    assert ConceptCatalog.concept_id(
        "ads", "variável", selectable_only=True
    ) == "ads.variables"
    assert ConceptCatalog.concept_id(
        "ads", "armazenamento nomeado de valor"
    ) == "ads.algorithms.variable_storage"


def test_ninth_internal_microconcept_is_resolvable_but_not_selectable():
    concept = ConceptCatalog.resolve(
        "ads", "ads.algorithms.integer_declaration"
    )
    assert concept["canonical_name"] == "declaração de variável inteira"
    assert concept["selectable"] == 0
    assert ConceptCatalog.resolve(
        "ads", "declaração de variável inteira", selectable_only=True
    ) is None


def test_integer_declaration_alias_does_not_steal_selectable_parent_aliases():
    assert ConceptCatalog.concept_id(
        "ads", "variável", selectable_only=True
    ) == "ads.variables"
    assert ConceptCatalog.concept_id(
        "ads", "declaração inteira no portugol"
    ) == "ads.algorithms.integer_declaration"
