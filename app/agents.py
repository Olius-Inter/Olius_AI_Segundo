from langchain.agents import create_agent
from app.llms import llm_especialista, llm_rapido
from app.prompts.prompts import PROMPTS
from app.tools.faq_tools import faq_retriever
from app.tools.routes_maps_tools import buscar_locais_proximos, calcular_tempos_deslocamento
from app.tools.business_analyst_tools import business_analyst_tool
from app.tools.ranking_sustainable_tools import ranking_sustainable_tool

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
   tools=[
      business_analyst_tool,
   ]
)

routes_maps_app = create_agent(
   model=llm_especialista,
   system_prompt=PROMPTS["routes_maps"],
   tools=[
      buscar_locais_proximos,
      calcular_tempos_deslocamento
   ]
)

ranking_sustainable_app = create_agent(
   model=llm_especialista,
   system_prompt=PROMPTS["ranking_sustainable"],
   tools=[
      ranking_sustainable_tool,
   ]
)
