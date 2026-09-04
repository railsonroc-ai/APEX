import re
from pathlib import Path


RENDER_FILE = Path("render.yaml")


def test_render_persists_sqlite_data_directory():
    source = RENDER_FILE.read_text()

    assert "disk:" in source

    assert (
        "mountPath: /opt/render/project/src/data"
        in source
    )

    assert re.search(
        r"sizeGB:\s*[1-9]\d*",
        source,
    )

    assert re.search(
        r"numInstances:\s*1",
        source,
    )


def test_sqlite_data_dir_matches_persistent_disk():
    source = RENDER_FILE.read_text()

    mount_match = re.search(
        r"mountPath:\s*(\S+)",
        source,
    )

    data_dir_match = re.search(
        r"- key:\s*APEX_DATA_DIR"
        r"\s+value:\s*(\S+)",
        source,
    )

    assert mount_match is not None
    assert data_dir_match is not None

    mount_path = mount_match.group(1)
    data_dir = data_dir_match.group(1)

    assert (
        mount_path
        == data_dir
        == "/opt/render/project/src/data"
    )


def test_render_keeps_required_production_secrets():
    source = RENDER_FILE.read_text()

    for key in (
        "GROQ_API_KEY",
        "SECRET_KEY",
    ):
        assert re.search(
            rf"- key:\s*{key}"
            rf"\s+sync:\s*false",
            source,
        )
