"""APEX - Main Orquestrador

Ponto de entrada principal do APEX
Similar a como funciona o Perplexity AI
"""

import os
import logging
import requests
from concurrent.futures import ThreadPoolExecutor
from pydantic import BaseModel, ValidationError

try:
    from utils import load_config, save_data
except ImportError:
    print("Aviso: utils.py não encontrado. Usando funções básicas.")

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('apex.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class ItemData(BaseModel):
    """Modelo de validação para dados de item."""
    id: int
    name: str
    value: float

def fetch_item_data(item_id: int) -> dict:
    """
    Busca dados de um item via API de forma segura e validada.
    
    Args:
        item_id (int): ID único do item.
    
    Returns:
        dict: Dados validados do item ou None se erro.
    """
    api_key = os.environ.get('API_KEY')
    if not api_key:
        logger.warning(f"API_KEY não definida para item {item_id}")
        return None
    
    try:
        response = requests.get(
            f'https://api.example.com/items/{item_id}',
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        validated_data = ItemData(**data)
        logger.info(f"Item {item_id} obtido e validado.")
        return validated_data.dict()
    except requests.RequestException as e:
        logger.error(f"Erro de rede para item {item_id}: {e}")
        return None
    except ValidationError as e:
        logger.error(f"Dados inválidos para item {item_id}: {e}")
        return None

def main():
    """
    Função principal: Carrega config, processa itens em paralelo e salva dados.
    """
    try:
        config = load_config()
    except Exception as e:
        logger.error(f"Erro ao carregar config: {e}")
        config = {}
    
    item_ids = config.get('item_ids', [1, 2, 3])
    
    if not item_ids:
        logger.warning("Nenhum item_id encontrado.")
        return
    
    logger.info(f"Iniciando processamento de {len(item_ids)} itens...")
    user_data_list = []
    
    # Paralelização para melhorar performance
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_item_data, item_id) for item_id in item_ids]
        for i, future in enumerate(futures):
            try:
                result = future.result(timeout=15)
                if result:
                    user_data_list.append(result)
                    logger.info(f"Item {i+1}/{len(item_ids)} processado.")
            except Exception as e:
                logger.error(f"Erro ao processar future {i}: {e}")
    
    try:
        save_data(user_data_list, 'output.json')
        logger.info(f"Processamento concluído. {len(user_data_list)} itens salvos.")
    except Exception as e:
        logger.error(f"Erro ao salvar dados: {e}")

if __name__ == "__main__":
    main()
