"""Casos de metadados ausentes e coleta sem provedores reais."""
import sys
from types import ModuleType, SimpleNamespace

import pytest
from langchain_core.outputs import LLMResult

from app import observability as obs


@pytest.mark.parametrize("serializado,invocacao,meta,esperado", [
    ({"kwargs": {"model": "models/teste"}}, None, None, "teste"),
    (None, {"model_name": "rapido"}, None, "rapido"),
    (None, None, {"model": "real"}, "real"),
    ({}, {}, {}, "desconhecido"),
])
def test_nome_modelo_em_metadados_alternativos(serializado, invocacao, meta, esperado):
    assert obs._nome_modelo(serializado, invocacao, meta) == esperado


def test_no_do_grafo_encontra_no_externo_e_trata_ausencia():
    assert obs._no_do_grafo({"langgraph_checkpoint_ns": "oil_advisor:abc|model:xyz", "langgraph_node": "model"}) == "oil_advisor"
    assert obs._no_do_grafo({"langgraph_node": "no_customizado"}) == "no_customizado"
    assert obs._no_do_grafo(None) == ""


def test_tokens_em_objeto_e_metadados_legados():
    assert obs._tokens(SimpleNamespace(usage_metadata=SimpleNamespace(input_tokens=3, output_tokens=4))) == (3, 4)
    assert obs._tokens(SimpleNamespace(response_metadata={"token_usage": {"prompt_tokens": 5, "completion_tokens": 6}})) == (5, 6)
    assert obs._tokens(SimpleNamespace()) == (0, 0)


def test_custo_por_alias_e_modelo_nao_tabelado():
    entrada, saida = obs.PRECO_POR_MILHAO["gpt-6-luna"]
    assert obs.custo_usd("provedor/gpt-6-luna-versao", 1_000_000, 1_000_000) == entrada + saida
    assert obs.custo_usd("modelo-sem-preco", 100, 100) == 0


def test_registro_duplicado_ou_sem_turno_nao_cria_chamada(monkeypatch):
    monkeypatch.setattr(obs, "_runs", {})
    monkeypatch.setattr(obs, "_chamadas", [])
    monkeypatch.setattr(obs, "_abertos", {})
    token = obs._turno_atual.set(None)
    try:
        coletor = obs.ColetorChamadas()
        coletor.on_llm_end(LLMResult(generations=[]), run_id="ausente")
        coletor.on_llm_error(RuntimeError("sem chamada"), run_id="ausente")
        coletor.on_chat_model_start(None, [], run_id="fora-turno")
        coletor.on_llm_end(LLMResult(generations=[]), run_id="fora-turno")
        obs.fechar_turno("ausente", "sessao", "faq", "erro")
        assert obs._chamadas == []
    finally:
        obs._turno_atual.reset(token)


def test_ligar_coleta_preserva_callbacks_e_nao_duplica(monkeypatch):
    llms = ModuleType("app.llms")
    existente = object()
    llms.llm_chatgpt = SimpleNamespace(callbacks=[existente])
    llms.llm_groq = None
    llms.llm_rapido = SimpleNamespace(callbacks=[])
    monkeypatch.setitem(sys.modules, "app.llms", llms)
    monkeypatch.setattr(obs, "_ligado", False)
    obs.ligar_coleta()
    obs.ligar_coleta()
    assert llms.llm_chatgpt.callbacks == [existente, obs.coletor]
    assert llms.llm_rapido.callbacks == [obs.coletor]
    monkeypatch.setattr(obs, "_ligado", False)
    obs.ligar_coleta()
    assert llms.llm_rapido.callbacks == [obs.coletor]
