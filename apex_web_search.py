# apex_web_search.py
"""Sistema de busca web integrado ao APEX - Funciona como Perplexity"""

import requests
from bs4 import BeautifulSoup
import json
from typing import List, Dict
import re


class APEXWebSearch:
    """
    Sistema de busca inteligente que pesquisa e extrai informações da web.
    Similar ao Perplexity AI.
    """
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.max_results = 5
    
    def buscar_google(self, query: str) -> List[Dict]:
        """
        Realiza busca no Google e retorna resultados.
        """
        try:
            # API do Google Custom Search (você precisará adicionar sua chave)
            # Por enquanto, faremos web scraping básico
            
            search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
            response = requests.get(search_url, headers=self.headers, timeout=10)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            
            # Extrair resultados de busca
            for g in soup.find_all('div', class_='g')[:self.max_results]:
                try:
                    title_elem = g.find('h3')
                    link_elem = g.find('a')
                    snippet_elem = g.find('div', class_=['VwiC3b', 'yXK7lf'])
                    
                    if title_elem and link_elem:
                        results.append({
                            'title': title_elem.get_text(),
                            'url': link_elem.get('href'),
                            'snippet': snippet_elem.get_text() if snippet_elem else ""
                        })
                except:
                    continue
            
            return results
        
        except Exception as e:
            print(f"Erro na busca: {e}")
            return []
    
    def extrair_conteudo(self, url: str) -> str:
        """
        Extrai o conteúdo principal de uma página web.
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remover scripts e estilos
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Extrair texto
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text[:5000]  # Primeiros 5000 caracteres
        
        except Exception as e:
            print(f"Erro ao extrair conteúdo: {e}")
            return ""
    
    def pesquisar_e_resumir(self, pergunta: str) -> str:
        """
        Busca na web e gera uma resposta resumida.
        Comportamento similar ao Perplexity.
        """
        print(f"\n🔍 Buscando: {pergunta}\n")
        
        # 1. Buscar no Google
        resultados = self.buscar_google(pergunta)
        
        if not resultados:
            return "Não consegui encontrar resultados para sua pergunta."
        
        # 2. Extrair conteúdo dos primeiros resultados
        conteudo_total = []
        fontes = []
        
        for i, resultado in enumerate(resultados[:3], 1):
            print(f"[{i}] {resultado['title']}")
            print(f"    {resultado['url'][:80]}...")
            
            conteudo = self.extrair_conteudo(resultado['url'])
            if conteudo:
                conteudo_total.append(conteudo)
                fontes.append(f"[{i}] {resultado['title']} - {resultado['url']}")
        
        # 3. Criar resposta resumida
        resposta = f"🤖 APEX encontrou {len(resultados)} resultados:\n\n"
        
        # Adicionar snippets dos resultados
        for i, resultado in enumerate(resultados, 1):
            resposta += f"[{i}] {resultado['title']}\n"
            if resultado['snippet']:
                resposta += f"    {resultado['snippet'][:200]}...\n"
            resposta += f"    {resultado['url']}\n\n"
        
        resposta += "\nℹ️ Use os números para acessar as fontes detalhadas."
        
        return resposta


# Função principal para integração com APEX
def buscar_web(query: str) -> str:
    """
    Interface simplificada para busca web.
    """
    search = APEXWebSearch()
    return search.pesquisar_e_resumir(query)


if __name__ == "__main__":
    # Teste
    resultado = buscar_web("qual a temperatura ideal para dormir bem")
    print(resultado)
