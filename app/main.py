from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import validar_config, FRONTEND_DIR
from app.routes import chat, sessions
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Falha na subida se faltar configuração, em vez de quebrar na 1ª requisição."""
    problemas = validar_config()
    if problemas:
        raise RuntimeError("Configuração inválida:\n- " + "\n- ".join(problemas))
    yield

app = FastAPI(
    title="OlivIA",
    description="API de IA multiagente do projeto Olius.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(chat.router)
app.include_router(sessions.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["infra"])
def health() -> dict:
    problemas = validar_config()
    return {
        "status": "ok" if not problemas else problemas,
    }