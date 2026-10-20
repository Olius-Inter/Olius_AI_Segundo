"""Histórico e consultas compartilhadas pelos agentes de descarte."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.tools.db import get_conn


class PeriodoDescarteArgs(BaseModel):
    data_inicio: date | None = Field(
        default=None, description="Data inicial inclusiva; padrão: início do terceiro mês anterior.",
    )
    data_fim: date | None = Field(
        default=None, description="Data final inclusiva; padrão: hoje em America/Sao_Paulo.",
    )


class ConsultarHistoricoDescarteArgs(PeriodoDescarteArgs):
    limite: int = Field(default=20, ge=1, le=100, description="Registros por página (1 a 100).")
    pagina: int = Field(default=1, ge=1, le=10000, description="Página do histórico, começando em 1.")


def usuario(config):
    # Identidade validada pelo backend, nunca escolhida pelo modelo.
    value = (config or {}).get("configurable", {}).get("user_id")
    if not value:
        raise ValueError("Usuário não identificado na configuração da execução.")
    try:
        return str(UUID(str(value)))
    except ValueError:
        raise ValueError("Identificador de usuário inválido.") from None


def perfil_usuario(cur, user_id):
    cur.execute(
        "SELECT user_type::text AS perfil FROM public.users "
        "WHERE id = %s AND status = 'ACTIVE'", (user_id,),
    )
    row = cur.fetchone()
    if not row or row["perfil"] not in ("CITIZENS", "ESTABLISHMENT"):
        raise ValueError("Usuário indisponível ou sem perfil participante.")
    return "B2C" if row["perfil"] == "CITIZENS" else "B2B"


def serializar(value):
    if isinstance(value, dict):
        return {key: serializar(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serializar(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    return value


def hoje_local():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date()


def deslocar_mes(primeiro_dia, meses):
    ano, mes = divmod(primeiro_dia.year * 12 + primeiro_dia.month - 1 + meses, 12)
    return date(ano, mes + 1, 1)


def periodo_descarte(data_inicio=None, data_fim=None):
    hoje = hoje_local()
    inicio = data_inicio or deslocar_mes(hoje.replace(day=1), -3)
    fim = data_fim or hoje
    if inicio > fim:
        raise ValueError("A data inicial deve ser anterior ou igual à final.")
    if fim > hoje:
        raise ValueError("O período de descarte não pode incluir datas futuras.")
    meses = []
    mes = inicio.replace(day=1)
    while mes <= fim:
        ultimo = deslocar_mes(mes, 1) - timedelta(days=1)
        completo = inicio <= mes and fim >= ultimo and mes < hoje.replace(day=1)
        meses.append({
            "mes": mes.isoformat()[:7], "inicio": max(inicio, mes),
            "fim": min(fim, ultimo), "parcial": not completo,
            "mes_atual": mes == hoje.replace(day=1),
        })
        mes = deslocar_mes(mes, 1)
    return {"inicio": inicio, "fim": fim, "fuso": "America/Sao_Paulo", "meses": meses}


def fonte_descartes(perfil):
    # Identificadores SQL fixos; somente valores são recebidos do chamador.
    if perfil == "B2B":
        return """
            SELECT id, collection_date AS data, collected_volume_liters AS litros,
                   points_earned AS pontos, observation AS observacao,
                   result::text AS resultado, NULL::uuid AS pev_id
            FROM public.collection
            WHERE establishment_id = %s AND record_status = 'RECORDED'
        """
    return """
        SELECT id, delivery_date AS data, oil_volume_liters AS litros,
               points_earned AS pontos, NULL::text AS observacao,
               NULL::text AS resultado, pev_id
        FROM public.delivery_pev
        WHERE citizen_id = %s AND record_status = 'RECORDED'
    """


def consulta_periodo(perfil):
    return "WITH descartes AS (" + fonte_descartes(perfil) + """), periodo AS (
        SELECT * FROM descartes
        WHERE data >= (%s::date::timestamp AT TIME ZONE 'America/Sao_Paulo')
          AND data < ((%s::date + INTERVAL '1 day') AT TIME ZONE 'America/Sao_Paulo')
    ) """


@tool("consultar_historico_descarte", args_schema=ConsultarHistoricoDescarteArgs)
def consultar_historico_descarte(
    config: RunnableConfig,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    limite: int = 20,
    pagina: int = 1,
) -> dict:
    """Lista coletas B2B ou entregas B2C do usuário, excluindo anulações.

    Padrão: três últimos meses completos mais o mês atual parcial até hoje.
    Datas inclusivas em São Paulo. Resultado paginado; consulte a tool de
    indicadores para totais de todo o período, nunca some somente esta lista.
    """
    try:
        user_id = usuario(config)
        if not 1 <= limite <= 100 or not 1 <= pagina <= 10000:
            raise ValueError("Use limite entre 1 e 100 e página entre 1 e 10000.")
        periodo = periodo_descarte(data_inicio, data_fim)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                perfil = perfil_usuario(cur, user_id)
                query = consulta_periodo(perfil) + "SELECT * FROM periodo ORDER BY data DESC, id DESC LIMIT %s OFFSET %s"
                cur.execute(query, [user_id, periodo["inicio"], periodo["fim"], limite + 1, (pagina - 1) * limite])
                rows = cur.fetchall()
        return serializar({
            "status": "ok", "perfil": perfil, "periodo": periodo,
            "count": len(rows[:limite]), "results": rows[:limite],
            "pagina": pagina, "limite": limite, "tem_proxima_pagina": len(rows) > limite,
        })
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    except (psycopg.Error, RuntimeError):
        return {"status": "error", "message": "Não foi possível consultar o histórico de descarte."}
