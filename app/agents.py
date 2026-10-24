from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver
from app.llms import llm_especialista, llm_rapido
from app.prompts.ranking_sustainable_prompt import RANKING_SUSTAINABLE_PROMPT_COMPLETO
from app.tools.ranking_sustainable_tools import TOOLS_RANKING_SUSTAINABLE
from app.prompts.business_analyst_prompt import BUSINESS_ANALYST_PROMPT_COMPLETO
from app.tools.business_analyst_tools import TOOLS_BUSINESS_ANALYST
from app.prompts.routes_maps_prompt import ROUTES_MAPS_PROMPT_COMPLETO
from app.tools.routes_maps_tools import TOOLS_ROUTES_MAPS
# from app.tools.financial_tools import TOOLS
# from app.tools.mongodb_tools import TOOLS_MEMORIA
from app.prompts.faq_prompt import FAQ_PROMPT
from app.tools.faq_tools import faq_retriever

router_memory = MemorySaver()

faq_app = create_agent(
    model=llm_rapido,
    system_prompt=FAQ_PROMPT,
    tools=[
        faq_retriever,
        # *TOOLS_MEMORIA
    ]
)

routes_maps_app = create_agent(
   model=llm_especialista,
   system_prompt=ROUTES_MAPS_PROMPT_COMPLETO,
   tools=TOOLS_ROUTES_MAPS
)

business_analyst_app = create_agent(
   model=llm_especialista,
   system_prompt=BUSINESS_ANALYST_PROMPT_COMPLETO,
   tools=TOOLS_BUSINESS_ANALYST
)

ranking_sustainable_app = create_agent(
   model=llm_especialista,
   system_prompt=RANKING_SUSTAINABLE_PROMPT_COMPLETO,
   tools=TOOLS_RANKING_SUSTAINABLE
)
