from backend.services.evidence_policy import EvidencePolicy


class AssistancePolicy:
    """Classifica a assistência a partir de decisões controladas pelo servidor.

    O modelo não escolhe nem declara o próprio nível de ajuda. O nível nasce do
    ``teaching_action`` calculado pelo kernel e é persistido para que a próxima
    resposta do aluno possa ser julgada com o contexto de suporte correto.
    """

    POLICY_ID = "server_teaching_assistance"
    POLICY_VERSION = 1

    ACTION_TO_LEVEL = {
        "testar": "independent",
        "revisar": "independent",
        "verificar": "light",
        "consolidar": "light",
        "explicar": "guided",
        "corrigir": "direct",
        "avancar": EvidencePolicy.ASSISTANCE_UNTRACKED,
    }

    CONTRACTS = {
        "independent": (
            "Faça recuperação/aplicação ativa sem fornecer a resposta antes "
            "da tentativa. Faça uma pergunta objetiva e deixe o aluno produzir "
            "a evidência com autonomia."
        ),
        "light": (
            "Pode oferecer uma pista curta, restrição ou lembrete de contexto, "
            "mas não entregue a solução completa antes da tentativa do aluno."
        ),
        "guided": (
            "Ensine com orientação estruturada e um exemplo curto quando útil. "
            "Depois peça ao aluno uma pequena produção própria para verificar "
            "compreensão."
        ),
        "direct": (
            "Corrija explicitamente o erro e mostre o raciocínio/solução "
            "necessária. Depois peça uma nova tentativa pequena e diferente."
        ),
        EvidencePolicy.ASSISTANCE_UNTRACKED: (
            "Não há nível de assistência pedagógica mensurável para esta ação."
        ),
    }

    @classmethod
    def normalize_teaching_action(cls, value):
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        return normalized if normalized in cls.ACTION_TO_LEVEL else None

    @classmethod
    def level_for_action(cls, teaching_action):
        normalized = cls.normalize_teaching_action(teaching_action)
        if normalized is None:
            return EvidencePolicy.ASSISTANCE_UNTRACKED
        return cls.ACTION_TO_LEVEL[normalized]

    @classmethod
    def contract_for_action(cls, teaching_action):
        level = cls.level_for_action(teaching_action)
        return {
            "policy_id": cls.POLICY_ID,
            "policy_version": cls.POLICY_VERSION,
            "teaching_action": cls.normalize_teaching_action(teaching_action),
            "assistance_level": level,
            "instruction": cls.CONTRACTS[level],
        }
