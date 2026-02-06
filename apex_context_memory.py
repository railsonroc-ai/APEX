"""apex_context_memory.py - Sistema de memória contextual e histórico persistente"""
import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

class ContextMemory:
    """
    Gerenciador de memória contextual do APEX
    Armazena histórico persistente em SQLite
    """
    def __init__(self, db_path: str = 'apex_memory.db'):
        self.db_path = db_path
        self._inicializar_db()
    
    def _inicializar_db(self):
        """Cria tabelas do banco de dados"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversa (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    pergunta TEXT,
                    resposta TEXT,
                    fonte TEXT,
                    tokens INTEGER
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contexto (
                    id INTEGER PRIMARY KEY,
                    chave TEXT UNIQUE,
                    valor TEXT,
                    atualizado TEXT
                )
            ''')
            conn.commit()
    
    def adicionar_conversa(self, pergunta: str, resposta: str, fonte: str = 'perplexity', tokens: int = 0):
        """Armazena uma conversa no histórico"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO conversa (timestamp, pergunta, resposta, fonte, tokens)
                VALUES (?, ?, ?, ?, ?)
            ''', (datetime.now().isoformat(), pergunta, resposta, fonte, tokens))
            conn.commit()
    
    def obter_contexto(self, limite: int = 10) -> List[Dict]:
        """Retorna as últimas conversar para contexto"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'SELECT * FROM conversa ORDER BY id DESC LIMIT {limite}')
            return [dict(zip([desc[0] for desc in cursor.description], row)) for row in cursor.fetchall()]
    
    def salvar_variavel(self, chave: str, valor: str):
        """Salva uma variável de contexto"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO contexto (chave, valor, atualizado)
                VALUES (?, ?, ?)
            ''', (chave, valor, datetime.now().isoformat()))
            conn.commit()
    
    def obter_variavel(self, chave: str) -> Optional[str]:
        """Obtém uma variável de contexto"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT valor FROM contexto WHERE chave = ?', (chave,))
            resultado = cursor.fetchone()
            return resultado[0] if resultado else None
    
    def exportar_historico(self, arquivo: str = 'apex_historico.json'):
        """Exporta histórico para JSON"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM conversa')
            colunas = [desc[0] for desc in cursor.description]
            dados = [dict(zip(colunas, row)) for row in cursor.fetchall()]
        
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
