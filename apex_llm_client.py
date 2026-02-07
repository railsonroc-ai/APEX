"""apex_llm_client.py
Cliente de integr action com Perplexity AI para gera action de respostas inteligentes.

Descri action:
    Módulo para integra action com a API da Perplexity AI, permitindo
    gera action de respostas contextualizadas baseadas em prompts e contextos fornecidos.

Fun action principais:
    - gerar_resposta: Gera uma resposta usando o modelo da Perplexity
    - chat_contextualizado: Genera respostas com contexto de sess action
    - processar_com_streaming: Processa respostas em tempo real
"""

import os
import json
from dotenv import load_dotenv
import requests
from typing import Optional, List, Dict, Any

# Carregar variáveis de ambiente
load_dotenv()

class APEXLLMClient:
    """
    Cliente para integra action com Perplexity AI.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa o cliente LLM.
        
        Args:
            api_key: Chave da API da Perplexity (se None, lê do .env)
        """
        self.api_key = api_key or os.getenv('PERPLEXITY_API_KEY')
        self.base_url = "https://api.perplexity.ai/openai/v1"
        self.model = "pplx-7b-online"
        self.temperature = 0.7
        
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY não definida no .env")
    
    def gerar_resposta(
        self,
        prompt: str,
        sistema: str = None,
        temperatura: float = None,
        contexto: Optional[List[str]] = None
    ) -> str:
        """
        Gera uma resposta usando a API da Perplexity.
        
        Args:
            prompt: Pergunta ou instru action do usuário
            sistema: Instru action do sistema (role='system')
            temperatura: Controla a criatividade (0-1)
            contexto: Lista de contextos anteriores para referência
            
        Returns:
            Resposta gerada pelo modelo
        """
        temperatura = temperatura or self.temperature
        
        messages = []
        
        if sistema:
            messages.append({"role": "system", "content": sistema})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperatura,
                    "max_tokens": 2048
                },
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            return data['choices'][0]['message']['content']
        
        except requests.exceptions.RequestException as e:
            return f"Erro ao conectar com Perplexity: {str(e)}"
    
    def chat_contextualizado(
        self,
        prompt: str,
        historico: Optional[List[Dict]] = None,
        sistema: str = None
    ) -> str:
        """
        Gera uma resposta com contexto do histórico de conversa action.
        
        Args:
            prompt: Mensagem atual do usuário
            historico: List de mensagens anteriores
            sistema: Instru action do sistema
            
        Returns:
            Resposta contextualizada
        """
        messages = []
        
        if sistema:
            messages.append({"role": "system", "content": sistema})
        
        if historico:
            messages.extend(historico)
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": 2048
                },
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            return data['choices'][0]['message']['content']
        
        except requests.exceptions.RequestException as e:
            return f"Erro: {str(e)}"

# Função auxiliar para uso direto
def gerar_resposta_simples(prompt: str, api_key: Optional[str] = None) -> str:
    """
    Gera uma resposta simples sem contexto.
    
    Args:
        prompt: Pergunta
        api_key: Chave da API (opcional)
        
    Returns:
        Resposta do modelo
    """
    client = APEXLLMClient(api_key)
    return client.gerar_resposta(prompt)

if __name__ == "__main__":
    # Teste simples
    client = APEXLLMClient()
    resposta = client.gerar_resposta("Qual é a capital do Brasil?")
    print(resposta)
