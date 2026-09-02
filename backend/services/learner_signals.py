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
