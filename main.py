"""
⚡ APEX - Main Orquestrador
Ponto de entrada principal do APEX
Similar a como funciona o Perplexity AI
"""

import sys
import os
from pathlib import Path

# Adicionar o diretório raiz ao path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

import json
import logging
from datetime import datetime

# Imports dos módulos APEX
try:
    from apex_nle import interpretar_comando
    from comandos import executar_comando
    from apex_web_search import buscar_web
    from instalador import verificar_dependencias
except ImportError as e:
    print(f"Erro ao importar módulos: {e}")
    print("Execute: pip install -r requirements.txt")
    sys.exit(1)

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('APEX')


class APEXOrchestrator:
    """
    Orquestrador principal do APEX
    Gerencia o fluxo de requisições e respostas
    """
    
    def __init__(self):
        self.nome = "APEX"
        self.versao = "1.0.0"
        self.modo = "CLI"
        self.historico = []
        logger.info(f"{self.nome} v{self.versao} iniciado")
    
    def processar_entrada(self, entrada: str) -> dict:
        """
        Processa a entrada do usuário
        Retorna um dicionário com o resultado
        """
        resultado = {
            'timestamp': datetime.now().isoformat(),
            'entrada': entrada,
            'tipo': None,
            'resposta': None,
            'sucesso': False
        }
        
        try:
            # 1. Interpretar o comando
            comando_interpretado = interpretar_comando(entrada)
            resultado['tipo'] = 'comando' if comando_interpretado != entrada else 'busca_web'
            
            # 2. Decidir se é busca web ou comando
            if "pesquisar" in entrada.lower() or "pesquise" in entrada.lower():
                logger.info(f"Modo: Busca Web - {entrada}")
                resposta = buscar_web(entrada)
                resultado['tipo'] = 'busca_web'
            else:
                logger.info(f"Modo: Executação de Comando - {comando_interpretado}")
                resposta = executar_comando(comando_interpretado)
                resultado['tipo'] = 'comando'
            
            resultado['resposta'] = resposta
            resultado['sucesso'] = True
            
        except Exception as e:
            logger.error(f"Erro ao processar: {e}")
            resultado['resposta'] = f"Erro: {str(e)}"
            resultado['sucesso'] = False
        
        # Adicionar ao histórico
        self.historico.append(resultado)
        
        return resultado
    
    def modo_interativo(self):
        """
        Inicia o APEX no modo interativo (CLI)
        """
        print(f"""
        ⚡ {self.nome} v{self.versao} - Automação de Ferramentas Inteligente
        Similar ao Perplexity AI com busca web e automação
        Digite 'sair' para encerrar
        """)
        
        while True:
            try:
                entrada = input("\n🤖 APEX> ").strip()
                
                if entrada.lower() in ['sair', 'exit', 'quit']:
                    print("\n⚡ APEX desligando...")
                    break
                
                if not entrada:
                    continue
                
                resultado = self.processar_entrada(entrada)
                
                # Exibir resposta
                print(f"""
✅ [{resultado['tipo'].upper()}]\n{resultado['resposta']}
                """)
                
            except KeyboardInterrupt:
                print("\n⚡ APEX interrompido pelo usuário")
                break
            except Exception as e:
                print(f"\n❌ Erro: {e}")
    
    def verificar_sistema(self):
        """
        Verifica dependências do sistema
        """
        print("\n🔍 Verificando dependências do sistema...")
        resultado = verificar_dependencias()
        print(resultado)


def main():
    """
    Função principal
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description='APEX - Automação de Ferramentas Inteligente'
    )
    parser.add_argument(
        '--modo',
        choices=['cli', 'api', 'voz'],
        default='cli',
        help='Modo de execução'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Verificar dependências'
    )
    parser.add_argument(
        '--comando',
        type=str,
        help='Executar um comando direto'
    )
    
    args = parser.parse_args()
    
    # Criar orquestrador
    apex = APEXOrchestrator()
    
    # Verificar dependências se solicitado
    if args.check:
        apex.verificar_sistema()
        return
    
    # Executar comando direto se fornecido
    if args.comando:
        resultado = apex.processar_entrada(args.comando)
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return
    
    # Iniciar no modo solicitado
    if args.modo == 'cli':
        apex.modo_interativo()
    elif args.modo == 'voz':
        print("Modo voz: execute jarvis_voz.py")
        os.system('python jarvis_voz.py')
    elif args.modo == 'api':
        print("Modo API: execute jarvis_voz.py (inclui Flask)")
        os.system('python jarvis_voz.py')


if __name__ == "__main__":
    main()
