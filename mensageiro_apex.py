import time
import requests
import json
import os


ARQUIVO_COMANDO = "copilot_bridge.txt"
ARQUIVO_RESPOSTA = "apex_response.txt"


URL_APEX = "http://127.0.0.1:5000/comando"



def enviar_para_apex(texto):
    try:
        dados = {"texto": texto}
        resposta = requests.post(URL_APEX, json=dados, timeout=5)


        try:
            retorno = resposta.json()
        except:
            retorno = {"status": "erro", "mensagem": "Resposta inválida do servidor"}


        print("APEX respondeu:", retorno)


        with open(ARQUIVO_RESPOSTA, "w", encoding="utf-8") as f:
            f.write(json.dumps(retorno, ensure_ascii=False))


    except Exception as e:
        print("Erro ao enviar comando:", e)
        with open(ARQUIVO_RESPOSTA, "w", encoding="utf-8") as f:
            f.write(json.dumps({"status": "erro", "mensagem": str(e)}, ensure_ascii=False))



def limpar_arquivo_comando():
    with open(ARQUIVO_COMANDO, "w", encoding="utf-8") as f:
        f.write("")



def loop_mensageiro():
    print("Mensageiro APEX iniciado. Aguardando comandos do Copilot...")


    ultimo_texto = ""


    while True:
        if os.path.exists(ARQUIVO_COMANDO):
            with open(ARQUIVO_COMANDO, "r", encoding="utf-8") as f:
                texto = f.read().strip()


            if texto and texto != ultimo_texto:
                print("Comando recebido do Copilot:", texto)


                enviar_para_apex(texto)
                ultimo_texto = texto


                limpar_arquivo_comando()


        time.sleep(0.3)



if __name__ == "__main__":
    loop_mensageiro()
