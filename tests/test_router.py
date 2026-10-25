from app.prompts.router_prompt import ROUTER_PROMPT
from app.prompts.persona_olius import SYSTEM_PERSON

def test_prompt_nao_esta_vazio():
    assert ROUTER_PROMPT.strip()

def test_prompt_inclui_persona():
    assert SYSTEM_PERSON.strip() in ROUTER_PROMPT

def test_prompt_contem_temas_obrigatorios():
    temas = [
        "usuário",
        "rota",
        "especialista",
        "oil_advisor",
        "maps",
        "sustainability_agent",
        "business_analyst",
        "faq",
    ]

    for tema in temas:
        assert tema in ROUTER_PROMPT
