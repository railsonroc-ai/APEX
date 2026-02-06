# apex_nle.py
import re


# Palavras que não influenciam o comando e devem ser removidas
STOPWORDS = [
    "apex", "por favor", "porfavor", "pode", "poderia", "você", "voce",
    "pra mim", "para mim", "aí", "ai", "mano", "rapidinho", "por gentileza",
    "faz", "faça", "faca", "me", "diz", "diga", "tipo", "assim", "por", "favor"
]


def limpar_texto(texto: str) -> str:
    """
    Remove palavras irrelevantes e normaliza o texto.
    """
    texto = texto.lower().strip()


    for sw in STOPWORDS:
        texto = texto.replace(sw, " ")


    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()



def interpretar_comando(texto: str) -> str:
    """
    Interpreta frases naturais e converte para comandos que o APEX entende.
    Se não encontrar intenção clara, devolve o texto original.
    """
    original = texto.lower().strip()
    texto = limpar_texto(original)


    if not texto:
        return original


    # -------------------------
    # ABRIR YOUTUBE
    # -------------------------
    if "youtube" in texto:
        return "abrir youtube"


    # -------------------------
    # ABRIR NAVEGADOR / CHROME
    # -------------------------
    if any(p in texto for p in ["navegador", "internet", "chrome", "google"]):
        if "chrome" in texto:
            return "abrir navegador chrome"
        return "abrir navegador"


    # -------------------------
    # ABRIR VS CODE
    # -------------------------
    if any(p in texto for p in ["vs code", "vscode", "visual studio code"]):
        return "abrir vs code"


    # -------------------------
    # PERGUNTAR HORAS
    # -------------------------
    if "hora" in texto or "horas" in texto:
        return "que horas são"


    # -------------------------
    # PESQUISAR NA INTERNET
    # -------------------------
    for gatilho in ["pesquisar", "pesquise", "procure", "busque", "buscar"]:
        if gatilho in texto:
            termo = texto.split(gatilho, 1)[-1].strip()
            if termo:
                return f"pesquisar por {termo}"
            return "pesquisar por"


    # -------------------------
    # CRIAR COMANDO PERSONALIZADO
    # -------------------------
    if "criar comando" in original:
        return original


    # -------------------------
    # SE NÃO ENTENDER, DEVOLVE O TEXTO ORIGINAL
    # -------------------------
    return original
