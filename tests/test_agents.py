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

            expected_prompts = {
                "faq_app": "faq",
                "oil_advisor_app": "oil_advisor",
                "business_analyst_app": "business_analyst",
                "routes_maps_app": "routes_maps",
                "ranking_sustainable_app": "ranking_sustainable",
                "router_app": "router",
                "orchestrator_app": "orchestrator",
            }

            for index, (agent_name, prompt_key) in enumerate(
                expected_prompts.items()
            ):
                assert calls[index].kwargs["system_prompt"] == (
                    agents.PROMPTS[prompt_key]
                )

                assert getattr(agents, f"{agent_name}_app") == (
                    fake_agents[index]
                )

            assert calls[0].kwargs["tools"] == [
                faq_tools_mock.faq_retriever
            ]

        finally:
            sys.modules.pop("app.agents", None)
