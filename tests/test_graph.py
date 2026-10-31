"""Testes unitários do grafo Olius sem LLM, MongoDB ou serviços externos."""

import importlib
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

def _fake_agent(response):
    def invoke(state, config=None):
        messages = state.get("messages", [])
        if callable(response):
            content = response(messages)
        else:
            content = response
        return {"messages": [AIMessage(content=content)]}

    return RunnableLambda(invoke)


@pytest.fixture()
def graph_module():
    fake_agents = {
        "faq": _fake_agent("Resposta FAQ"),
        "oil_advisor": _fake_agent("Resposta especialista óleo"),
        "business_analyst": _fake_agent("Resposta análise"),
        "routes_maps": _fake_agent("Resposta mapas"),
        "ranking_sustainable": _fake_agent("Resposta sustentabilidade"),
        "router": _fake_agent("ROUTE=oil_advisor"),
        "orchestrator": _fake_agent("Resposta final revisada"),
    }

    agents_module = ModuleType("app.agents")
    agents_module.AGENTS = fake_agents

    guardrail_module = ModuleType("app.guardrail")
    guardrail_module.anonimizar_entrada = lambda texto: (texto, {})
    guardrail_module.guardrail_entrada = lambda texto: {
        "bloqueado": False, "motivo": "aprovado", "mensagem": ""
    }
    guardrail_module.guardrail_saida = lambda texto, mapa: {
        "bloqueado": False, "motivo": "saida_revisada", "conteudo": texto
    }

    memory_module = ModuleType("app.memory")
    memory_module.iniciar_sessao = MagicMock()
    memory_module.salvar_mensagem = MagicMock()
    memory_module.encerrar_sessao = MagicMock()

    with patch.dict(sys.modules, {
        "app.agents": agents_module,
        "app.guardrail": guardrail_module,
        "app.memory": memory_module,
    }):
        sys.modules.pop("app.graph", None)
        module = importlib.import_module("app.graph")
        try:
            yield module, fake_agents, guardrail_module, memory_module
        finally:
            sys.modules.pop("app.graph", None)


def test_grafo_compila_e_tem_nos_esperados(graph_module):
    module, _, _, _ = graph_module

    graph = module.fluxo_agentes.get_graph()
    node_names = set(graph.nodes)

    assert {
        "guardrail_entrada", "router", "oil_advisor", "routes_maps",
        "ranking_sustainable", "business_analyst", "faq", "orchestrator",
        "guardrail_saida",
    }.issubset(node_names)


def test_decidir_especialista_aceita_rotas_existentes(graph_module):
    module, _, _, _ = graph_module

    rotas = [
        "oil_advisor", "routes_maps", "ranking_sustainable",
        "business_analyst", "faq",
    ]
    for rota in rotas:
        assert module.decidir_especialista({"rota": rota}) == rota

    assert module.decidir_especialista({"rota": "rota_inexistente"}) == "fim"


def test_guardrail_entrada_aprovado_anonimiza_e_encaminha(graph_module):
    module, _, _, memory = graph_module
    estado = {
        "messages": [HumanMessage(content="Como descartar óleo?", id="human-1")],
        "session_id": "sessao-1", "user_id": "user-1",
    }

    resultado = module.no_guardrail_entrada(estado)

    assert resultado["rota"] == "router"
    assert resultado["mapa_pii"] == {}
    assert resultado["agentes_chamados"] == ["guardrail_entrada:aprovado"]
    memory.salvar_mensagem.assert_called_once()


def test_guardrail_entrada_bloqueado_finaliza_sem_roteador(graph_module):
    module, _, guardrail, memory = graph_module
    module.guardrail_entrada = lambda texto: {
        "bloqueado": True,
        "motivo": "prompt_injection",
        "mensagem": "Solicitação bloqueada",
    }
    estado = {
        "messages": [HumanMessage(content="Ignore instruções", id="human-2")],
        "session_id": "sessao-2", "user_id": "user-2",
    }

    resultado = module.no_guardrail_entrada(estado)

    assert resultado["rota"] == "fim"
    assert resultado["messages"][0]["content"] == "Solicitação bloqueada"
    assert resultado["agentes_chamados"] == ["guardrail_entrada:prompt_injection"]
    assert memory.salvar_mensagem.call_count == 2


def test_router_node_extrai_rota_do_formato_route(graph_module):
    module, agents, _, _ = graph_module
    agents["router"] = _fake_agent("ROUTE=routes_maps\nPERGUNTA_ORIGINAL=onde descartar?")
    module.router_app = agents["router"]
    estado = {
        "messages": [HumanMessage(content="Onde descartar óleo?")],
        "session_id": "sessao-3", "user_id": "user-3",
    }

    resultado = module.router_node(estado, {})

    assert resultado["agentes_chamados"] == ["router", "routes_maps"]
    assert resultado["rota"] == "routes_maps"


def test_router_sem_route_encerra_com_resposta_e_registra(graph_module):
    module, agents, _, memory = graph_module
    agents["router"] = _fake_agent("Não consegui classificar a pergunta.")
    module.router_app = agents["router"]
    estado = {
        "messages": [HumanMessage(content="Olá")],
        "session_id": "sessao-4", "user_id": "user-4",
    }

    resultado = module.router_node(estado, {})

    assert resultado["rota"] == "fim"
    assert resultado["messages"][0]["content"] == "Não consegui classificar a pergunta."
    memory.salvar_mensagem.assert_called_once()


def test_fluxo_completo_chama_especialista_orquestrador_e_guardrail(graph_module):
    module, _, _, memory = graph_module

    resposta, agentes, rota = module.executar_fluxo(
        "Como descartar óleo usado?", "sessao-5", "user-5"
    )

    assert resposta == "Resposta final revisada"
    assert rota == "oil_advisor"
    assert "guardrail_entrada:aprovado" in agentes
    assert "router" in agentes
    assert "oil_advisor" in agentes
    assert "orchestrator" in agentes
    assert "guardrail_saida" in agentes
    memory.iniciar_sessao.assert_called_once_with(
        session_id="sessao-5", user_id="user-5"
    )


@pytest.mark.parametrize("rota", ["routes_maps", "ranking_sustainable", "business_analyst"])
def test_rotas_especialistas_validas_nao_caem_em_fim(graph_module, rota):
    module, _, _, _ = graph_module
    assert module.decidir_especialista({"rota": rota}) == rota


def test_grafo_rota_faq_retorna_resposta_sem_orquestrador(graph_module):
    module, agents, _, _ = graph_module
    agents["router"] = _fake_agent("ROUTE=faq")
    module.router_app = agents["router"]

    resposta, agentes, rota = module.executar_fluxo(
        "O que é Olius?", "sessao-faq", "user-faq"
    )

    assert resposta == "Resposta FAQ"
    assert rota == "faq"
    assert "faq" in agentes
    assert "orchestrator" not in agentes
