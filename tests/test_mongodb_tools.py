
from datetime import datetime
from unittest.mock import patch

from app.tools.mongodb_tools import buscar_historico, TOOLS_MEMORIA


def executar_tool(busca, config):
    """Executa a tool diretamente, sem chamar o modelo."""
    return buscar_historico.invoke(
        {"busca": busca},
        config=config,
    )


def test_buscar_historico_sem_user_id():
    config = {"configurable": {}}

    resultado = executar_tool("preferências", config)

    assert resultado == (
        "Não foi possível identificar o usuário para buscar o histórico."
    )


def test_buscar_historico_usa_thread_id():
    config = {"configurable": {"thread_id": "usuario-123"}}

    with patch(
        "app.tools.mongodb_tools.recuperar_historico",
        return_value=[],
    ) as mock_recuperar:
        resultado = executar_tool("preferências", config)

    mock_recuperar.assert_called_once_with(
        "usuario-123",
        busca="preferências",
        limite=3,
    )
    assert resultado == "Nenhuma conversa anterior relevante encontrada."


def test_buscar_historico_usa_user_id_prioritariamente():
    config = {
        "configurable": {
            "user_id": "usuario-1",
            "thread_id": "thread-2",
        }
    }

    with patch(
        "app.tools.mongodb_tools.recuperar_historico",
        return_value=[],
    ) as mock_recuperar:
        executar_tool("planos", config)

    mock_recuperar.assert_called_once_with(
        "usuario-1",
        busca="planos",
        limite=3,
    )


def test_buscar_historico_sem_resultados():
    config = {"configurable": {"user_id": "usuario-123"}}

    with patch(
        "app.tools.mongodb_tools.recuperar_historico",
        return_value=None,
    ):
        resultado = executar_tool("decisões", config)

    assert resultado == "Nenhuma conversa anterior relevante encontrada."


def test_buscar_historico_formata_datetime():
    config = {"configurable": {"user_id": "usuario-123"}}
    historico = [
        {
            "iniciada_em": datetime(2026, 10, 20),
            "resumo": "O usuário prefere respostas objetivas.",
        }
    ]

    with patch(
        "app.tools.mongodb_tools.recuperar_historico",
        return_value=historico,
    ):
        resultado = executar_tool("preferências", config)

    assert resultado == (
        "[20/10/2026] O usuário prefere respostas objetivas."
    )


def test_buscar_historico_formata_data_como_string():
    config = {"configurable": {"user_id": "usuario-123"}}
    historico = [
        {
            "iniciada_em": "2026-09-15T10:30:00",
            "resumo": "O usuário decidiu usar PostgreSQL.",
        }
    ]

    with patch(
        "app.tools.mongodb_tools.recuperar_historico",
        return_value=historico,
    ):
        resultado = executar_tool("decisões", config)

    assert resultado == (
        "[2026-09-15] O usuário decidiu usar PostgreSQL."
    )


def test_buscar_historico_formata_multiplos_resultados():
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

    with patch(
        "app.tools.mongodb_tools.recuperar_historico",
        return_value=historico,
    ):
        resultado = executar_tool("conversas anteriores", config)

    assert resultado == (
        "[20/10/2026] Primeira conversa.\n\n"
        "[2026-10-10] Segunda conversa."
    )


def test_tools_memoria_contem_buscar_historico():
    assert buscar_historico in TOOLS_MEMORIA
    assert len(TOOLS_MEMORIA) == 1
