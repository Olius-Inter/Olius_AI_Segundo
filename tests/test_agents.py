from unittest.mock import MagicMock, patch

import importlib
import sys


def test_agents_are_created():
    # Simula dependências externas para não inicializar LLMs ou ferramentas reais.
    with (
        patch("langchain.agents.create_agent") as create_agent,
        patch("langgraph.checkpoint.memory.MemorySaver") as memory_saver,
        patch("app.llms.llm_especialista", MagicMock()),
        patch("app.llms.llm_rapido", MagicMock()),
        patch("app.tools.faq_tools.faq_retriever", MagicMock()),
    ):
        create_agent.side_effect = ["faq_fake", "oil_fake"]

        # Força a execução das instruções do módulo sob teste.
        sys.modules.pop("app.agents", None)
        agents = importlib.import_module("app.agents")

        memory_saver.assert_called_once_with()
        assert agents.router_memory is not None

        assert agents.faq_app == "faq_fake"
        assert agents.oil_advisor_app == "oil_fake"
        assert create_agent.call_count == 2

        calls = create_agent.call_args_list

        assert calls[0].kwargs["system_prompt"] == agents.PROMPTS["faq"]
        assert calls[0].kwargs["tools"] == [agents.faq_retriever]

        assert calls[1].kwargs["system_prompt"] == agents.PROMPTS["oil_advisor"]
