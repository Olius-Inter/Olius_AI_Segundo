"""Testes unitários de app.tools.mongodb_tools sem MongoDB, Qdrant ou LLM."""

import importlib
import sys
from datetime import datetime
from types import ModuleType
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture
def mongodb_tools(monkeypatch):
    """Importa app.tools.mongodb_tools com app.memory substituído por um mock."""
    memory_module = ModuleType("app.memory")
    memory_module.recuperar_historico = MagicMock(name="recuperar_historico")

    monkeypatch.setitem(sys.modules, "app.memory", memory_module)
    monkeypatch.delitem(sys.modules, "app.tools.mongodb_tools", raising=False)

    return importlib.import_module("app.tools.mongodb_tools")


def executar_tool(modulo, busca, config):
    """Executa a tool diretamente, sem chamar o modelo."""
    return modulo.buscar_historico.invoke(
        {"busca": busca},
        config=config,
    )


def test_buscar_historico_sem_user_id(mongodb_tools):
    config = {"configurable": {}}

    resultado = executar_tool(mongodb_tools, "preferências", config)

    assert resultado == (
        "Não foi possível identificar o usuário para buscar o histórico."
    )


def test_buscar_historico_usa_thread_id(mongodb_tools):
    config = {"configurable": {"thread_id": "usuario-123"}}

    with patch.object(
        mongodb_tools,
        "recuperar_historico",
        return_value=[],
    ) as mock_recuperar:
        resultado = executar_tool(mongodb_tools, "preferências", config)

    mock_recuperar.assert_called_once_with(
        "usuario-123",
        busca="preferências",
        limite=3,
    )
    assert resultado == "Nenhuma conversa anterior relevante encontrada."


def test_buscar_historico_usa_user_id_prioritariamente(mongodb_tools):
    config = {
        "configurable": {
            "user_id": "usuario-1",
            "thread_id": "thread-2",
        }
    }

    with patch.object(
        mongodb_tools,
        "recuperar_historico",
        return_value=[],
    ) as mock_recuperar:
        executar_tool(mongodb_tools, "planos", config)

    mock_recuperar.assert_called_once_with(
        "usuario-1",
        busca="planos",
        limite=3,
    )


def test_buscar_historico_sem_resultados(mongodb_tools):
    config = {"configurable": {"user_id": "usuario-123"}}

    with patch.object(
        mongodb_tools,
        "recuperar_historico",
        return_value=None,
    ):
        resultado = executar_tool(mongodb_tools, "decisões", config)

    assert resultado == "Nenhuma conversa anterior relevante encontrada."


def test_buscar_historico_formata_datetime(mongodb_tools):
    config = {"configurable": {"user_id": "usuario-123"}}
    historico = [
        {
            "iniciada_em": datetime(2026, 10, 20),
            "resumo": "O usuário prefere respostas objetivas.",
        }
    ]

    with patch.object(
        mongodb_tools,
        "recuperar_historico",
        return_value=historico,
    ):
        resultado = executar_tool(mongodb_tools, "preferências", config)

    assert resultado == (
        "[20/10/2026] O usuário prefere respostas objetivas."
    )


def test_buscar_historico_formata_data_como_string(mongodb_tools):
    config = {"configurable": {"user_id": "usuario-123"}}
    historico = [
        {
            "iniciada_em": "2026-09-15T10:30:00",
            "resumo": "O usuário decidiu usar PostgreSQL.",
        }
    ]

    with patch.object(
        mongodb_tools,
        "recuperar_historico",
        return_value=historico,
    ):
        resultado = executar_tool(mongodb_tools, "decisões", config)

    assert resultado == (
        "[2026-09-15] O usuário decidiu usar PostgreSQL."
    )


def test_buscar_historico_formata_multiplos_resultados(mongodb_tools):
    config = {"configurable": {"user_id": "usuario-123"}}
    historico = [
        {
            "iniciada_em": datetime(2026, 10, 20),
            "resumo": "Primeira conversa.",
        },
        {
            "iniciada_em": "2026-10-10",
            "resumo": "Segunda conversa.",
        },
    ]

    with patch.object(
        mongodb_tools,
        "recuperar_historico",
        return_value=historico,
    ):
        resultado = executar_tool(mongodb_tools, "conversas anteriores", config)

    assert resultado == (
        "[20/10/2026] Primeira conversa.\n\n"
        "[2026-10-10] Segunda conversa."
    )


def test_tools_memoria_contem_buscar_historico(mongodb_tools):
    assert mongodb_tools.buscar_historico in mongodb_tools.TOOLS_MEMORIA
    assert len(mongodb_tools.TOOLS_MEMORIA) == 1
