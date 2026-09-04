import io
import tarfile

import pytest

from tools import apex_apply_update


pytestmark = pytest.mark.reliability


def _archive_bytes(files):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in files.items():
            payload = content.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    buffer.seek(0)
    return buffer


def _canonical_manifest(*, migration="NAO", files=("README.md",)):
    listed = "\n".join(f"- {name}" for name in files)
    return (
        "APEX Update Contract\n"
        "Base commit esperado: abc1234\n"
        f"Migration nova: {migration}\n"
        f"Arquivos de projeto: {len(files)}\n\n"
        "Arquivos:\n"
        f"{listed}\n"
    )


def test_manifest_declares_no_migration_and_exact_files():
    buffer = _archive_bytes(
        {
            "README.md": "ok\n",
            apex_apply_update.MANIFEST_NAME: _canonical_manifest(),
        }
    )
    with tarfile.open(fileobj=buffer, mode="r:gz") as archive:
        members = apex_apply_update.safe_members(archive)
        result = apex_apply_update.validate_update_manifest(archive, members)

    assert result["requires_migration"] is False
    assert result["files"] == ("README.md",)


def test_manifest_declares_migration_when_version_is_present():
    text = _canonical_manifest(
        migration="15 create_release_hardening",
    )
    assert apex_apply_update.manifest_requires_migration(text) is True


def test_package_rejects_noncanonical_manifest_file():
    buffer = _archive_bytes(
        {
            "README.md": "ok\n",
            "APEX_OTHER_MANIFEST.txt": "nao deveria estar aqui\n",
            apex_apply_update.MANIFEST_NAME: _canonical_manifest(),
        }
    )
    with tarfile.open(fileobj=buffer, mode="r:gz") as archive:
        members = apex_apply_update.safe_members(archive)
        with pytest.raises(RuntimeError, match="manifesto fora do nome canonico"):
            apex_apply_update.validate_update_manifest(archive, members)


def test_package_rejects_file_not_declared_in_manifest():
    buffer = _archive_bytes(
        {
            "README.md": "ok\n",
            "unexpected.txt": "extra\n",
            apex_apply_update.MANIFEST_NAME: _canonical_manifest(),
        }
    )
    with tarfile.open(fileobj=buffer, mode="r:gz") as archive:
        members = apex_apply_update.safe_members(archive)
        with pytest.raises(RuntimeError, match="diverge do manifesto"):
            apex_apply_update.validate_update_manifest(archive, members)


def test_package_rejects_missing_canonical_manifest():
    buffer = _archive_bytes({"README.md": "ok\n"})
    with tarfile.open(fileobj=buffer, mode="r:gz") as archive:
        members = apex_apply_update.safe_members(archive)
        with pytest.raises(RuntimeError, match="sem manifesto canonico"):
            apex_apply_update.validate_update_manifest(archive, members)
