"""Valida o monitor sem chamar modelos, bancos ou serviços externos."""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from app import observabilidade as obs
from app.routes.monitor import montar_painel
from app.schemas import ChatRequest


@pytest.fixture(autouse=True)
def registros_isolados(monkeypatch):
    for nome, valor in (("_turnos", []), ("_chamadas", []), ("_abertos", {}), ("_runs", {}), ("_erros_modelo", []), ("_falhas_primarias", {}), ("_em_andamento", 0)):
        monkeypatch.setattr(obs, nome, valor)
    monkeypatch.setattr(obs, "ligar_coleta", lambda: None)
    token = obs._turno_atual.set(None)
    yield
    obs._turno_atual.reset(token)


def test_monitor_vazio():
    painel = montar_painel()
    assert painel["resumo"]["turnos"] == 0
    assert painel["resumo"]["custo_usd"] == 0
    assert painel["resumo"]["slo_ok"] is True
    assert painel["serie_latencia"] == []
    assert painel["por_modelo"] == []


def test_coleta_tokens_custo_e_latencia(monkeypatch):
    tempos = iter([0, 1, 3, 4])
    monkeypatch.setattr(obs.time, "perf_counter", lambda: next(tempos))
    turno = obs.abrir_turno()
    coletor = obs.ColetorChamadas()
    coletor.on_chat_model_start(
        {"kwargs": {"model": "gpt-6-luna"}}, [], run_id="modelo-1",
        metadata={"langgraph_node": "oil_advisor"},
    )
    mensagem = AIMessage(content="ok", usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150})
    coletor.on_llm_end(LLMResult(generations=[[ChatGeneration(message=mensagem)]]), run_id="modelo-1")
    obs.fechar_turno(turno, "sessao", "oil_advisor", "ok")
    painel = montar_painel()
    assert painel["resumo"]["tokens_total"] == 150
    assert painel["turnos"][0]["latencia_ms"] == 4000
    assert painel["por_modelo"][0]["latencia_media_ms"] == 2000
    assert painel["turnos"][0]["custo_usd"] == pytest.approx(0.000035)
    assert painel["serie_custo"][0]["custo_acumulado_usd"] == pytest.approx(0.000035)
    assert painel["resumo"]["em_andamento"] == 0


def test_erros_bloqueios_p95_e_limite_de_historico():
    for status in ("ok", "erro", "bloqueado"):
        turno = obs.abrir_turno()
        obs.fechar_turno(turno, "sessao", "faq", status)
    painel = montar_painel()
    assert painel["resumo"]["taxa_erro"] == pytest.approx(1 / 3, abs=0.0001)
    assert painel["resumo"]["bloqueios"] == 1
    assert painel["resumo"]["slo_ok"] is False
    assert painel["por_rota"][0]["erros"] == 1
    for _ in range(55):
        turno = obs.abrir_turno()
        obs.fechar_turno(turno, "sessao", "faq", "ok")
    assert len(obs.listar_turnos()) == obs.LIMITE_TURNOS


@pytest.mark.parametrize("resultado,status,rota", [
    (["Resposta", ["guardrail_entrada:aprovado", "faq"], "faq"], "ok", "faq"),
    (["Bloqueado", ["guardrail_entrada:fora_escopo"], "fim"], "bloqueado", "guardrail_entrada"),
    (["Resposta", ["guardrail_entrada:prompt_injection", "guardrail_entrada:aprovado", "router", "oil_advisor", "orchestrator", "guardrail_saida"], "oil_advisor"], "ok", "oil_advisor"),
    (["Bloqueado", ["guardrail_entrada:aprovado", "router", "faq", "guardrail_entrada:prompt_injection"], "fim"], "bloqueado", "guardrail_entrada"),
    (["Olá", ["guardrail_entrada:aprovado", "router"], "fim"], "ok", "router"),
    (RuntimeError("erro simulado"), "erro", "—"),
])
def test_chat_registra_turno_mesmo_com_excecao(monkeypatch, resultado, status, rota):
    graph = ModuleType("app.graph")
    graph.executar_fluxo = Mock(side_effect=resultado) if isinstance(resultado, Exception) else Mock(return_value=resultado)
    monkeypatch.setitem(sys.modules, "app.graph", graph)
    spec = importlib.util.spec_from_file_location("chat_monitor_test", Path(__file__).parents[1] / "app/routes/chat.py")
    chat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(chat)
    pedido = ChatRequest(pergunta="Teste", session_id="sessao", user_id="usuario")
    if status == "erro":
        with pytest.raises(RuntimeError, match="erro simulado"):
            chat.conversar(pedido)
    else:
        assert chat.conversar(pedido).resposta == resultado[0]
    assert obs.listar_turnos()[0]["status"] == status
    assert obs.listar_turnos()[0]["rota"] == rota
    assert obs.situacao()["em_andamento"] == 0


def _iniciar_chamada(coletor, modelo, run_id, no="oil_advisor", parent="tentativa-1"):
    coletor.on_chat_model_start(
        {"kwargs": {"model": modelo}}, [], run_id=run_id, parent_run_id=parent,
        metadata={"langgraph_node": no},
    )


def _finalizar_chamada(coletor, run_id):
    coletor.on_llm_end(LLMResult(generations=[[ChatGeneration(message=AIMessage(content="ok"))]]), run_id=run_id)


def test_faq_e_groq_sem_falha_primaria_nao_sao_fallbacks():
    obs.abrir_turno()
    coletor = obs.ColetorChamadas()
    _iniciar_chamada(coletor, "openai/gpt-oss-120b", "faq", no="faq")
    _finalizar_chamada(coletor, "faq")
    _iniciar_chamada(coletor, "openai/gpt-oss-120b", "direto")
    _finalizar_chamada(coletor, "direto")
    assert montar_painel()["resumo"]["fallbacks"] == 0


def test_fallback_exige_falha_primaria_da_mesma_tentativa_e_turno(caplog, monkeypatch):
    monkeypatch.setenv("CHATGPT_API_KEY", "sk-teste-secreto")
    turno = obs.abrir_turno()
    coletor = obs.ColetorChamadas()
    erro = RuntimeError("erro")
    erro.body = {"message": "Model unavailable; credencial sk-teste-secreto", "code": "model_not_found", "param": "model"}
    erro.status_code = 404
    _iniciar_chamada(coletor, "gpt-6-luna", "primario")
    coletor.on_llm_error(erro, run_id="primario")
    # Outra execução do agente não deve consumir a falha da primeira.
    _iniciar_chamada(coletor, "openai/gpt-oss-120b", "outra", parent="tentativa-2")
    _finalizar_chamada(coletor, "outra")
    assert montar_painel()["resumo"]["fallbacks"] == 0
    _iniciar_chamada(coletor, "openai/gpt-oss-120b", "fallback")
    _finalizar_chamada(coletor, "fallback")
    obs.fechar_turno(turno, "sessao", "oil_advisor", "ok")
    painel = montar_painel()
    assert painel["resumo"]["fallbacks"] == 1
    assert painel["turnos"][0]["status"] == "ok"
    assert painel["erros_modelo"][0]["codigo"] == "model_not_found"
    assert painel["erros_modelo"][0]["http_status"] == 404
    assert "sk-teste-secreto" not in str(painel)
    assert "sk-teste-secreto" not in caplog.text
    assert "model_not_found" in caplog.text
    obs.abrir_turno()
    _iniciar_chamada(coletor, "openai/gpt-oss-120b", "novo-turno")
    _finalizar_chamada(coletor, "novo-turno")
    assert montar_painel()["resumo"]["fallbacks"] == 1


def test_integracao_fallback_real_sem_chamadas_externas():
    import asyncio
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.outputs import ChatResult
    from langchain_core.runnables import RunnableLambda

    class ModeloTeste(BaseChatModel):
        model_name: str
        falhar: bool = False

        @property
        def _llm_type(self):
            return "teste"

        @property
        def _identifying_params(self):
            return {"model": self.model_name}

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            if self.falhar:
                raise RuntimeError("Falha de teste")
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])

    obs.abrir_turno()
    primario = ModeloTeste(model_name="gpt-6-luna", falhar=True, callbacks=[obs.coletor])
    reserva = ModeloTeste(model_name="openai/gpt-oss-120b", callbacks=[obs.coletor])
    modelo = primario.with_fallbacks([reserva])
    # Reproduz o callback pai que o nó do agente fornece aos modelos.
    agente = RunnableLambda(lambda mensagem: modelo.invoke(mensagem))
    assert agente.invoke("Teste", config={"metadata": {"langgraph_node": "oil_advisor"}}).text == "ok"
    assert montar_painel()["resumo"]["fallbacks"] == 1

    async def chamar(mensagem, config):
        return await modelo.ainvoke(mensagem, config=config)

    agente_async = RunnableLambda(chamar)
    assert asyncio.run(agente_async.ainvoke("Teste", config={"metadata": {"langgraph_node": "oil_advisor"}})).text == "ok"
    assert montar_painel()["resumo"]["fallbacks"] == 2
    # Uma resposta do principal não conta como fallback.
    primario.falhar = False
    assert asyncio.run(agente_async.ainvoke("Teste", config={"metadata": {"langgraph_node": "oil_advisor"}})).text == "ok"
    assert montar_painel()["resumo"]["fallbacks"] == 2
