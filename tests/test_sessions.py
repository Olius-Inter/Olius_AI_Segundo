import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

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
    app = FastAPI()
    app.include_router(module.router)
    with TestClient(app) as client:
        assert client.post("/sessions/s1/iniciar").status_code == 422
        inicio = client.post("/sessions/s1/iniciar?user_id=u1")
        fim = client.post("/sessions/s1/encerrar")
    assert inicio.status_code == 200
    assert inicio.json() == {"session_id": "s1", "resumo": None}
    memory.iniciar_sessao.assert_called_once_with("s1", "u1")
    assert fim.json() == {"session_id": "s1", "resumo": resumo or None}
    memory.encerrar_sessao.assert_called_once_with("s1")
