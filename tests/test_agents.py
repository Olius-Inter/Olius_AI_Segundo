from unittest.mock import MagicMock, patch
import importlib
import sys

def test_agents_are_created():
    llms_mock = MagicMock()
    llms_mock.llm_especialista = MagicMock()
    llms_mock.llm_rapido = MagicMock()

    faq_tools_mock = MagicMock()
    faq_tools_mock.faq_retriever = MagicMock()

    with (
        patch("langchain.agents.create_agent") as create_agent,
        patch.dict(
            sys.modules,
            {
                "app.llms": llms_mock,
                "app.tools.faq_tools": faq_tools_mock,
            },
        ),
    ):
        create_agent.side_effect = ["faq_fake", "oil_fake"]
        sys.modules.pop("app.agents", None)

        try:
            agents = importlib.import_module("app.agents")

            assert agents.faq_app == "faq_fake"
            assert agents.oil_advisor_app == "oil_fake"
            assert create_agent.call_count == 2
        finally:
            sys.modules.pop("app.agents", None)