from flask import Flask, render_template, jsonify
import pandas as pd
import json
import os
import logging

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

@app.route('/')
def dashboard():
    """Dashboard com dados processados."""
    try:
        if os.path.exists('output.json'):
            with open('output.json', 'r') as f:
                data = json.load(f)
            df = pd.DataFrame(data)
            html = df.to_html()
            return f"<h1>Dashboard APEX</h1>{html}"
        else:
            return "<h1>Nenhum dado</h1>"
    except Exception as e:
        return f"<h1>Erro: {e}</h1>"

@app.route('/api/data')
def get_data():
    """Retorna dados em JSON."""
    if os.path.exists('output.json'):
        with open('output.json', 'r') as f:
            return jsonify(json.load(f))
    return jsonify({"error": "No data"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
