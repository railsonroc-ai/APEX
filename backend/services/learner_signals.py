import re


class LearnerSignals:
    DIFFICULTY = "difficulty"
    TEST_REQUEST = "test_request"
    REVIEW_REQUEST = "review_request"
    REEXPLAIN_REQUEST = "reexplain_request"

    @staticmethod
    def normalize_message(message):
        if not isinstance(message, str):
            return ""
        return " ".join(message.strip().lower().split())

    DIFFICULTY_PHRASES = (
        "estou perdido",
        "não entendi",
        "nao entendi",
        "não estou entendendo",
        "nao estou entendendo",
        "fiquei confuso",
        "não consegui entender",
        "nao consegui entender",
    )

    TEST_REQUEST_PHRASES = (
        "me testa",
        "me teste",
        "quero ser testado",
        "quero fazer um teste",
        "pode me testar",
    )

    REVIEW_REQUEST_PHRASES = (
        "quero revisar",
        "vamos revisar",
        "pode revisar",
        "revisar antes",
        "quero uma revisão",
        "quero uma revisao",
    )

    REEXPLAIN_REQUEST_PHRASES = (
        "explique diferente",
        "explica diferente",
        "explique de outro jeito",
        "explica de outro jeito",
        "me explica de outra forma",
        "me explique de outra forma",
    )

    CONTROL_FILLERS = {
        "agora", "ainda", "mesmo", "por", "favor", "mas", "so", "só",
        "realmente", "entao", "então", "ok", "ta", "tá",
    }

    @classmethod
    def detect(cls, message):
        text = cls.normalize_message(message)
        if not text:
            return set()
        signals = set()
        if any(p in text for p in cls.DIFFICULTY_PHRASES):
            signals.add(cls.DIFFICULTY)
        if any(p in text for p in cls.TEST_REQUEST_PHRASES):
            signals.add(cls.TEST_REQUEST)
        if any(p in text for p in cls.REVIEW_REQUEST_PHRASES):
            signals.add(cls.REVIEW_REQUEST)
        if any(p in text for p in cls.REEXPLAIN_REQUEST_PHRASES):
            signals.add(cls.REEXPLAIN_REQUEST)
        return signals

    @classmethod
    def is_control_only(cls, message):
        """Diferencia um comando puro de uma resposta que também contém comando.

        ``não entendi`` isolado controla o tutor e não é evidência. Já
        ``abrir, lavar, secar; mas não entendi por quê`` preserva a produção do
        aluno para avaliação e trata a dificuldade separadamente.
        """
        text = cls.normalize_message(message)
        detected = cls.detect(text)
        if not detected:
            return False

        phrases = ()
        if cls.DIFFICULTY in detected:
            phrases += cls.DIFFICULTY_PHRASES
        if cls.TEST_REQUEST in detected:
            phrases += cls.TEST_REQUEST_PHRASES
        if cls.REVIEW_REQUEST in detected:
            phrases += cls.REVIEW_REQUEST_PHRASES
        if cls.REEXPLAIN_REQUEST in detected:
            phrases += cls.REEXPLAIN_REQUEST_PHRASES

        remainder = text
        for phrase in sorted(phrases, key=len, reverse=True):
            remainder = remainder.replace(phrase, " ")
        tokens = re.findall(r"[a-zà-ÿ0-9]+", remainder)
        meaningful = [token for token in tokens if token not in cls.CONTROL_FILLERS]
        return not meaningful
