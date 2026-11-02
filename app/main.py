from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.config import validar_config, CORS_ORIGINS
from app.routes import chat, sessions, monitor
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
app.include_router(monitor.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

@app.get("/health", tags=["infra"])
def health() -> dict:
    problemas = validar_config()
    return {
        "status": "ok" if not problemas else problemas,
    }


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/", response_class=RedirectResponse, include_in_schema=False)
def inicio() -> RedirectResponse:
    return RedirectResponse(url="/monitor")


@app.get("/monitor", response_class=FileResponse, include_in_schema=False)
def monitor_principal() -> FileResponse:
    """Abre o monitor principal."""
    return FileResponse(FRONTEND_DIR / "monitor.html")


# As rotas de API precisam preceder a montagem na raiz.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
