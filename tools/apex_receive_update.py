#!/usr/bin/env python3
"""Recebe um pacote APEX pelo navegador, valida SHA-256 e grava atomicamente.

Uso:
    python3 tools/apex_receive_update.py /public/PACOTE.tar.gz SHA256

Depois abra a URL exibida, selecione o arquivo e envie. O servidor encerra
sozinho após uma transferência válida.
"""

from __future__ import annotations

import argparse
from email.parser import BytesParser
from email.policy import default
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
import threading


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def valid_sha256(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    return len(normalized) == 64 and all(ch in "0123456789abcdef" for ch in normalized)


def extract_upload(content_type: str, body: bytes) -> tuple[str, bytes]:
    message = BytesParser(policy=default).parsebytes(
        (
            "Content-Type: "
            + content_type
            + "\r\nMIME-Version: 1.0\r\n\r\n"
        ).encode("utf-8")
        + body
    )
    for part in message.iter_parts():
        filename = part.get_filename()
        if filename:
            return filename, part.get_payload(decode=True) or b""
    raise ValueError("nenhum arquivo recebido")


def build_server(target: Path, expected_sha: str, host: str, port: int):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def respond(self, text: str, status: int = 200):
            body = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.respond(
                "<h2>APEX — Receber atualização</h2>"
                f"<p>Destino: {target.name}</p>"
                "<form method='post' enctype='multipart/form-data'>"
                "<input type='file' name='file' required>"
                "<button>TRANSFERIR</button>"
                "</form>"
            )

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length") or "0")
                if length <= 0:
                    raise ValueError("upload vazio")
                body = self.rfile.read(length)
                filename, data = extract_upload(
                    self.headers.get("Content-Type") or "",
                    body,
                )
                actual = sha256_bytes(data)
                if actual != expected_sha:
                    self.respond(
                        "<h2>SHA-256 INCORRETO</h2>"
                        f"<p>Arquivo: {filename}</p>"
                        f"<pre>{actual}</pre>",
                        400,
                    )
                    print("TRANSFERÊNCIA: FALHA — SHA-256 divergente", flush=True)
                    print("SHA-256 recebido:", actual, flush=True)
                    return

                target.parent.mkdir(parents=True, exist_ok=True)
                temp = target.with_name(target.name + ".part")
                temp.write_bytes(data)
                os.replace(temp, target)

                self.respond(
                    "<h2>TRANSFERÊNCIA CONCLUÍDA</h2>"
                    f"<p>{target}</p>"
                )
                print("TRANSFERÊNCIA: OK", flush=True)
                print("ARQUIVO:", target, flush=True)
                print("SHA-256:", actual, flush=True)
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            except Exception as exc:
                self.respond(f"<h2>ERRO</h2><pre>{type(exc).__name__}: {exc}</pre>", 400)
                print(f"TRANSFERÊNCIA: FALHA — {type(exc).__name__}: {exc}", flush=True)

    return HTTPServer((host, port), Handler)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Recebe pacote APEX por localhost com validação SHA-256."
    )
    parser.add_argument("target", help="caminho final, ex.: /public/PACOTE.tar.gz")
    parser.add_argument("sha256", help="SHA-256 esperado")
    parser.add_argument("--port", type=int, default=18775)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args(argv)

    expected = args.sha256.strip().lower()
    if not valid_sha256(expected):
        raise SystemExit("SHA-256 esperado inválido")
    if not (1 <= args.port <= 65535):
        raise SystemExit("porta inválida")

    target = Path(args.target).expanduser().resolve()
    server = build_server(target, expected, args.host, args.port)
    print(f"ABRA: http://127.0.0.1:{args.port}", flush=True)
    print(f"DESTINO: {target}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
