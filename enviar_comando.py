import requests
import json


URL_APEX = "http://127.0.0.1:5000/comando"
ARQUIVO_RESPOSTA = "apex_response.txt"



def enviar(texto):
    dados = {"texto": texto}


    try:
        resposta = requests.post(URL_APEX, json=dados, timeout=5)


        try:
            retorno = resposta.json()
        except:
            retorno = {"status": "erro", "mensagem": "Resposta inválida do servidor"}


        print("Resposta do APEX:", retorno)


        with open(ARQUIVO_RESPOSTA, "w", encoding="utf-8") as f:
            f.write(json.dumps(retorno, ensure_ascii=False))


        return retorno


    except Exception as e:
        erro = {"status": "erro", "mensagem": str(e)}
        print("Erro ao enviar comando:", erro)


        with open(ARQUIVO_RESPOSTA, "w", encoding="utf-8") as f:
            f.write(json.dumps(erro, ensure_ascii=False))


        return erro



if __name__ == "__main__":
    while True:
        comando = input("Digite o comando para o APEX: ")
        enviar(comando)
