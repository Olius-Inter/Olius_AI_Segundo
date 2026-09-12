import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"

FAQ_PDF_PATH = DATA_DIR / "faq.pdf"

load_dotenv(BASE_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

OBRIGATORIAS = {
    "GEMINI_API_KEY": GEMINI_API_KEY,
    "GROQ_API_KEY": GROQ_API_KEY,
}

def validar_config() -> list[str]:
    """Devolve a lista de problemas de configuração (retorno vazio = tudo certo)."""
    problemas = []
    for nome, valor in OBRIGATORIAS.items():
        if not valor:
            problemas.append(f"Variável ausente no .env: {nome}")
    if not FAQ_PDF_PATH.exists():
        problemas.append(f"PDF do FAQ não encontrado em: {FAQ_PDF_PATH}")
    return problemas

# Testes
print(validar_config())
print("GEMINI:", bool(GEMINI_API_KEY))
print("GROQ:", bool(GROQ_API_KEY))
print("BASE_DIR:", bool(BASE_DIR))
print("APP_DIR:", bool(APP_DIR))
print("DATA_DIR:", bool(DATA_DIR))
print(".env:", (BASE_DIR / ".env").exists())