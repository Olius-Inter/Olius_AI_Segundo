from app.prompts.oil_advisor_prompt import OIL_ADVISOR_PROMPT
from app.prompts.persona_olius import SYSTEM_PERSON

def test_prompt_nao_esta_vazio():
    assert OIL_ADVISOR_PROMPT.strip()

def test_prompt_inclui_persona():
    assert SYSTEM_PERSON.strip() in OIL_ADVISOR_PROMPT

def test_prompt_contem_temas_obrigatorios():
    temas = [
        "óleo",
    ]

    for tema in temas:
        assert tema in OIL_ADVISOR_PROMPT

def test_prompt_orienta_adaptacao_ao_publico():
    assert "cidadão" in OIL_ADVISOR_PROMPT
    assert "estabelecimento" in OIL_ADVISOR_PROMPT
    assert "B2B" in OIL_ADVISOR_PROMPT
    assert "B2C" in OIL_ADVISOR_PROMPT