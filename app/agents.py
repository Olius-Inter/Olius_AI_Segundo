from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver
from app.llms import llm_especialista, llm_rapido
from app.prompts import PROMPTS
# from app.tools.financial_tools import TOOLS
# from app.tools.mongodb_tools import TOOLS_MEMORIA
# from app.tools.faq_tools import faq_retriever

router_memory = MemorySaver()

router_app = create_agent(
   model=llm_rapido,
   system_prompt=PROMPTS["router"],
   checkpointer=router_memory,
#    tools=TOOLS_MEMORIA
)

faq_app = create_agent(
    model=llm_rapido,
    system_prompt=PROMPTS["faq"],
    tools=[
        # faq_retriever,
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

oil_advisor_app = create_agent(
    model=llm_especialista,
    system_prompt=PROMPTS["oil_advisor"]
)