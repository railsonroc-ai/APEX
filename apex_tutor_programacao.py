"""apex_tutor_programacao.py - Tutor de Programação com IA"""
from typing import Dict

class TutorProgramacao:
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def explicar_conceito(self, linguagem: str, conceito: str, nivel='iniciante') -> str:
        prompt = f"Explique {conceito} em {linguagem} para nível {nivel}. Inclua exemplos de código."
        return self.llm.gerar_resposta(prompt)
    
    def revisar_codigo(self, linguagem: str, codigo: str) -> Dict:
        prompt = f"Revise este código {linguagem}:\n{codigo}\nAonte melhorias."
        return {'codigo': codigo, 'revisao': self.llm.gerar_resposta(prompt)}
    
    def debugar_codigo(self, linguagem: str, codigo: str, erro: str) -> str:
        prompt = f"Debug código {linguagem}:\n{codigo}\nErro: {erro}"
        return self.llm.gerar_resposta(prompt)
    
    def criar_exercicio(self, linguagem: str, topico: str, dif='facil') -> str:
        prompt = f"Crie exercício {linguagem} sobre {topico} - dificuldade {dif}."
        return self.llm.gerar_resposta(prompt)

def criar_tutor(llm_client):
    return TutorProgramacao(llm_client)
