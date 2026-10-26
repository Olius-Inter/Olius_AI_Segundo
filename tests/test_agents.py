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

    fake_agents = [f"{name}_fake" for name in agent_names]

    langchain_agents_mock = MagicMock()
    langchain_agents_mock.create_agent.side_effect = fake_agents

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

            create_agent = langchain_agents_mock.create_agent
            calls = create_agent.call_args_list

            assert create_agent.call_count == len(agent_names)

            expected_prompt_keys = {
                "faq",
                "oil_advisor",
                "business_analyst",
                "routes_maps",
                "ranking_sustainable",
                "router",
                "orchestrator",
            }

            assert create_agent.call_count == len(expected_prompt_keys)

            actual_prompts = [
                call.kwargs["system_prompt"]
                for call in calls
            ]

            expected_prompts = [
                agents.PROMPTS[key]
                for key in expected_prompt_keys
            ]

            assert sorted(actual_prompts) == sorted(expected_prompts)

        finally:
            sys.modules.pop("app.agents", None)
