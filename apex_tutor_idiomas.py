"""apex_tutor_idiomas.py - Tutor de idiomas com IA"""
from typing import List, Dict, Optional

class TutorIdiomas:
    def __init__(self, llm_client):
        self.llm = llm_client
        self.idiomas_suportados = ['inglés', 'alemão', 'espanhol', 'francês']
    
    def ensinar_gramatica(self, idioma: str, topico: str, nivel: str = 'iniciante') -> str:
        prompt = f"Ensine sobre {topico} em {idioma} para alguém em nível {nivel}. Inclua exemplos práticos."
        return self.llm.gerar_resposta(prompt)
    
    def corrigir_frase(self, idioma: str, frase: str) -> Dict[str, str]:
        prompt = f"Corrija esta frase em {idioma}: '{frase}'. Explique os erros."
        correcao = self.llm.gerar_resposta(prompt)
        return {'frase_original': frase, 'correcao': correcao}
    
    def criar_dialogo(self, idioma: str, contexto: str, nivel: str = 'intermediário') -> str:
        prompt = f"Crie um diálogo em {idioma} para nível {nivel} sobre: {contexto}"
        return self.llm.gerar_resposta(prompt)
    
    def pronunciacao(self, idioma: str, palavra: str) -> str:
        prompt = f"Explique como pronunciar '{palavra}' em {idioma}. Use descrição fonética."
        return self.llm.gerar_resposta(prompt)
    
    def traduzir_com_contexto(self, idioma_origem: str, idioma_destino: str, texto: str) -> Dict:
        prompt = f"Traduza de {idioma_origem} para {idioma_destino}: '{texto}'. Explique a tradução."
        traducao = self.llm.gerar_resposta(prompt)
        return {'texto_origem': texto, 'idioma_origem': idioma_origem, 'traducao': traducao}

def criar_tutor(llm_client) -> TutorIdiomas:
    return TutorIdiomas(llm_client)
