"""Validação de configuração sem ler .env ou acessar provedores de IA."""
import importlib.util
from pathlib import Path

import dotenv
import pytest


@pytest.fixture
def config(monkeypatch, tmp_path):
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setenv("CHATGPT_API_KEY", "test-chatgpt-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    path = Path(__file__).resolve().parents[1] / "app" / "config.py"
    spec = importlib.util.spec_from_file_location("chatbot_config_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    pdf = tmp_path / "faq.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(module, "FAQ_PDF_PATH", pdf)
    return module


def test_valid_configuration_has_no_problems(config):
    assert config.validar_config() == []


@pytest.mark.parametrize("missing", [("GROQ_API_KEY",), ("DATABASE_URL",), ("GROQ_API_KEY", "DATABASE_URL")])
def test_missing_keys_are_reported(config, monkeypatch, missing):
    for name in missing:
        monkeypatch.setitem(config.OBRIGATORIAS, name, "")

    assert config.validar_config() == [
        f"Variável ausente no .env: {name}" for name in missing
    ]


def test_missing_faq_is_reported(config):
    config.FAQ_PDF_PATH.unlink()

    assert config.validar_config() == [
        f"PDF do FAQ não encontrado em: {config.FAQ_PDF_PATH}"
    ]


def test_all_configuration_problems_are_reported_together(config, monkeypatch):
    monkeypatch.setattr(config, "OBRIGATORIAS", {"GROQ_API_KEY": None, "DATABASE_URL": ""})
    config.FAQ_PDF_PATH.unlink()

    assert config.validar_config() == [
        "Variável ausente no .env: GROQ_API_KEY",
        "Variável ausente no .env: DATABASE_URL",
        f"PDF do FAQ não encontrado em: {config.FAQ_PDF_PATH}",
    ]
