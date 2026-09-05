from backend.config import (
    MAX_HISTORY_MESSAGES as CONFIG_MAX_HISTORY_MESSAGES,
)
from backend.prompts.tutor import TUTOR_SYSTEM_PROMPT
from backend.services.concept_catalog import ConceptCatalog
from backend.services.assistance_policy import AssistancePolicy
from backend.services.task_policy import TaskPolicy
from backend.services.turn_teaching_contract import TurnTeachingContract


class TutorCore:
    """
    Monta o contexto enviado ao modelo.

    Responsabilidades atuais:
    - aplicar o prompt pedagógico do APEX;
    - informar a área de estudo atual;
    - filtrar o histórico confirmado pelo servidor;
    - limitar o tamanho do contexto;
    - aceitar somente papéis válidos no histórico.
    """

    ALLOWED_HISTORY_ROLES = {
        "user",
        "assistant",
    }

    # Mantém o limite centralizado em backend.config,
    # mas preserva o atributo público usado pelos testes
    # e por possíveis consumidores do TutorCore.
    MAX_HISTORY_MESSAGES = (
        CONFIG_MAX_HISTORY_MESSAGES
    )

    MAX_HISTORY_CONTENT_CHARS = 4000

    AREA_CONTEXT = {
        "ads": (
            "Análise e Desenvolvimento de Sistemas (ADS). "
            "Priorize programação, lógica, algoritmos, "
            "engenharia de software, bancos de dados e "
            "demais assuntos relacionados ao curso."
        ),
        "it": (
            "Tecnologia da Informação (TI). "
            "Priorize fundamentos e práticas relacionadas "
            "à tecnologia da informação."
        ),
    }

    @classmethod
    def normalize_area(cls, area):
        """
        Aceita somente áreas conhecidas.

        Caso o valor seja inválido ou ausente,
        utiliza ADS como padrão.
        """

        if not isinstance(area, str):
            return "ads"

        normalized = area.strip().lower()

        if normalized not in cls.AREA_CONTEXT:
            return "ads"

        return normalized

    @classmethod
    def build_system_message(
        cls,
        area,
        learner_state=None,
        teaching_action=None,
        teaching_contract=None,
    ):
        """
        Combina o prompt pedagógico principal
        com o contexto da área atual.
        """

        normalized_area = cls.normalize_area(
            area
        )

        area_context = cls.AREA_CONTEXT[
            normalized_area
        ]

        pedagogical_context = ""
        if isinstance(learner_state, dict):
            concept_value = (
                learner_state.get("current_concept_id")
                or learner_state.get("current_concept")
            )
            concept = ConceptCatalog.canonical_name(
                normalized_area,
                concept_value,
            )
            pedagogical_context = (
                "ESTADO PEDAGÓGICO ATUAL:\n"
                f"Conceito: {concept or 'não definido'}\n"
                f"Etapa: {learner_state.get('stage', 'compreender')}\n"
                f"Domínio: {learner_state.get('mastery', 0.0)}\n"
                f"Dificuldades: {learner_state.get('difficulty_count', 0)}\n"
            )

        if teaching_action:
            pedagogical_context += f"Ação pedagógica prioritária: {teaching_action}.\n"
            assistance_contract = AssistancePolicy.contract_for_action(
                teaching_action
            )
            pedagogical_context += (
                "Nível de assistência controlado pelo servidor: "
                f"{assistance_contract['assistance_level']}.\n"
                "Contrato de assistência: "
                f"{assistance_contract['instruction']}\n"
                "Não aumente o nível de ajuda além deste contrato e não "
                "declare outro nível de assistência.\n"
            )
            task_contract = TaskPolicy.contract_for_action(teaching_action)
            if task_contract["assessable"]:
                pedagogical_context += (
                    "Contrato de tarefa avaliável controlado pelo servidor: "
                    f"{task_contract['instruction']}\n"
                    "A tarefa deve avaliar somente o conceito ativo e não deve "
                    "empilhar múltiplas novidades ou múltiplas perguntas.\n"
                )

        if teaching_contract is None and isinstance(learner_state, dict):
            teaching_contract = TurnTeachingContract.build(
                learner_state,
                teaching_action,
            )
        if isinstance(teaching_contract, TurnTeachingContract):
            pedagogical_context += f"\n{teaching_contract.as_prompt()}\n"

        return (
            f"{TUTOR_SYSTEM_PROMPT}\n\n"
            "CONTEXTO DA SESSÃO ATUAL:\n"
            f"{area_context}\n\n"
            f"{pedagogical_context}\n"
            "Use a área apenas como contexto temático. "
            "Se o aluno fizer uma pergunta legítima fora "
            "dessa área, responda normalmente sem inventar "
            "uma mudança de matéria."
        )

    @classmethod
    def build_messages(
        cls,
        user_message,
        history=None,
        area="ads",
        learner_state=None,
        teaching_action=None,
        teaching_contract=None,
    ):
        """
        Produz a lista final de mensagens
        enviada ao modelo.
        """

        messages = [
            {
                "role": "system",
                "content": cls.build_system_message(
                    area,
                    learner_state=learner_state,
                    teaching_action=teaching_action,
                    teaching_contract=teaching_contract,
                ),
            }
        ]

        if isinstance(history, list):

            for item in history[
                -cls.MAX_HISTORY_MESSAGES:
            ]:

                if not isinstance(item, dict):
                    continue

                role = item.get(
                    "role"
                )

                content = item.get(
                    "content"
                )

                if (
                    role
                    not in cls.ALLOWED_HISTORY_ROLES
                ):
                    continue

                if not isinstance(
                    content,
                    str,
                ):
                    continue

                content = content.strip()

                if not content:
                    continue

                content = content[
                    :cls.MAX_HISTORY_CONTENT_CHARS
                ]

                messages.append(
                    {
                        "role": role,
                        "content": content,
                    }
                )

        current_message = str(
            user_message
        ).strip()

        messages.append(
            {
                "role": "user",
                "content": current_message,
            }
        )

        return messages
