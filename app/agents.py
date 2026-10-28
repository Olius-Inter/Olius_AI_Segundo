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
    ]
)

oil_advisor_app = create_agent(
   model=llm_especialista,
   system_prompt=PROMPTS["oil_advisor"]
)

business_analyst_app = create_agent(
   model=llm_especialista,
   system_prompt=PROMPTS["business_analyst"],
   tools=TOOLS_BUSINESS_ANALYST,
)

routes_maps_app = create_agent(
   model=llm_especialista,
   system_prompt=PROMPTS["routes_maps"],
   tools=TOOLS_ROUTES_MAPS,
)

ranking_sustainable_app = create_agent(
   model=llm_especialista,
   system_prompt=PROMPTS["ranking_sustainable"],
   tools=TOOLS_RANKING_SUSTAINABLE,
)

router_app = create_agent(
   model=llm_rapido,
   system_prompt=PROMPTS["router"]
)

orchestrator_app = create_agent(
   model=llm_rapido,
   system_prompt=PROMPTS["orchestrator"]
)

# Dicionário para juntar os agentes e facilitar a importação dos agentes em outros módulos.
AGENTS = {
   "faq": faq_app,
   "oil_advisor": oil_advisor_app,
   "business_analyst": business_analyst_app,
   "routes_maps": routes_maps_app,
   "ranking_sustainable": ranking_sustainable_app,
   "router": router_app,
   "orchestrator": orchestrator_app
}