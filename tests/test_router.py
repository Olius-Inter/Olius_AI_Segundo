from app.prompts.router_prompt import ROUTER
from app.prompts.persona_olius import SYSTEM_PERSON

def test_prompt_nao_esta_vazio():
    assert ROUTER.strip()

def test_prompt_inclui_persona():
    assert SYSTEM_PERSON.strip() in ROUTER

def test_prompt_contem_temas_obrigatorios():
    temas = [
        "usuário",
        "rota",
        "especialista",
        "oil_advisor",
        "routes_maps",
        "ranking_sustainable",
        "business_analyst",
        "faq",
        "roteador"
    ]

    for tema in temas:
        assert tema in ROUTER
