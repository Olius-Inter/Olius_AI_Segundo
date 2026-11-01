from app.prompts.orchestrator_prompt import ORCHESTRATOR_PROMPT
from app.prompts.persona_olius import SYSTEM_PERSON

def test_prompt_nao_esta_vazio():
    assert ORCHESTRATOR_PROMPT.strip()

def test_prompt_inclui_persona():
    assert SYSTEM_PERSON.strip() in ORCHESTRATOR_PROMPT

def test_prompt_contem_temas_obrigatorios():
    temas = [
        "usuário",
        "resposta final",
        "especialista",
    ]

    for tema in temas:
        assert tema in ORCHESTRATOR_PROMPT
