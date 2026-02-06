# instalador.py
import subprocess
import sys


def instalar_pacote(pacote: str) -> str:
    """
    Instala pacotes Python usando pip.
    """
    if not pacote:
        return "Você não informou o nome do pacote Python."


    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pacote])
        return f"Pacote Python '{pacote}' instalado com sucesso."
    except Exception as e:
        return f"Erro ao instalar o pacote '{pacote}': {e}"



def instalar_programa(programa: str) -> str:
    """
    Instala programas usando o Winget.
    """
    if not programa:
        return "Você não informou o nome do programa para instalar."


    try:
        comando = [
            "winget", "install", programa,
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements"
        ]
        subprocess.run(comando, shell=True)
        return f"Programa '{programa}' enviado para instalação."
    except Exception as e:
        return f"Erro ao instalar o programa '{programa}': {e}"



def verificar_dependencias() -> str:
    """
    Verifica e instala dependências essenciais do APEX.
    """
    dependencias = [
        "sounddevice",
        "soundfile",
        "numpy",
        "pyaudio",
        "opencv-python"
    ]


    resultados = []


    for dep in dependencias:
        try:
            __import__(dep)
            resultados.append(f"{dep}: OK")
        except ImportError:
            resultados.append(instalar_pacote(dep))


    return "\n".join(resultados)
