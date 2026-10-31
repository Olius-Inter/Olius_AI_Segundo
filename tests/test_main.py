import importlib
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch
import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

def _fake_router(path):
    router = APIRouter()

    @router.post(path)
    def rota():
        return {"rota": path}

    return router

@pytest.fixture()
def main_module():
    problemas = []

    config_module = ModuleType("app.config")
    config_module.validar_config = MagicMock(side_effect=lambda: list(problemas))
    config_module.FRONTEND_DIR = Path("frontend-inexistente")

    chat_module = ModuleType("app.routes.chat")
    chat_module.router = _fake_router("/api/v1/chat")

    sessions_module = ModuleType("app.routes.sessions")
    sessions_module.router = _fake_router("/sessions/teste")

    routes_package = ModuleType("app.routes")
    routes_package.chat = chat_module
    routes_package.sessions = sessions_module

    with patch.dict(sys.modules, {
        "app.config": config_module,
        "app.routes": routes_package,
        "app.routes.chat": chat_module,
        "app.routes.sessions": sessions_module,
    }):
        sys.modules.pop("app.main", None)
        module = importlib.import_module("app.main")
        try:
            yield module, config_module, problemas
        finally:
            sys.modules.pop("app.main", None)

def test_app_tem_metadados_esperados(main_module):
    module, _, _ = main_module

    assert module.app.title == "OlivIA"
    assert module.app.version == "0.1.0"

def test_routers_de_chat_e_sessoes_sao_registrados(main_module):
    module, _, _ = main_module

    caminhos = set(module.app.openapi()["paths"])

    assert "/api/v1/chat" in caminhos
    assert "/sessions/teste" in caminhos

def test_health_responde_ok(main_module):
    module, _, _ = main_module

    with TestClient(module.app) as client:
        resposta = client.get("/health")

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"

def test_rota_inexistente_retorna_404(main_module):
    module, _, _ = main_module

    with TestClient(module.app) as client:
        resposta = client.get("/rota-que-nao-existe")

    assert resposta.status_code == 404

def test_rotas_dos_routers_respondem(main_module):
    module, _, _ = main_module

    with TestClient(module.app) as client:
        assert client.post("/api/v1/chat").json() == {"rota": "/api/v1/chat"}
        assert client.post("/sessions/teste").json() == {"rota": "/sessions/teste"}

def test_lifespan_valida_config_na_subida(main_module):
    module, config, _ = main_module

    with TestClient(module.app): pass

    config.validar_config.assert_called()

def test_lifespan_aborta_subida_com_config_invalida(main_module):
    module, _, problemas = main_module
    problemas.extend(["Variável ausente no .env: GROQ_API_KEY"])

    with pytest.raises(RuntimeError) as erro:
        with TestClient(module.app):
            pass

    assert "Configuração inválida" in str(erro.value)
    assert "GROQ_API_KEY" in str(erro.value)

def test_cors_libera_origem_externa(main_module):
    module, _, _ = main_module

    with TestClient(module.app) as client:
        resposta = client.get("/health", headers={"Origin": "http://localhost:8000"})

    assert resposta.headers["access-control-allow-origin"] in ("*", "http://localhost:8000")

def test_cors_responde_preflight(main_module):
    module, _, _ = main_module

    with TestClient(module.app) as client:
        resposta = client.options(
            "/api/v1/chat",
            headers={
                "Origin": "http://localhost:8000",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert resposta.status_code == 200
    assert "POST" in resposta.headers["access-control-allow-methods"]
