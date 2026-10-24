from unittest.mock import MagicMock, patch
import importlib
import sys

def test_agents_are_created():
    langchain_agents_mock = MagicMock()
    langchain_agents_mock.create_agent.side_effect = [
        "faq_fake",
        "oil_fake",
        "business_fake",
        "routes_fake",
        "ranking_fake",
    ]

    llms_mock = MagicMock()
    llms_mock.llm_especialista = MagicMock()
    llms_mock.llm_rapido = MagicMock()

    faq_tools_mock = MagicMock()
    faq_tools_mock.faq_retriever = MagicMock()

    with patch.dict(
        sys.modules,
        {
            "langchain.agents": langchain_agents_mock,
            "app.llms": llms_mock,
            "app.tools.faq_tools": faq_tools_mock,
        },
    ):
        sys.modules.pop("app.agents", None)

        try:
            agents = importlib.import_module("app.agents")

            assert agents.faq_app == "faq_fake"
            assert agents.oil_advisor_app == "oil_fake"

            create_agent = langchain_agents_mock.create_agent
            assert create_agent.call_count == 5

            calls = create_agent.call_args_list

            assert calls[0].kwargs["system_prompt"] == agents.PROMPTS["faq"]
            assert calls[0].kwargs["tools"] == [
                faq_tools_mock.faq_retriever
            ]

            assert calls[1].kwargs["system_prompt"] == agents.PROMPTS[
                "oil_advisor"
            ]

            for index, name, expected, tools in (
                (2, "business_analyst", "business_fake", agents.TOOLS_BUSINESS_ANALYST),
                (3, "routes_maps", "routes_fake", agents.TOOLS_ROUTES_MAPS),
                (4, "ranking_sustainable", "ranking_fake", agents.TOOLS_RANKING_SUSTAINABLE),
            ):
                assert calls[index].kwargs["system_prompt"] == agents.PROMPTS[name]
                assert calls[index].kwargs["tools"] == tools
                assert getattr(agents, name + "_app") == expected

        finally:
            sys.modules.pop("app.agents", None)
