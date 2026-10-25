from app.prompts.router_prompt import ROUTER_PROMPT
from app.prompts.orchestrator_prompt import ORCHESTRATOR_PROMPT
from .faq_prompt import FAQ_PROMPT
from .oil_advisor_prompt import OIL_ADVISOR_PROMPT
from .routes_maps_prompt import ROUTES_MAPS_PROMPT
from .business_analyst_prompt import BUSINESS_ANALYST_PROMPT
from .ranking_sustainable_prompt import RANKING_SUSTAINABLE_PROMPT

# Arquivo para juntar os prompts e facilitar a importação dos agentes em outros módulos.
PROMPTS = {
    "router": ROUTER_PROMPT,
    "orchestrator": ORCHESTRATOR_PROMPT,
    "faq": FAQ_PROMPT,
    "oil_advisor": OIL_ADVISOR_PROMPT,
    "routes_maps": ROUTES_MAPS_PROMPT,
    "business_analyst": BUSINESS_ANALYST_PROMPT,
    "ranking_sustainable": RANKING_SUSTAINABLE_PROMPT
}