"""Regressões de autenticação e abuso, sem rede externa ou inferência paga."""
import asyncio
import importlib.util
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from app import security
from app.schemas import ChatRequest
from app.request_limits import BodyLimitMiddleware
from app import resource_limits as limits

USER = "00000000-0000-0000-0000-000000000001"
SESSION = "00000000-0000-0000-0000-000000000002"


def principal(profile="CITIZENS"):
    return security.UsuarioAutenticado(user_id=USER, session_id=SESSION, user_type=profile)


@pytest.mark.parametrize("payload", [
    {"session_id": SESSION, "pergunta": "x", "user_id": USER},
    {"session_id": "arbitrario", "pergunta": "x"},
    {"session_id": SESSION, "pergunta": "x" * 4001},
])
def test_contrato_recusa_identidade_e_entradas_invalidas(payload):
    with pytest.raises(ValidationError):
        ChatRequest(**payload)


def test_autenticacao_ausente_nao_acessa_core():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(security.exigir_usuario(None))
    assert exc.value.status_code == 401


@pytest.mark.parametrize("status,body,expected", [
    (200, {"userId": USER, "sessionId": SESSION, "userType": "ESTABLISHMENT", "sessionExpiresAt": "2099-01-01T00:00:00Z"}, 200),
    (200, {"userId": USER, "sessionId": SESSION, "userType": "ADMIN", "sessionExpiresAt": "2000-01-01T00:00:00Z"}, 401),
    (200, {"userId": USER, "sessionId": SESSION, "userType": "CITIZENS", "sessionExpiresAt": "2099-01-01T00:00:00"}, 503),
    (200, {"userId": USER}, 503),
    (200, {"userId": USER, "sessionId": SESSION, "userType": "SUPERADMIN", "sessionExpiresAt": "2099-01-01T00:00:00Z"}, 503),
    (200, {"active": True, "user_id": USER, "session_id": SESSION, "user_type": "ADMIN"}, 503),
    (401, {}, 401), (403, {}, 401), (302, {}, 503), (500, {}, 503),
])
def test_core_e_fonte_da_identidade_e_falha_fecha_acesso(monkeypatch, status, body, expected):
    monkeypatch.setenv("CORE_AUTH_URL", "https://core.test.invalid/validate")
    requests = []
    def responder(request):
        requests.append(request)
        return httpx.Response(status, json=body)
    client_class = httpx.AsyncClient
    def client(**kwargs):
        assert kwargs["follow_redirects"] is False and kwargs["trust_env"] is False
        return client_class(transport=httpx.MockTransport(responder), **kwargs)
    monkeypatch.setattr(security.httpx, "AsyncClient", client)
    token = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token-de-teste")
    if expected == 200:
        user = asyncio.run(security.exigir_usuario(token))
        assert str(user.user_id) == USER and user.user_type == "ESTABLISHMENT"
    else:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(security.exigir_usuario(token))
        assert exc.value.status_code == expected
    assert len(requests) == 1
    assert requests[0].headers["authorization"] == "Bearer token-de-teste"
    assert requests[0].url.query == b""


@pytest.mark.parametrize("url", ["", "http://core.test.invalid/auth", "https://u:p@core.test.invalid/auth", "https://core.test.invalid/auth?url=evil"])
def test_configuracao_core_sem_endpoint_inseguro(monkeypatch, url):
    monkeypatch.setenv("CORE_AUTH_URL", url)
    with pytest.raises(ValueError):
        security.auth_url()


def test_monitor_anonimo_e_usuario_comum_nao_recebem_metricas():
    from app.routes.monitor import router
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.get("/api/v1/monitor").status_code == 401
        app.dependency_overrides[security.exigir_usuario] = principal
        assert client.get("/api/v1/monitor").status_code == 403
        app.dependency_overrides[security.exigir_usuario] = lambda: principal("ADMIN")
        response = client.get("/api/v1/monitor")
        assert response.status_code == 200
        assert all("session_id" not in t for t in response.json()["turnos"])


def test_chat_http_usa_apenas_identidade_autenticada(monkeypatch):
    graph = ModuleType("app.graph")
    graph.executar_fluxo_async = AsyncMock(return_value=["Resposta", [], "fim"])
    monkeypatch.setitem(sys.modules, "app.graph", graph)
    path = Path(__file__).parents[1] / "app/routes/chat.py"
    spec = importlib.util.spec_from_file_location("chat_security_test", path)
    chat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(chat)
    @asynccontextmanager
    async def permitida(user_id):
        assert user_id == USER
        yield
    monkeypatch.setattr(chat, "operacao", permitida)
    monkeypatch.setattr(chat, "abrir_turno", lambda: "turno")
    monkeypatch.setattr(chat, "fechar_turno", Mock())
    app = FastAPI()
    app.include_router(chat.router)
    with TestClient(app) as client:
        payload = {"session_id": SESSION, "pergunta": "Como descartar óleo?"}
        assert client.post("/api/v1/chat", json=payload).status_code == 401
        graph.executar_fluxo_async.assert_not_awaited()
        app.dependency_overrides[security.exigir_usuario] = principal
        assert client.post("/api/v1/chat", json={**payload, "user_id": "intruso"}).status_code == 422
        graph.executar_fluxo_async.assert_not_awaited()
        assert client.post("/api/v1/chat", json=payload).status_code == 200
    graph.executar_fluxo_async.assert_awaited_once_with(payload["pergunta"], SESSION, USER)


def test_corpo_em_blocos_excedente_e_recusado_antes_da_aplicacao():
    called, sent = [], []
    async def application(scope, receive, send):
        called.append(True)
    messages = iter([
        {"type": "http.request", "body": b"x" * 20000, "more_body": True},
        {"type": "http.request", "body": b"x" * 20000, "more_body": False},
    ])
    async def receive():
        return next(messages)
    async def send(message):
        sent.append(message)
    middleware = BodyLimitMiddleware(application)
    asyncio.run(middleware({"type": "http", "method": "POST", "headers": []}, receive, send))
    assert not called
    assert sent[0]["status"] == 413
    assert middleware.active == 0


def test_cota_esgotada_retorna_429_sem_reservar_capacidade(monkeypatch):
    collection = Mock()
    collection.update_one.side_effect = DuplicateKeyError("quota")
    monkeypatch.setattr(limits, "_colecao", lambda: collection)
    reservar = Mock()
    monkeypatch.setattr(limits, "_reservar", reservar)
    with pytest.raises(HTTPException) as exc:
        limits._adquirir(USER, "operacao")
    assert exc.value.status_code == 429
    reservar.assert_not_called()


def test_concorrencia_global_esgotada_libera_reserva_usuario(monkeypatch):
    collection = Mock()
    monkeypatch.setattr(limits, "_colecao", lambda: collection)
    monkeypatch.setattr(limits, "_cota", lambda *args: None)
    monkeypatch.setattr(limits, "_reservar", Mock(side_effect=[True] + [False] * limits.GLOBAL_CONCURRENCY))
    with pytest.raises(HTTPException) as exc:
        limits._adquirir(USER, "operacao")
    assert exc.value.status_code == 429
    collection.delete_many.assert_called_once_with({"owner": "operacao"})


def test_reserva_expirada_pode_ser_reaproveitada_e_nao_rouba_ativa():
    collection = Mock()
    now = datetime.now(timezone.utc)
    collection.update_one.side_effect = DuplicateKeyError("busy")
    assert not limits._reservar(collection, "slot:0", "atacante", now)
    assert collection.update_one.call_args.args[0]["expires_at"] == {"$lte": now}
    collection.update_one.side_effect = None
    collection.update_one.return_value = SimpleNamespace(modified_count=1, upserted_id=None)
    assert limits._reservar(collection, "slot:0", "novo", now)


def test_timeout_mantem_reserva_para_trabalho_em_cancelamento(monkeypatch):
    collection = Mock()
    monkeypatch.setattr(limits, "_colecao", lambda: collection)
    monkeypatch.setattr(limits, "_adquirir", lambda *args: None)
    monkeypatch.setattr(limits, "OPERATION_SECONDS", 0.01)
    async def run():
        async with limits.operacao(USER):
            await asyncio.sleep(1)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(run())
    assert exc.value.status_code == 504
    collection.delete_many.assert_not_called()


def test_endpoint_padrao_corresponde_ao_swagger(monkeypatch):
    monkeypatch.delenv("CORE_AUTH_URL", raising=False)
    assert security.auth_url() == "https://tvkgo0evuj.execute-api.us-east-1.amazonaws.com/api/v1/auth/session"
