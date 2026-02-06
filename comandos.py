import os
import webbrowser
import subprocess


def executar_comando(texto):
    texto = texto.lower()


    # -----------------------------
    # ABRIR YOUTUBE
    # -----------------------------
    if "abrir youtube" in texto:
        webbrowser.open("https://www.youtube.com")
        return "Abrindo o YouTube."


    # -----------------------------
    # ABRIR GOOGLE CHROME
    # -----------------------------
    if "abrir chrome" in texto or "abrir navegador chrome" in texto:
        caminhos = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
        ]


        for caminho in caminhos:
            caminho_exp = os.path.expandvars(caminho)
            if os.path.exists(caminho_exp):
                subprocess.Popen([caminho_exp])
                return "Abrindo o Google Chrome."


        return "Chrome não encontrado no sistema."


    # -----------------------------
    # ABRIR BLOCO DE NOTAS
    # -----------------------------
    if "abrir bloco de notas" in texto or "abrir notepad" in texto:
        subprocess.Popen(["notepad.exe"])
        return "Abrindo o Bloco de Notas."


    # -----------------------------
    # ABRIR CALCULADORA
    # -----------------------------
    if "abrir calculadora" in texto:
        subprocess.Popen(["calc.exe"])
        return "Abrindo a calculadora."


    # -----------------------------
    # ABRIR PASTA DOWNLOADS
    # -----------------------------
    if "abrir pasta downloads" in texto or "abrir downloads" in texto:
        caminho = os.path.join(os.path.expanduser("~"), "Downloads")
        if os.path.exists(caminho):
            subprocess.Popen(["explorer", caminho])
            return "Abrindo a pasta de Downloads."
        else:
            return "Não encontrei a pasta de Downloads."


    # -----------------------------
    # COMANDO NÃO RECONHECIDO
    # -----------------------------
    return "Não reconheci esse comando."
