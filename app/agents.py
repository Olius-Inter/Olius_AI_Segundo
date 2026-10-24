from langchain.agents import create_agent
from app.llms import llm_especialista, llm_rapido
from app.prompts.prompts import PROMPTS
from app.tools.faq_tools import faq_retriever

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