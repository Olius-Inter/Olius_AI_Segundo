from .faq_prompt import FAQ_PROMPT
from .oil_advisor_prompt import OIL_ADVISOR_PROMPT

# Arquivo para juntar os prompts e facilitar a importação dos agentes em outros módulos.
PROMPTS = {
    "faq": FAQ_PROMPT,
    "oil_advisor": OIL_ADVISOR_PROMPT
}