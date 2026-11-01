"""Métricas em memória dos últimos 50 turnos do chat.

Custos estimados pela tabela local de tokens, sem equivalência à fatura.
Reiniciar o processo apaga os registros. Nenhum prompt é armazenado aqui.
"""

from __future__ import annotations

import threading
import logging
import os
import re
from contextvars import ContextVar
import time
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

_FUSO = ZoneInfo("America/Sao_Paulo")

# USD por 1 milhão de tokens: (entrada, saída).
PRECO_POR_MILHAO: dict[str, tuple[float, float]] = {
    "gpt-6-luna": (0.10, 0.50),
    "openai/gpt-oss-120b": (0.15, 0.60),
}

# Groq é o fallback do especialista configurado em llms.py.
_NOS_ESPECIALISTA = {"oil_advisor", "routes_maps", "ranking_sustainable", "business_analyst"}
_NOS_GRAFO = _NOS_ESPECIALISTA | {"faq", "router", "orchestrator", "guardrail_entrada", "guardrail_saida"}
_MODELO_ESPECIALISTA = "gpt-6-luna"
_MODELO_FALLBACK = "openai/gpt-oss-120b"
_logger = logging.getLogger(__name__)

LIMITE_TURNOS = 50
LIMITE_P95_MS = 8_000
LIMITE_TAXA_ERRO = 0.05

_lock = threading.Lock()
_inicio_processo = time.time()
_em_andamento = 0
_turnos: list[dict[str, Any]] = []
_chamadas: list[dict[str, Any]] = []
_abertos: dict[str, float] = {}
_runs: dict[str, dict[str, Any]] = {}
_erros_modelo: list[dict[str, Any]] = []
_falhas_primarias: dict[tuple, dict[str, Any]] = {}
_ligado = False

# Um handler só, compartilhado pelos três modelos. O turno entra no run
# na largada da chamada, então duas requisições ao mesmo tempo não misturam
# a conta.
coletor = None  # preenchido abaixo, depois da classe


def _agora_local() -> str:
    return datetime.now(_FUSO).strftime("%H:%M:%S")


def _nome_modelo(serialized: dict | None, invocation_params: dict | None, resposta_meta: dict | None) -> str:
    candidatos = []
    for fonte in (resposta_meta or {}, invocation_params or {}, (serialized or {}).get("kwargs") or {}):
        for chave in ("model_name", "model"):
            valor = fonte.get(chave)
            if valor:
                candidatos.append(str(valor))
    for nome in candidatos:
        if nome.startswith("models/"):
            nome = nome.split("/", 1)[1]
        return nome
    return "desconhecido"


def _no_do_grafo(metadata: dict | None) -> str:
    """O nó do nosso grafo, não o nó interno do create_agent."""
    metadata = metadata or {}
    ns = str(metadata.get("langgraph_checkpoint_ns") or "")
    candidatos: list[str] = []
    if ns:
        for parte in ns.split("|"):
            candidatos.append(parte.split(":", 1)[0])
    no = metadata.get("langgraph_node")
    if no:
        candidatos.append(str(no))
    for nome in candidatos:
        if nome in _NOS_GRAFO:
            return nome
    return candidatos[0] if candidatos else ""


def _tokens(message: Any) -> tuple[int, int]:
    usage = getattr(message, "usage_metadata", None) or {}
    if not isinstance(usage, dict):
        usage = {
            "input_tokens": getattr(usage, "input_tokens", 0),
            "output_tokens": getattr(usage, "output_tokens", 0),
        }
    entrada = int(usage.get("input_tokens") or 0)
    saida = int(usage.get("output_tokens") or 0)
    if entrada or saida:
        return entrada, saida

    meta = getattr(message, "response_metadata", None) or {}
    bruto = meta.get("token_usage") or meta.get("usage") or {}
    entrada = int(bruto.get("prompt_tokens") or bruto.get("input_tokens") or 0)
    saida = int(bruto.get("completion_tokens") or bruto.get("output_tokens") or 0)
    return entrada, saida


def custo_usd(modelo: str, entrada: int, saida: int) -> float:
    precos = PRECO_POR_MILHAO.get(modelo)
    if precos is None:
        for chave, valor in PRECO_POR_MILHAO.items():
            if chave in modelo:
                precos = valor
                break
    if precos is None:
        return 0.0
    preco_entrada, preco_saida = precos
    return (entrada * preco_entrada + saida * preco_saida) / 1_000_000


def _chave_tentativa(abertura: dict) -> tuple:
    return (abertura["turno_id"], abertura["no"], abertura["parent_run_id"])


def _detalhes_erro(error: BaseException) -> dict:
    """Registra o erro do provedor, sem cabeçalhos, prompts ou credenciais."""
    corpo = getattr(error, "body", None)
    corpo = corpo if isinstance(corpo, dict) else {}
    if isinstance(corpo.get("error"), dict):
        corpo = corpo["error"]
    mensagem = corpo.get("message") or getattr(error, "message", None) or type(error).__name__
    mensagem = str(mensagem)
    for nome, valor in os.environ.items():
        if valor and len(valor) > 6 and any(item in nome.upper() for item in ("KEY", "TOKEN", "PASSWORD", "SECRET")):
            mensagem = mensagem.replace(valor, "[credencial removida]")
    mensagem = re.sub(r"(?:sk-[\w-]+|gsk_[\w-]+)", "[credencial removida]", mensagem)
    return {
        "tipo": type(error).__name__,
        "mensagem": mensagem[:1000],
        "http_status": getattr(error, "status_code", None),
        "codigo": corpo.get("code"),
        "parametro": corpo.get("param"),
    }


class ColetorChamadas(BaseCallbackHandler):
    """Anota cada chamada de chat model sem guardar o texto do prompt."""

    raise_error = False

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: Any,
        metadata: dict[str, Any] | None = None,
        parent_run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        invocation = kwargs.get("invocation_params") or {}
        with _lock:
            _runs[str(run_id)] = {
                "t0": time.perf_counter(),
                "modelo": _nome_modelo(serialized, invocation, None),
                "no": _no_do_grafo(metadata),
                "turno_id": _turno_da_thread(),
                "parent_run_id": str(parent_run_id) if parent_run_id is not None else None,
            }

    def on_llm_end(self, response: LLMResult, *, run_id: Any, **kwargs: Any) -> None:
        chave = str(run_id)
        with _lock:
            abertura = _runs.pop(chave, None)
        if abertura is None or not abertura.get("turno_id"):
            return

        message = None
        try:
            message = response.generations[0][0].message
        except (IndexError, AttributeError):
            message = None

        entrada, saida = _tokens(message) if message is not None else (0, 0)
        meta = getattr(message, "response_metadata", None) if message is not None else None
        modelo = _nome_modelo(None, None, meta) 
        if modelo == "desconhecido":
            modelo = abertura["modelo"]

        latencia_ms = int((time.perf_counter() - abertura["t0"]) * 1000)
        registro = {
            "turno_id": abertura["turno_id"],
            "modelo": modelo,
            "no": abertura["no"],
            "tokens_entrada": entrada,
            "tokens_saida": saida,
            "custo_usd": custo_usd(modelo, entrada, saida),
            "latencia_ms": latencia_ms,
            "fallback": False,
        }
        with _lock:
            chave_tentativa = _chave_tentativa(abertura)
            falha = _falhas_primarias.pop(chave_tentativa, None)
            registro["fallback"] = bool(
                falha and abertura["parent_run_id"] is not None
                and abertura["no"] in _NOS_ESPECIALISTA
                and _MODELO_FALLBACK in modelo
            )
            _chamadas.append(registro)

    def on_llm_error(self, error: BaseException, *, run_id: Any, **kwargs: Any) -> None:
        with _lock:
            abertura = _runs.pop(str(run_id), None)
        if not abertura or not abertura["turno_id"]:
            return
        registro = {
            **_detalhes_erro(error), "hora": _agora_local(),
            "modelo": abertura["modelo"], "no": abertura["no"],
            "turno_id": abertura["turno_id"],
        }
        with _lock:
            _erros_modelo.append(registro)
            if abertura["no"] in _NOS_ESPECIALISTA and _MODELO_ESPECIALISTA in abertura["modelo"]:
                _falhas_primarias[_chave_tentativa(abertura)] = registro
        _logger.warning(
            "Falha de modelo: modelo=%s agente=%s tipo=%s HTTP=%s codigo=%s mensagem=%s",
            registro["modelo"], registro["no"], registro["tipo"],
            registro["http_status"], registro["codigo"], registro["mensagem"],
        )


coletor = ColetorChamadas()

# ContextVar acompanha o contexto copiado pelo LangGraph nas tarefas dos nós.
_turno_atual: ContextVar[str | None] = ContextVar("observabilidade_turno", default=None)


def _turno_da_thread() -> str | None:
    return _turno_atual.get()


def ligar_coleta() -> None:
    """Põe o coletor nos três modelos, uma vez por processo."""
    global _ligado
    if _ligado:
        return
    from app.llms import llm_chatgpt, llm_rapido

    for modelo in (
            llm_chatgpt,
            # llm_groq,
            llm_rapido
        ):
        if modelo is None:
            continue
        atuais = list(modelo.callbacks or [])
        if not any(isinstance(item, ColetorChamadas) for item in atuais):
            modelo.callbacks = [*atuais, coletor]
    _ligado = True


def abrir_turno() -> str:
    ligar_coleta()
    turno_id = uuid.uuid4().hex
    _turno_atual.set(turno_id)
    with _lock:
        global _em_andamento
        _em_andamento += 1
        _abertos[turno_id] = time.perf_counter()
    return turno_id


def fechar_turno(turno_id: str, session_id: str, rota: str, status: str) -> None:
    _turno_atual.set(None)
    with _lock:
        inicio = _abertos.pop(turno_id, None)
        if inicio is None:
            return
        global _em_andamento
        _em_andamento = max(0, _em_andamento - 1)
        do_turno = [c for c in _chamadas if c["turno_id"] == turno_id]
        for chave in [c for c in _falhas_primarias if c[0] == turno_id]:
            _falhas_primarias.pop(chave, None)
        _turnos.append({
            "id": turno_id,
            "hora": _agora_local(),
            "session_id": session_id,
            "latencia_ms": int((time.perf_counter() - inicio) * 1000),
            "rota": rota or "—",
            "status": status,
            "tokens_total": sum(c["tokens_entrada"] + c["tokens_saida"] for c in do_turno),
            "custo_usd": sum(c["custo_usd"] for c in do_turno),
        })
        while len(_turnos) > LIMITE_TURNOS:
            antigo = _turnos.pop(0)
            _chamadas[:] = [c for c in _chamadas if c["turno_id"] != antigo["id"]]
            _erros_modelo[:] = [e for e in _erros_modelo if e["turno_id"] != antigo["id"]]


def status_do_estado(estado: dict) -> str:
    """Bloqueio de entrada é o sistema funcionando. Erro fica para a exceção."""
    for nome in reversed(estado.get("agentes_chamados") or []):
        if isinstance(nome, str) and nome.startswith("guardrail_entrada:"):
            return "ok" if nome == "guardrail_entrada:aprovado" else "bloqueado"
    return "ok"


def rota_do_estado(estado: dict) -> str:
    """Agente da requisição atual, sem reutilizar agentes de turnos anteriores."""
    for nome in reversed(estado.get("agentes_chamados") or []):
        if nome in _NOS_ESPECIALISTA | {"faq", "router"}:
            return nome
        if isinstance(nome, str) and nome.startswith("guardrail_entrada:"):
            return "guardrail_entrada"
    return "—"


def listar_erros_modelo() -> list[dict[str, Any]]:
    with _lock:
        return [{k: v for k, v in erro.items() if k != "turno_id"} for erro in _erros_modelo]

def listar_turnos() -> list[dict[str, Any]]:
    with _lock:
        return [
            {chave: valor for chave, valor in turno.items() if chave != "id"}
            for turno in _turnos
        ]


def listar_chamadas() -> list[dict[str, Any]]:
    with _lock:
        return [
            {chave: valor for chave, valor in chamada.items() if chave != "turno_id"}
            for chamada in _chamadas
        ]


def situacao() -> dict[str, int]:
    with _lock:
        return {
            "em_andamento": _em_andamento,
            "no_ar_segundos": int(time.time() - _inicio_processo),
        }
