from prompts.faq_prompt import FAQ_PROMPT
from prompts.router_prompt import ROUTER_PROMPT
from prompts.orchestrator_prompt import ORCHESTRATOR_PROMPT
from prompts.maps_prompt import MAPS_PROMPT
from prompts.business_analyst_prompt import BUSINESS_ANALYST_PROMPT
from prompts.sustainability_agent_prompt import SUSTAINABILITY_AGENT_PROMPT
from prompts.oil_advisor_prompt import OIL_ADVISOR_PROMPT

# Arquivo para juntar os prompts e facilitar a importação dos agentes em outros módulos.
PROMPTS = {
    "faq": FAQ_PROMPT,
    "router": ROUTER_PROMPT,
    "orchestrator": ORCHESTRATOR_PROMPT,
    "maps": MAPS_PROMPT,
    "business_analyst": BUSINESS_ANALYST_PROMPT,
    "sustainability_agent": SUSTAINABILITY_AGENT_PROMPT,
    "oil_advisor": OIL_ADVISOR_PROMPT
}