import importlib
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch
import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from app.routes.monitor import router as monitor_router
from app.monitor_access import exigir_sessao_monitor

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
    config_module.CORS_ORIGINS = ["http://localhost:8000"]

    chat_module = ModuleType("app.routes.chat")
    chat_module.router = _fake_router("/api/v1/chat")

    sessions_module = ModuleType("app.routes.sessions")
    sessions_module.router = _fake_router("/sessions/teste")

    monitor_module = ModuleType("app.routes.monitor")
    monitor_module.router = monitor_router

    routes_package = ModuleType("app.routes")
    routes_package.chat = chat_module
    routes_package.sessions = sessions_module
    routes_package.monitor = monitor_module

    with patch.dict(sys.modules, {
        "app.config": config_module,
        "app.routes": routes_package,
        "app.routes.chat": chat_module,
        "app.routes.sessions": sessions_module,
        "app.routes.monitor": monitor_module,
    }):
        sys.modules.pop("app.main", None)
        module = importlib.import_module("app.main")
        module.app.dependency_overrides[exigir_sessao_monitor] = lambda: None
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


def test_monitor_retorna_dados_antes_dos_arquivos_estaticos(main_module):
    module, _, _ = main_module
    with TestClient(module.app) as client:
        resposta = client.get("/api/v1/monitor")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("application/json")
    assert set(resposta.json()) == {
        "slo", "resumo", "serie_latencia", "serie_custo", "por_modelo", "por_rota", "turnos", "erros_modelo",
        "por_agente", "por_transicao",
    }

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


@pytest.mark.parametrize("caminho,conteudo", [
    ("/", "Acesse o monitor"),
    ("/monitor", "Acesse o monitor"),
    ("/monitor.html", "Acesse o monitor"),
])
def test_monitor_principal_e_servido(main_module, caminho, conteudo):
    module, _, _ = main_module
    with TestClient(module.app) as client:
        resposta = client.get(caminho)
    assert resposta.status_code == 200
    assert conteudo in resposta.text


def test_raiz_redireciona_para_monitor(main_module):
    module, _, _ = main_module
    with TestClient(module.app) as client:
        resposta = client.get("/", follow_redirects=False)
    assert resposta.status_code == 307
    assert resposta.headers["location"] == "/monitor"


def test_cors_recusa_origem_nao_autorizada(main_module):
    module, _, _ = main_module
    with TestClient(module.app) as client:
        resposta = client.options("/api/v1/chat", headers={
            "Origin": "https://origem-nao-autorizada.invalid",
            "Access-Control-Request-Method": "POST",
        })
    assert resposta.status_code == 400
    assert "access-control-allow-origin" not in resposta.headers


def test_monitor_abre_graficos_apenas_com_sessao(main_module, monkeypatch):
    module, _, _ = main_module
    with TestClient(module.app) as client:
        entrada = client.get("/monitor")
        assert "Acesse o monitor" in entrada.text
        assert "Resumo do monitor" not in entrada.text
        assert entrada.headers["cache-control"] == "no-store"
        assert 'src="/monitor/olius-logo.png"' in entrada.text
        logo = client.get("/monitor/olius-logo.png")
        assert logo.status_code == 200
        assert logo.headers["content-type"] == "image/png"
        assert logo.content.startswith(b"\x89PNG\r\n\x1a\n")

        monkeypatch.setattr(module, "tem_sessao_monitor", lambda request: True)
        painel = client.get("/monitor")
        assert "Resumo do monitor" in painel.text
        assert "Acesse o monitor" not in painel.text
        assert painel.headers["cache-control"] == "no-store"
