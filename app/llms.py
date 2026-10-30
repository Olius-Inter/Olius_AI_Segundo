from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from app.config import CHATGPT_API_KEY, GROQ_API_KEY

# Definição dos LLMs utilizados no projeto
llm_chatgpt = ChatOpenAI(
    model="gpt-6-luna",
    reasoning={"effort": "none"},
    temperature=0.7,
    top_p=0.95,
    api_key=CHATGPT_API_KEY,
) if CHATGPT_API_KEY else None

llm_groq = ChatGroq(
   model="openai/gpt-oss-120b",
   temperature=0.7,
   api_key=GROQ_API_KEY
)

llm_especialista = llm_chatgpt.with_fallbacks([llm_groq]) if llm_chatgpt else llm_groq

llm_rapido = ChatGroq(
   model="openai/gpt-oss-120b",
   temperature=0.0,
   api_key=GROQ_API_KEY
)
