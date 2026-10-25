from langchain.agents import create_agent
from app.llms import llm_especialista, llm_rapido
from app.prompts.prompts import PROMPTS
from app.tools.faq_tools import faq_retriever
from app.tools.routes_maps_tools import TOOLS_ROUTES_MAPS
from app.tools.business_analyst_tools import TOOLS_BUSINESS_ANALYST
from app.tools.ranking_sustainable_tools import TOOLS_RANKING_SUSTAINABLE

faq_app = create_agent(
    model=llm_rapido,
    system_prompt=PROMPTS["faq"],
    tools=[
        faq_retriever,
        # *TOOLS_MEMORIA
    ]
)

orquestrator_app = create_agent(
   model=llm_rapido,
   system_prompt=PROMPTS["orchestrator"]
)

maps_app = create_agent(
   model=llm_especialista,
   system_prompt=PROMPTS["maps"]
)

business_analyst_app = create_agent(
   model=llm_especialista,
   system_prompt=PROMPTS["business_analist"]
)

sustainability_agent_app = create_agent(
   model=llm_especialista,
   system_prompt=PROMPTS["sustainability_agent"]
)

ranking_sustainable_app = create_agent(
   model=llm_especialista,
   system_prompt=PROMPTS["ranking_sustainable"],
   tools=TOOLS_RANKING_SUSTAINABLE,
)
