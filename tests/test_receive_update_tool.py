import importlib.util
from pathlib import Path


MODULE_PATH = Path("tools/apex_receive_update.py")
spec = importlib.util.spec_from_file_location("apex_receive_update", MODULE_PATH)
receiver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receiver)


def test_valid_sha256_accepts_lower_and_upper_hex():
    value = "a" * 64
    assert receiver.valid_sha256(value)
    assert receiver.valid_sha256(value.upper())


def test_valid_sha256_rejects_bad_values():
    assert not receiver.valid_sha256("abc")
    assert not receiver.valid_sha256("g" * 64)


def test_sha256_bytes_is_deterministic():
    assert receiver.sha256_bytes(b"APEX") == receiver.sha256_bytes(b"APEX")
    assert receiver.sha256_bytes(b"APEX") != receiver.sha256_bytes(b"apex")


def test_extract_upload_reads_multipart_file():
    boundary = "----apex-boundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="update.tar.gz"\r\n'
        "Content-Type: application/gzip\r\n\r\n"
    ).encode() + b"abc123" + f"\r\n--{boundary}--\r\n".encode()
    filename, data = receiver.extract_upload(
        f"multipart/form-data; boundary={boundary}",
        body,
    )
    assert filename == "update.tar.gz"
    assert data == b"abc123"
