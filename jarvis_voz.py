import sounddevice as sd
import soundfile as sf
import os
import subprocess
import threading
from flask import Flask, request
from comandos import executar_comando
from apex_nle import interpretar_comando


app = Flask(__name__)


# ============================
# FUNÇÕES DE ÁUDIO
# ============================


def falar(texto: str):
    comando = f'powershell -Command "Add-Type –AssemblyName System.Speech; ' \
              f'$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; ' \
              f'$speak.Speak(\'{texto}\');"'
    os.system(comando)


def ouvir_microfone(duracao=5):
    fs = 44100
    audio = sd.rec(int(duracao * fs), samplerate=fs, channels=1)
    sd.wait()
    sf.write("voz.wav", audio, fs)
    return "voz.wav"


def transcrever(caminho_audio):
    try:
        resultado = subprocess.check_output(
            ["whisper", caminho_audio, "--model", "tiny", "--language", "pt"],
            stderr=subprocess.STDOUT,
            text=True
        )
        linhas = resultado.splitlines()
        return linhas[-1] if linhas else ""
    except:
        return ""


# ============================
# HOTWORD
# ============================


def esperar_hotword():
    while True:
        audio = ouvir_microfone(3)
        texto = transcrever(audio).lower()
        if "apex" in texto:
            falar("Sim?")
            return


# ============================
# LOOP PRINCIPAL
# ============================


def loop_principal():
    while True:
        esperar_hotword()
        audio = ouvir_microfone(5)
        texto = transcrever(audio)


        print("Você disse:", texto)


        if not texto.strip():
            falar("Não entendi, pode repetir")
            continue


        comando_final = interpretar_comando(texto)
        resposta = executar_comando(comando_final)
        falar(resposta)


# ============================
# SERVIDOR FLASK PARA COMANDOS EXTERNOS
# ============================


@app.route("/comando", methods=["POST"])
def receber_comando():
    try:
        dados = request.get_json()
        texto = dados.get("texto", "").strip()


        if not texto:
            return {"status": "erro", "mensagem": "Comando vazio"}, 400


        print("\n=== COMANDO RECEBIDO DO COPILOT ===")
        print("Texto recebido:", texto)


        comando_final = interpretar_comando(texto)
        resposta = executar_comando(comando_final)


        try:
            falar(resposta)
        except:
            print("Falha ao falar a resposta")


        print("Resposta enviada ao Copilot:", resposta)


        return {"status": "ok", "mensagem": resposta}, 200


    except Exception as e:
        print("Erro no servidor Flask:", e)
        return {"status": "erro", "mensagem": str(e)}, 500


def iniciar_servidor():
    app.run(port=5000)


# ============================
# INICIAR SISTEMA
# ============================


if __name__ == "__main__":
    falar("APEX iniciado. Aguardando comandos.")
    threading.Thread(target=iniciar_servidor).start()
    loop_principal()
