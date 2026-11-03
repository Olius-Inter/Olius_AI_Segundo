import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest
import langchain_openai
import langchain_groq


@pytest.mark.parametrize("chave", ["test-key", None])
def test_modelos_usam_configuracao_e_fallback_sem_rede(monkeypatch, chave):
    config = ModuleType("app.config")
    config.CHATGPT_API_KEY = chave
    config.GROQ_API_KEY = "test-groq-key"
    monkeypatch.setitem(sys.modules, "app.config", config)
    openai = Mock()
    groq = Mock()
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", openai)
    monkeypatch.setattr(langchain_groq, "ChatGroq", groq)
    spec = importlib.util.spec_from_file_location("llms_under_test", Path(__file__).parents[1] / "app/llms.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert groq.call_count == 2
    if chave:
        openai.assert_called_once()
        assert openai.call_args.kwargs["api_key"] == chave
        openai.return_value.with_fallbacks.assert_called_once_with([groq.return_value])
    else:
        openai.assert_not_called()
        assert module.llm_chatgpt is None
        assert module.llm_especialista is groq.return_value
