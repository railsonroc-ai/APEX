from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (ROOT / "docs" / "PEDAGOGICAL_CONTRACT.md").read_text()


def test_all_kernel_requirements_remain_registered():
    for number in range(1, 17):
        assert f"PED-{number:03d}" in CONTRACT


def test_long_term_directives_remain_visible_without_false_enforcement_claims():
    for number in range(1, 10):
        assert f"ROAD-{number:03d}" in CONTRACT
    assert "regra escrita apenas no prompt não conta como implementada" in CONTRACT
    assert "Revisões vencidas reaparecem" in CONTRACT
    assert "Inglês técnico progressivo" in CONTRACT
