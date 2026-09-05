from pathlib import Path


def test_stream_validates_and_commits_before_token_delivery():
    source = Path(
        "backend/app.py"
    ).read_text()

    validation_marker = "TutorResponseValidator.validate_or_fallback("
    token_marker = 'yield sse({"token": chunk})'
    commit_marker = (
        "ProcessLearningTurn.commit_turn("
    )
    done_marker = '"done": True'

    assert source.count(commit_marker) == 1
    assert source.count(done_marker) >= 2

    validation_position = source.index(validation_marker)
    token_position = source.index(token_marker)
    commit_position = source.index(
        commit_marker
    )
    done_position = source.rindex(
        done_marker
    )

    assert (
        validation_position
        < commit_position
        < token_position
        < done_position
    )


def test_stream_forwards_authoritative_evidence_context_to_commit():
    source = Path("backend/app.py").read_text()

    assert "evidence_context=evidence_evaluation" in source
