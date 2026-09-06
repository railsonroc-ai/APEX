from dataclasses import dataclass
import hashlib
import re
import unicodedata


CATALOG_V1_VERSION = 1
CATALOG_V2_VERSION = 2
CATALOG_V3_VERSION = 3
CATALOG_V4_VERSION = 4
CATALOG_V5_VERSION = 5
CATALOG_V6_VERSION = 6
CATALOG_V7_VERSION = 7
CATALOG_V8_VERSION = 8
CATALOG_V9_VERSION = 9
CATALOG_V10_VERSION = 10
CATALOG_VERSION = 11


@dataclass(frozen=True)
class ConceptSeed:
    concept_id: str
    area: str
    canonical_name: str
    aliases: tuple[str, ...]
    selectable: bool = True


CORE_CONCEPT_SEEDS = (
    ConceptSeed(
        "ads.variables",
        "ads",
        "variáveis",
        (
            "variável",
            "variaveis",
            "variavel",
            "variables",
            "variable",
        ),
    ),
    ConceptSeed(
        "ads.functions",
        "ads",
        "funções",
        (
            "função",
            "funcoes",
            "funcao",
            "functions",
            "function",
        ),
    ),
    ConceptSeed(
        "ads.conditionals",
        "ads",
        "condicionais",
        (
            "condicional",
            "conditionals",
            "conditional",
            "if",
        ),
    ),
    ConceptSeed(
        "ads.lists",
        "ads",
        "listas",
        (
            "lista",
            "lists",
            "list",
        ),
    ),
    ConceptSeed(
        "ads.algorithms",
        "ads",
        "algoritmos",
        (
            "algoritmo",
            "algorithms",
            "algorithm",
            "lógica de programação",
            "logica de programacao",
            "lógica",
            "logica",
        ),
    ),
    ConceptSeed(
        "ads.data_types",
        "ads",
        "tipos de dados",
        (
            "tipo de dado",
            "tipos",
            "data types",
            "data type",
        ),
    ),
    ConceptSeed(
        "it.networks",
        "it",
        "redes",
        (
            "rede",
            "redes de computadores",
            "networking",
            "networks",
            "network",
        ),
    ),
    ConceptSeed(
        "it.operating_systems",
        "it",
        "sistemas operacionais",
        (
            "sistema operacional",
            "operating systems",
            "operating system",
            "os",
        ),
    ),
    ConceptSeed(
        "it.hardware",
        "it",
        "hardware",
        (),
    ),
    ConceptSeed(
        "it.information_security",
        "it",
        "segurança da informação",
        (
            "seguranca da informacao",
            "segurança",
            "seguranca",
            "information security",
            "security",
        ),
    ),
)


ORDERED_STEPS_SEED = ConceptSeed(
    "ads.algorithms.ordered_steps",
    "ads",
    "sequência ordenada de passos",
    (
        "sequencia ordenada de passos",
        "passos ordenados",
        "ordered steps",
    ),
    selectable=False,
)


GOAL_RESULT_SEED = ConceptSeed(
    "ads.algorithms.goal_result",
    "ads",
    "objetivo e resultado de uma sequência",
    (
        "objetivo de uma sequencia",
        "resultado de uma sequencia",
        "goal and result",
    ),
    selectable=False,
)


INPUT_PROCESS_OUTPUT_SEED = ConceptSeed(
    "ads.algorithms.input_process_output",
    "ads",
    "entrada, processamento e saída",
    (
        "entrada processamento saida",
        "entrada processamento e saida",
        "input process output",
        "input processing output",
    ),
    selectable=False,
)


STRUCTURED_SEQUENCE_SEED = ConceptSeed(
    "ads.algorithms.structured_sequence",
    "ads",
    "representação estruturada de uma sequência",
    (
        "representacao estruturada de uma sequencia",
        "sequencia estruturada",
        "passos estruturados",
        "structured sequence",
    ),
    selectable=False,
)


PORTUGOL_SKELETON_SEED = ConceptSeed(
    "ads.algorithms.portugol_skeleton",
    "ads",
    "estrutura mínima do Portugol",
    (
        "estrutura minima do portugol",
        "esqueleto do portugol",
        "estrutura basica do portugol",
        "portugol skeleton",
    ),
    selectable=False,
)


PORTUGOL_WRITE_SEED = ConceptSeed(
    "ads.algorithms.portugol_write",
    "ads",
    "saída simples com escreva",
    (
        "saida simples com escreva",
        "comando escreva",
        "escreva no portugol",
        "portugol write",
    ),
    selectable=False,
)


PORTUGOL_READ_SEED = ConceptSeed(
    "ads.algorithms.portugol_read",
    "ads",
    "entrada simples com leia",
    (
        "entrada simples com leia",
        "comando leia",
        "leia no portugol",
        "portugol read",
    ),
    selectable=False,
)


VARIABLE_STORAGE_SEED = ConceptSeed(
    "ads.algorithms.variable_storage",
    "ads",
    "variável como armazenamento nomeado",
    (
        "armazenamento nomeado de valor",
        "lugar nomeado para guardar valor",
        "named value storage",
    ),
    selectable=False,
)


INTEGER_DECLARATION_SEED = ConceptSeed(
    "ads.algorithms.integer_declaration",
    "ads",
    "declaração de variável inteira",
    (
        "declaracao de variavel inteira",
        "declaração inteira no portugol",
        "declaracao inteira no portugol",
        "integer variable declaration",
    ),
    selectable=False,
)


READ_VARIABLE_SEED = ConceptSeed(
    "ads.algorithms.read_variable",
    "ads",
    "entrada em variável com leia",
    (
        "entrada em variavel com leia",
        "leia com variavel",
        "leia variavel",
        "receber entrada em variavel",
        "read into variable",
    ),
    selectable=False,
)


CATALOG_V2_SEEDS = CORE_CONCEPT_SEEDS + (ORDERED_STEPS_SEED,)
CATALOG_V3_SEEDS = CORE_CONCEPT_SEEDS + (
    ORDERED_STEPS_SEED,
    GOAL_RESULT_SEED,
)
CATALOG_V4_SEEDS = CORE_CONCEPT_SEEDS + (
    ORDERED_STEPS_SEED,
    GOAL_RESULT_SEED,
    INPUT_PROCESS_OUTPUT_SEED,
)
CATALOG_V5_SEEDS = CORE_CONCEPT_SEEDS + (
    ORDERED_STEPS_SEED,
    GOAL_RESULT_SEED,
    INPUT_PROCESS_OUTPUT_SEED,
    STRUCTURED_SEQUENCE_SEED,
)
CATALOG_V6_SEEDS = CORE_CONCEPT_SEEDS + (
    ORDERED_STEPS_SEED,
    GOAL_RESULT_SEED,
    INPUT_PROCESS_OUTPUT_SEED,
    STRUCTURED_SEQUENCE_SEED,
    PORTUGOL_SKELETON_SEED,
)
CATALOG_V7_SEEDS = CORE_CONCEPT_SEEDS + (
    ORDERED_STEPS_SEED,
    GOAL_RESULT_SEED,
    INPUT_PROCESS_OUTPUT_SEED,
    STRUCTURED_SEQUENCE_SEED,
    PORTUGOL_SKELETON_SEED,
    PORTUGOL_WRITE_SEED,
)
CATALOG_V8_SEEDS = CORE_CONCEPT_SEEDS + (
    ORDERED_STEPS_SEED,
    GOAL_RESULT_SEED,
    INPUT_PROCESS_OUTPUT_SEED,
    STRUCTURED_SEQUENCE_SEED,
    PORTUGOL_SKELETON_SEED,
    PORTUGOL_WRITE_SEED,
    PORTUGOL_READ_SEED,
)
CATALOG_V9_SEEDS = CORE_CONCEPT_SEEDS + (
    ORDERED_STEPS_SEED,
    GOAL_RESULT_SEED,
    INPUT_PROCESS_OUTPUT_SEED,
    STRUCTURED_SEQUENCE_SEED,
    PORTUGOL_SKELETON_SEED,
    PORTUGOL_WRITE_SEED,
    PORTUGOL_READ_SEED,
    VARIABLE_STORAGE_SEED,
)
CATALOG_V10_SEEDS = CORE_CONCEPT_SEEDS + (
    ORDERED_STEPS_SEED,
    GOAL_RESULT_SEED,
    INPUT_PROCESS_OUTPUT_SEED,
    STRUCTURED_SEQUENCE_SEED,
    PORTUGOL_SKELETON_SEED,
    PORTUGOL_WRITE_SEED,
    PORTUGOL_READ_SEED,
    VARIABLE_STORAGE_SEED,
    INTEGER_DECLARATION_SEED,
)


MICRO_CONCEPT_SEEDS = (
    ORDERED_STEPS_SEED,
    GOAL_RESULT_SEED,
    INPUT_PROCESS_OUTPUT_SEED,
    STRUCTURED_SEQUENCE_SEED,
    PORTUGOL_SKELETON_SEED,
    PORTUGOL_WRITE_SEED,
    PORTUGOL_READ_SEED,
    VARIABLE_STORAGE_SEED,
    INTEGER_DECLARATION_SEED,
    READ_VARIABLE_SEED,
)

CONCEPT_SEEDS = CORE_CONCEPT_SEEDS + MICRO_CONCEPT_SEEDS


_SEED_BY_ID = {
    seed.concept_id: seed
    for seed in CONCEPT_SEEDS
}


def normalize_area(area):
    normalized = str(area or "ads").strip().lower()
    return normalized if normalized in {"ads", "it"} else "ads"


def normalize_alias(value):
    if not isinstance(value, str):
        return None

    normalized = unicodedata.normalize("NFKD", value.casefold())
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = " ".join(normalized.split())
    return normalized or None


def seed_by_id(concept_id):
    if not isinstance(concept_id, str):
        return None
    return _SEED_BY_ID.get(concept_id.strip())


def seed_for_value(area, value):
    normalized_area = normalize_area(area)

    if isinstance(value, str):
        direct = seed_by_id(value)
        if direct is not None and direct.area == normalized_area:
            return direct

    normalized_value = normalize_alias(value)
    if not normalized_value:
        return None

    for seed in CONCEPT_SEEDS:
        if seed.area != normalized_area:
            continue

        aliases = (
            seed.canonical_name,
            *seed.aliases,
        )
        if normalized_value in {
            normalize_alias(alias)
            for alias in aliases
        }:
            return seed

    return None


def legacy_concept_id(area, value):
    normalized_area = normalize_area(area)
    normalized_value = normalize_alias(value) or "unknown"
    digest = hashlib.sha256(
        f"{normalized_area}\0{normalized_value}".encode("utf-8")
    ).hexdigest()[:16]
    return f"legacy.{normalized_area}.{digest}"


def legacy_canonical_name(concept_id):
    suffix = str(concept_id).rsplit(".", 1)[-1][:8]
    return f"Conceito legado {suffix}"
