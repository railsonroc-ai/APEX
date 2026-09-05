import re


class TaskSpec:
    """Extrai a única tarefa que foi realmente exibida ao aluno."""

    TASK_PATTERN = re.compile(
        r"(?ims)^\s*(?:tarefa|desafio|sua vez)\s*:\s*(.+?)(?=\n\s*\n|\Z)"
    )

    @classmethod
    def extract(cls, response):
        if not isinstance(response, str):
            return None
        matches = [" ".join(match.split()) for match in cls.TASK_PATTERN.findall(response)]
        matches = [match for match in matches if match]
        return matches[0] if len(matches) == 1 else None

    @classmethod
    def count(cls, response):
        if not isinstance(response, str):
            return 0
        return len(cls.TASK_PATTERN.findall(response))
