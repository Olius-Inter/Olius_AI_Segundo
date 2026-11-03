import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock
from contextlib import asynccontextmanager
from app.security import exigir_usuario, UsuarioAutenticado

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.mark.parametrize("resumo", ["Resumo da sessão", ""])
def test_rotas_de_sessao_preservam_usuario_e_encerramento(monkeypatch, resumo):
    memory = ModuleType("app.memory")
    memory.iniciar_sessao = Mock()
    memory.encerrar_sessao = Mock(return_value=resumo)
    monkeypatch.setitem(sys.modules, "app.memory", memory)
    spec = importlib.util.spec_from_file_location("sessions_under_test", Path(__file__).parents[1] / "app/routes/sessions.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    @asynccontextmanager
    async def permitida(user_id):
        yield
    monkeypatch.setattr(module, "operacao", permitida)
    app = FastAPI()
    app.include_router(module.router)
    uid = "00000000-0000-0000-0000-000000000001"
    sid = "00000000-0000-0000-0000-000000000002"
    app.dependency_overrides[exigir_usuario] = lambda: UsuarioAutenticado(user_id=uid, session_id=sid, user_type="CITIZENS")
    with TestClient(app) as client:
        inicio = client.post(f"/sessions/{sid}/iniciar?user_id=intruso")
        fim = client.post(f"/sessions/{sid}/encerrar")
    assert inicio.status_code == 200
    assert inicio.json() == {"session_id": sid, "resumo": None}
    memory.iniciar_sessao.assert_called_once_with(sid, uid)
    assert fim.json() == {"session_id": sid, "resumo": resumo or None}
    memory.encerrar_sessao.assert_called_once_with(sid, uid)
