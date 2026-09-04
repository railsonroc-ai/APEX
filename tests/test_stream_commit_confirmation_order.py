from pathlib import Path


def test_stream_commits_before_done_confirmation():
    source = Path(
        "backend/app.py"
    ).read_text()

    token_marker = '"token":'
    commit_marker = (
        "ProcessLearningTurn.commit_turn("
    )
    done_marker = '"done": True'

    assert source.count(commit_marker) == 1
    assert source.count(done_marker) == 2

    token_position = source.index(
        token_marker
    )
    commit_position = source.index(
        commit_marker
    )
    done_position = source.rindex(
        done_marker
    )

    assert (
        token_position
        < commit_position
        < done_position
    )
