from .faq_prompt import FAQ_PROMPT
from .oil_advisor_prompt import OIL_ADVISOR_PROMPT
from .routes_maps_prompt import ROUTES_MAPS_PROMPT_COMPLETO
from .business_analyst_prompt import BUSINESS_ANALYST_PROMPT_COMPLETO
from .ranking_sustainable_prompt import RANKING_SUSTAINABLE_PROMPT_COMPLETO

# Arquivo para juntar os prompts e facilitar a importação dos agentes em outros módulos.
PROMPTS = {
    "faq": FAQ_PROMPT,
    "oil_advisor": OIL_ADVISOR_PROMPT,
    "routes_maps": ROUTES_MAPS_PROMPT_COMPLETO,
    "business_analyst": BUSINESS_ANALYST_PROMPT_COMPLETO,
    "ranking_sustainable": RANKING_SUSTAINABLE_PROMPT_COMPLETO
}