import os
import json
import threading
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template, Response

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024

_WRITE_LOCK = threading.Lock()
_VALID_AREAS = {"ads", "it"}

def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default

def _save_json(path, data):
    with _WRITE_LOCK:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temp_path = path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)

@app.before_request
def _check_access():
    if request.method == "OPTIONS":
        return
    
    public_paths = ["/", "/ads", "/estudos", "/health"]
    if request.path in public_paths or request.path.startswith("/static/"):
        return

    access_key = os.getenv("APEX_ACCESS_KEY", "").strip()
    app_env = os.getenv("APP_ENV", "production").lower()

    if app_env == "production" and not access_key:
        return jsonify({
            "ok": False, 
            "error": "Erro crítico de segurança: APEX_ACCESS_KEY não configurada no ambiente."
        }), 500

    if access_key:
        client_key = request.headers.get("X-Apex-Key")
        if not client_key:
            return jsonify({"ok": False, "error": "Autenticação requerida. Chave ausente no header."}), 401
        if client_key != access_key:
            return jsonify({"ok": False, "error": "Chave de acesso inválida."}), 403

@app.route("/")
def index():
    return render_template("chat.html")

@app.route("/ads")
def ads():
    return render_template("chat.html")

@app.route("/estudos")
def estudos():
    return render_template("estudos.html")

@app.route("/health")
def health():
    return jsonify({"ok": True, "status": "healthy"})

@app.route("/api/notes", methods=["GET", "POST", "DELETE"])
def handle_notes():
    notes_path = os.path.join("data", "notes.json")
    notes = _load_json(notes_path, [])

    if request.method == "GET":
        return jsonify({"ok": True, "notes": notes})

    data = request.get_json() or {}
    if request.method == "POST":
        text = str(data.get("text", "")).strip()
        area = str(data.get("area", "ads")).strip().lower()
        
        if area not in _VALID_AREAS:
            return jsonify({"ok": False, "error": "Área de estudo inválida."}), 400
        if not text:
            return jsonify({"ok": False, "error": "Texto da nota vazio."}), 400

        new_note = {
            "id": int(datetime.now(timezone.utc).timestamp() * 1000),
            "text": text,
            "area": area,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        notes.insert(0, new_note)
        _save_json(notes_path, notes)
        return jsonify({"ok": True, "note": new_note})

    if request.method == "DELETE":
        note_id = data.get("id")
        notes = [n for n in notes if n.get("id") != note_id]
        _save_json(notes_path, notes)
        return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
