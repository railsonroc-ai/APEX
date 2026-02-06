"""
apex_perplexity_integration.py
Integração APEX com Perplexity AI
Funciona como o Perplexity com busca web e respostas contextualizadas
"""

import requests
import json
from typing import Optional, Dict, List
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PerplexityIntegration:
    """
    Integração com Perplexity AI
    Oferece respostas inteligentes com busca web
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa a integração
        API Key pode vir de variável de ambiente ou parâmetro
        """
        self.api_key = api_key or os.getenv('PERPLEXITY_API_KEY')
        self.modelo = "pplx-70b-online"  # Modelo com acesso web
        self.url_api = "https://api.perplexity.ai/chat/completions"
        self.historico = []
        self.max_tokens = 1000
    
    def fazer_pergunta(self, pergunta: str, com_web: bool = True) -> Dict:
        """
        Faz uma pergunta ao Perplexity e retorna resposta
        """
        if not self.api_key:
            return {
                'status': 'erro',
                'mensagem': 'PERPLEXITY_API_KEY não configurada',
                'solucao': 'Defina a variável de ambiente PERPLEXITY_API_KEY'
            }
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Selecionar modelo com ou sem busca web
            modelo_selecionado = "pplx-70b-online" if com_web else "pplx-70b"
            
            payload = {
                "model": modelo_selecionado,
                "messages": self._preparar_mensagens(pergunta),
                "max_tokens": self.max_tokens,
                "temperature": 0.7,
                "top_p": 0.9,
                "stream": False
            }
            
            response = requests.post(self.url_api, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                resultado = response.json()
                resposta_completa = resultado['choices'][0]['message']['content']
                
                # Armazenar no histórico
                self.historico.append({
                    'timestamp': datetime.now().isoformat(),
                    'pergunta': pergunta,
                    'resposta': resposta_completa,
                    'modelo': modelo_selecionado,
                    'tokens': resultado['usage']['total_tokens']
                })
                
                return {
                    'status': 'sucesso',
                    'resposta': resposta_completa,
                    'com_busca_web': com_web,
                    'modelo': modelo_selecionado,
                    'tokens_usados': resultado['usage']['total_tokens']
                }
            else:
                logger.error(f"Erro da API: {response.status_code}")
                return {
                    'status': 'erro',
                    'mensagem': f'Erro HTTP {response.status_code}',
                    'detalhes': response.text
                }
        
        except requests.exceptions.Timeout:
            return {'status': 'erro', 'mensagem': 'Timeout na conexão com Perplexity'}
        except Exception as e:
            logger.error(f"Erro: {e}")
            return {'status': 'erro', 'mensagem': str(e)}
    
    def _preparar_mensagens(self, pergunta: str) -> List[Dict]:
        """
        Prepara o histórico de mensagens para a API
        """
        mensagens = []
        
        # Adicionar contexto do histórico (limitado aos últimos 5)
        for item in self.historico[-5:]:
            mensagens.append({
                "role": "user",
                "content": item['pergunta']
            })
            mensagens.append({
                "role": "assistant",
                "content": item['resposta']
            })
        
        # Adicionar pergunta atual
        mensagens.append({
            "role": "user",
            "content": pergunta
        })
        
        return mensagens
    
    def resumir_com_contexto(self, texto: str, contexto: Optional[str] = None) -> str:
        """
        Resumir um texto com contexto usando Perplexity
        """
        prompt = f"Resuma o seguinte texto em 3-5 frases:\n\n{texto}"
        
        if contexto:
            prompt += f"\n\nContexto: {contexto}"
        
        resultado = self.fazer_pergunta(prompt, com_web=False)
        return resultado.get('resposta', 'Não foi possível processar')
    
    def pesquisar_com_ia(self, termo_busca: str) -> str:
        """
        Realiza busca usando inteligência do Perplexity
        """
        prompt = f"Pesquise e resuma as informações mais relevantes sobre: {termo_busca}"
        resultado = self.fazer_pergunta(prompt, com_web=True)
        return resultado.get('resposta', 'Não encontrado')
    
    def obter_historico(self) -> List[Dict]:
        """
        Retorna o histórico de perguntas e respostas
        """
        return self.historico
    
    def limpar_historico(self):
        """
        Limpa o histórico de conversa
        """
        self.historico = []
        logger.info("Histórico limpo")
    
    def exportar_historico(self, arquivo: str = 'historico_apex.json'):
        """
        Exporta o histórico para arquivo JSON
        """
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(self.historico, f, ensure_ascii=False, indent=2)
        logger.info(f"Histórico exportado para {arquivo}")


def testar_integracao():
    """
    Testa a integração com Perplexity
    """
    print("\n📌 Testando integração com Perplexity...\n")
    
    perplexity = PerplexityIntegration()
    
    # Teste 1: Pergunta simples
    print("[TESTE 1] Pergunta simples")
    resultado = perplexity.fazer_pergunta("Qual é a capital do Brasil?")
    print(f"Status: {resultado.get('status')}")
    if resultado.get('status') == 'sucesso':
        print(f"Resposta: {resultado.get('resposta')[:100]}...\n")
    
    # Teste 2: Busca com web
    print("[TESTE 2] Busca com contexto web")
    resultado = perplexity.fazer_pergunta("Quais são as tendências de IA em 2024?", com_web=True)
    print(f"Status: {resultado.get('status')}")
    
    # Teste 3: Histórico
    print(f"\n[TESTE 3] Histórico de conversa")
    historico = perplexity.obter_historico()
    print(f"Total de interacoes: {len(historico)}")


if __name__ == "__main__":
    testar_integracao()
