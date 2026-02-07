import json
import logging
import os

logger = logging.getLogger(__name__)

def load_config(config_path: str = 'config.json') -> dict:
    """
    Carrega configurações de um arquivo JSON.
    
    Args:
        config_path (str): Caminho para o arquivo de config.
    
    Returns:
        dict: Configurações carregadas.
    """
    if not os.path.exists(config_path):
        logger.warning(f"Arquivo '{config_path}' não encontrado. Usando config vazia.")
        return {}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info(f"Config carregada de {config_path}.")
        return config
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao decodificar JSON em {config_path}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Erro ao carregar config: {e}")
        return {}

def save_data(data: list, output_path: str):
    """
    Salva lista de dados em um arquivo JSON.
    
    Args:
        data (list): Dados a salvar.
        output_path (str): Caminho do arquivo de saída.
    """
    try:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.info(f"Dados salvos em {output_path}.")
    except IOError as e:
        logger.error(f"Erro ao salvar dados em {output_path}: {e}")
    except Exception as e:
        logger.error(f"Erro desconhecido ao salvar dados: {e}")
