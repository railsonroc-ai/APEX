"""Novo Arquivo: code_generation_utils.py (Para Criação de Ferramentas/Apps)
Descrição: Gera código/apps baseado em prompts usando Perplexity.
"""
import os
import requests
import logging

logging.basicConfig(level=logging.INFO)

def generate_tool_code(prompt: str) -> str:
    """
    Gera código para tool/app usando Perplexity (plano pro).
    Ex.: 'Crie um app Flask para flashcards de francês'.
    
    Args:
        prompt: Descrição da ferramenta desejada
        
    Returns:
        Código Python gerado
    """
    perplexity_api_key = os.environ.get('PERPLEXITY_API_KEY')
    if not perplexity_api_key:
        logging.error("PERPLEXITY_API_KEY não configurada.")
        return "Configure PERPLEXITY_API_KEY no arquivo .env."
    
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {perplexity_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "pplx-70b-chat",
        "messages": [
            {
                "role": "user",
                "content": f"Gere código Python completo para: {prompt}. Foque em simplicidade e educação. Inclua comentários explicativos."
            }
        ],
        "max_tokens": 1500
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            code = response.json()['choices'][0]['message']['content']
            # Salva em arquivo
            with open('generated_tool.py', 'w', encoding='utf-8') as f:
                f.write(code)
            logging.info(f"Código gerado e salvo em generated_tool.py")
            return code
        else:
            logging.error(f"Erro na API Perplexity: {response.status_code}")
            return f"Erro ao gerar código: {response.text}"
    except Exception as e:
        logging.error(f"Exceção ao gerar código: {e}")
        return f"Erro: {str(e)}"

def generate_educational_app(topic: str, app_type: str = "quiz") -> str:
    """
    Gera aplicação educacional específica.
    
    Args:
        topic: Tópico de ensino (ex: "Python", "Francês")
        app_type: Tipo de app ("quiz", "flashcards", "practice")
        
    Returns:
        Código da aplicação educacional
    """
    prompts = {
        "quiz": f"Crie um aplicativo de quiz interativo sobre {topic} com 10 perguntas",
        "flashcards": f"Crie um sistema de flashcards para estudar {topic}",
        "practice": f"Crie exercícios práticos interativos sobre {topic}"
    }
    
    prompt = prompts.get(app_type, prompts["quiz"])
    return generate_tool_code(prompt)

def generate_automation_script(task_description: str) -> str:
    """
    Gera script de automação baseado em descrição.
    
    Args:
        task_description: Descrição da tarefa a automatizar
        
    Returns:
        Script Python para automação
    """
    prompt = f"Crie um script Python para automatizar: {task_description}. Inclua tratamento de erros e documentação."
    return generate_tool_code(prompt)
