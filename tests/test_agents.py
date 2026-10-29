import importlib
import sys
from unittest.mock import MagicMock, patch

def test_agents_are_created():
    agent_names = [
        "faq",
        "oil_advisor",
        "business_analyst",
        "routes_maps",
        "ranking_sustainable",
        "router",
        "orchestrator",
    ]
    
    agents_with_memory = agent_names[:5]

    langchain_agents_mock = MagicMock()
    langchain_agents_mock.create_agent.side_effect = [
        f"{name}_fake" for name in agent_names
    ]

    llms_mock = MagicMock()
    llms_mock.llm_especialista = MagicMock(name="llm_especialista")
    llms_mock.llm_rapido = MagicMock(name="llm_rapido")

    faq_tools_mock = MagicMock()
    faq_tools_mock.faq_retriever = MagicMock(name="faq_retriever")

    mongodb_tools_mock = MagicMock()
    buscar_historico_mock = MagicMock(name="buscar_historico")
    mongodb_tools_mock.TOOLS_MEMORIA = [buscar_historico_mock]

    modules_mock = {
        "langchain.agents": langchain_agents_mock,
        "app.llms": llms_mock,
        "app.tools.faq_tools": faq_tools_mock,
        "app.tools.mongodb_tools": mongodb_tools_mock,
    }

    with patch.dict(sys.modules, modules_mock):
        sys.modules.pop("app.agents", None)

        try:
            agents = importlib.import_module("app.agents")

            create_agent = langchain_agents_mock.create_agent
            calls = create_agent.call_args_list

            assert create_agent.call_count == len(agent_names)

            for name, call in zip(agent_names, calls):
                assert call.kwargs["system_prompt"] == agents.PROMPTS[name]

            for name, call in zip(agent_names, calls):
                tools = call.kwargs.get("tools", [])
                if name in agents_with_memory:
                    assert buscar_historico_mock in tools
                    assert mongodb_tools_mock.TOOLS_MEMORIA not in tools
                else:
                    assert tools == []

            faq_call = calls[0]
            assert faq_tools_mock.faq_retriever in faq_call.kwargs["tools"]

            for name in agent_names:
                assert getattr(agents, f"{name}_app") == f"{name}_fake"

        finally:
            sys.modules.pop("app.agents", None)
