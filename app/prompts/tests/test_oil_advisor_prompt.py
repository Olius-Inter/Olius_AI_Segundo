from oil_advisor_prompt import OIL_ADVISOR_PROMPT
from persona_olius import SYSTEM_PERSON

def test_prompt_nao_esta_vazio():
    assert OIL_ADVISOR_PROMPT.strip()

def test_prompt_inclui_persona():
    assert SYSTEM_PERSON.strip() in OIL_ADVISOR_PROMPT

def test_prompt_contem_temas_obrigatorios():
    temas = [
        "Gestão de óleo",
        "Consumo consciente",
        "Descarte correto",
        "Reciclagem e sustentabilidade",
    ]

    for tema in temas:
        assert tema in OIL_ADVISOR_PROMPT

def test_prompt_orienta_adaptacao_ao_publico():
    assert "consumidores" in OIL_ADVISOR_PROMPT
    assert "empresas" in OIL_ADVISOR_PROMPT