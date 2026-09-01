from backend.prompts.tutor import TUTOR_SYSTEM_PROMPT


class TutorCore:
    """
    Monta o contexto enviado ao modelo.

    Responsabilidades atuais:
    - aplicar o prompt pedagógico do APEX;
    - informar a área de estudo atual;
    - filtrar o histórico recebido do navegador;
    - limitar o tamanho do contexto;
    - impedir injeção de mensagens "system"
      através do histórico do cliente.
    """

    ALLOWED_HISTORY_ROLES = {
        "user",
        "assistant",
    }

    MAX_HISTORY_MESSAGES = 8
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
    def build_system_message(cls, area):
        """
        Combina o prompt pedagógico principal
        com o contexto da área atual.
        """

        normalized_area = cls.normalize_area(area)

        area_context = cls.AREA_CONTEXT[
            normalized_area
        ]

        return (
            f"{TUTOR_SYSTEM_PROMPT}\n\n"
            "CONTEXTO DA SESSÃO ATUAL:\n"
            f"{area_context}\n\n"
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
    ):
        """
        Produz a lista final de mensagens
        enviada ao modelo.
        """

        messages = [
            {
                "role": "system",
                "content": cls.build_system_message(
                    area
                ),
            }
        ]

        if isinstance(history, list):

            for item in history[
                -cls.MAX_HISTORY_MESSAGES:
            ]:

                if not isinstance(item, dict):
                    continue

                role = item.get("role")
                content = item.get("content")

                if (
                    role
                    not in cls.ALLOWED_HISTORY_ROLES
                ):
                    continue

                if not isinstance(content, str):
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