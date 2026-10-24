from app.prompts.prompts import PROMPTS
from app.prompts.faq_prompt import FAQ_PROMPT
from app.prompts.oil_advisor_prompt import OIL_ADVISOR_PROMPT


def test_prompts_contains_expected_keys():
    assert "faq" in PROMPTS
    assert "oil_advisor" in PROMPTS


def test_prompts_maps_correct_values():
    assert PROMPTS["faq"] == FAQ_PROMPT
    assert PROMPTS["oil_advisor"] == OIL_ADVISOR_PROMPT


def test_prompts_values_are_non_empty_strings():
    assert all(
        isinstance(prompt, str) and prompt.strip()
        for prompt in PROMPTS.values()
    )
