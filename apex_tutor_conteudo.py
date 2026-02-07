"""apex_tutor_conteudo.py - Tutor de conteúdo com AI"""
from typing import Dict, List, Optional, Any

class TutorConteudo:
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def explicar_conteudo(self, conteudo: str, nivel: str = 'intermediário') -> str:
        prompt = f"Explique este conteúdo de forma clara para um aluno em nível {nivel}:\n{conteudo}"
        return self.llm.gerar_resposta(prompt)
    
    def resumir(self, conteudo: str, tamanho: str = 'medio') -> str:
        instrucoes = {'pequeno': 100, 'medio': 300, 'grande': 700}
        palavras = instrucoes.get(tamanho, 300)
        prompt = f"Resuma este texto em ~{palavras} palavras:\n{conteudo}"
        return self.llm.gerar_resposta(prompt)
    
    def gerar_exercicios(self, conteudo: str, quantidade: int = 3) -> List[str]:
        prompt = f"Crie {quantidade} exercícios sobre:\n{conteudo}"
        resposta = self.llm.gerar_resposta(prompt)
        return resposta.split('\n')[:quantidade]
    
    def responder_duvida(self, conteudo: str, duvida: str) -> str:
        prompt = f"Contexto: {conteudo}\nDúvida do aluno: {duvida}\nResponda de forma didática."
        return self.llm.gerar_resposta(prompt)

def criar_tutor(llm_client) -> TutorConteudo:
    return TutorConteudo(llm_client)
