from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.tools.db import get_conn


class ConsultarNivelRankingArgs(BaseModel):
    """Identidade recebida pela configuração da execução, não pelo modelo."""


class ConsultarHistoricoDescarteArgs(BaseModel):
    data_inicio: date | None = Field(default=None, description="Data inicial inclusiva (YYYY-MM-DD).")
    data_fim: date | None = Field(default=None, description="Data final inclusiva (YYYY-MM-DD).")
    limite: int = Field(default=20, ge=1, le=100, description="Máximo de descartes retornados (1 a 100).")


def _usuario(config):
    # Preenchido pelo backend após validar a identidade do usuário.
    value = (config or {}).get("configurable", {}).get("user_id")
    if not value:
        raise ValueError("Usuário não identificado na configuração da execução.")
    try:
        return str(UUID(str(value)))
    except ValueError:
        raise ValueError("Identificador de usuário inválido.") from None


def _perfil(cur, user_id):
    cur.execute(
        "SELECT user_type::text AS perfil FROM public.users "
        "WHERE id = %s AND status = 'ACTIVE'", (user_id,),
    )
    row = cur.fetchone()
    if not row or row["perfil"] not in ("CITIZENS", "ESTABLISHMENT"):
        raise ValueError("Usuário indisponível ou sem perfil participante.")
    return "B2C" if row["perfil"] == "CITIZENS" else "B2B"


def _serializar(value):
    if isinstance(value, dict):
        return {key: _serializar(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serializar(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    return value


@tool("consultar_nivel_ranking", args_schema=ConsultarNivelRankingArgs)
def consultar_nivel_ranking(config: RunnableConfig) -> dict:
    """Consulta nível de certificado e posição no ranking anual do usuário.

    Ranking oficial do ano corrente, separado entre B2B e B2C. Níveis de
    certificado existem apenas para estabelecimentos (B2B), por litros acumulados.
    """
    try:
        user_id = _usuario(config)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                perfil = _perfil(cur, user_id)
                cur.execute(
                    "SELECT profile, ranking_year, annual_points, ranking_position "
                    "FROM public.vw_annual_ranking WHERE participant_id = %s AND profile = %s",
                    (user_id, perfil),
                )
                ranking = cur.fetchone()
                niveis = []
                if perfil == "B2B":
                    cur.execute("SELECT * FROM public.get_certificate_progress(%s)", (user_id,))
                    niveis = cur.fetchall()
        atingidos = [nivel for nivel in niveis if nivel["is_level_reached"]]
        pendentes = [nivel for nivel in niveis if not nivel["is_level_reached"]]
        situacao_niveis = "nao_aplicavel_cidadao"
        if perfil == "B2B":
            situacao_niveis = "configurados" if niveis else "sem_niveis_cadastrados"
        return _serializar({
            "status": "ok", "perfil": perfil, "ranking": ranking,
            "participa_ranking": ranking is not None,
            "nivel_atual": atingidos[-1] if atingidos else None,
            "proximo_nivel": pendentes[0] if pendentes else None,
            "niveis": niveis,
            "situacao_niveis": situacao_niveis,
        })
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    except (psycopg.Error, RuntimeError):
        return {"status": "error", "message": "Não foi possível consultar o nível e o ranking."}


def _consultar_descartes(cur, perfil, user_id, data_inicio, data_fim, limite):
    if perfil == "B2B":
        source = """
            SELECT id, collection_date AS data, collected_volume_liters AS litros,
                   points_earned AS pontos, observation AS observacao, result::text AS resultado
            FROM public.collection
            WHERE establishment_id = %s AND record_status = 'RECORDED'
        """
    else:
        source = """
            SELECT id, delivery_date AS data, oil_volume_liters AS litros,
                   points_earned AS pontos, pev_id
            FROM public.delivery_pev
            WHERE citizen_id = %s AND record_status = 'RECORDED'
        """
    conditions = []
    values = [user_id]
    if data_inicio:
        conditions.append("data >= (%s::date::timestamp AT TIME ZONE 'America/Sao_Paulo')")
        values.append(data_inicio)
    if data_fim:
        conditions.append("data < ((%s::date + INTERVAL '1 day') AT TIME ZONE 'America/Sao_Paulo')")
        values.append(data_fim)
    query = "WITH descartes AS (" + source + ") SELECT * FROM descartes"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY data DESC, id DESC LIMIT %s"
    values.append(limite)
    cur.execute(query, values)
    return cur.fetchall()


@tool("consultar_historico_descarte", args_schema=ConsultarHistoricoDescarteArgs)
def consultar_historico_descarte(
    config: RunnableConfig,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    limite: int = 20,
) -> dict:
    """Lista descartes do usuário, do mais recente ao mais antigo.

    Retorna coletas B2B ou entregas em PEV do cidadão B2C. Exclui anulações.
    Datas YYYY-MM-DD inclusivas em America/Sao_Paulo. Não use a lista limitada
    para calcular saldo ou totais de todo o histórico.
    """
    try:
        user_id = _usuario(config)
        if not 1 <= limite <= 100:
            raise ValueError("O limite deve estar entre 1 e 100.")
        if data_inicio and data_fim and data_inicio > data_fim:
            raise ValueError("A data inicial deve ser anterior ou igual à final.")
        if data_fim == date.max:
            raise ValueError("A data final deve ser anterior a 9999-12-31.")
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                perfil = _perfil(cur, user_id)
                rows = _consultar_descartes(cur, perfil, user_id, data_inicio, data_fim, limite)
        return _serializar({"status": "ok", "perfil": perfil, "count": len(rows), "results": rows})
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    except (psycopg.Error, RuntimeError):
        return {"status": "error", "message": "Não foi possível consultar o histórico de descarte."}


TOOLS_RANKING_SUSTAINABLE = [consultar_nivel_ranking, consultar_historico_descarte]
