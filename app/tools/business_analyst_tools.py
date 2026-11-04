from decimal import Decimal
from datetime import date

import psycopg
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig

from app.tools.db import get_conn
from app.tools.discard_tools import (
    PeriodoDescarteArgs, consulta_periodo, consultar_historico_descarte,
    periodo_descarte, perfil_usuario, serializar, usuario,
)


INDICADORES_SQL = """
    SELECT to_char(data AT TIME ZONE 'America/Sao_Paulo', 'YYYY-MM') AS mes,
           COUNT(*) AS quantidade,
           SUM(litros) AS litros,
           COUNT(*) FILTER (WHERE resultado = 'SUCCESSFUL') AS sucessos
    FROM periodo GROUP BY 1 ORDER BY 1
"""


def _medidas(quantidade, litros, sucessos, perfil):
    return {
        "quantidade": quantidade, "litros": litros,
        "media_litros_por_operacao": litros / quantidade if quantidade else None,
        "coletas_bem_sucedidas": sucessos if perfil == "B2B" else None,
        "taxa_sucesso_percentual": (
            Decimal(sucessos) * 100 / quantidade if perfil == "B2B" and quantidade else None
        ),
    }


def _indicadores_mensais(periodo, rows, perfil):
    por_mes = {row["mes"]: row for row in rows}
    meses = []
    for mes in periodo["meses"]:
        row = por_mes.get(mes["mes"], {"quantidade": 0, "litros": Decimal(0), "sucessos": 0})
        meses.append({**mes, **_medidas(row["quantidade"], row["litros"], row["sucessos"], perfil)})
    return meses


def _comparacoes(meses):
    comparacoes = []
    for anterior, atual in zip(meses, meses[1:]):
        if anterior["parcial"] or atual["parcial"]:
            continue
        diferenca = atual["litros"] - anterior["litros"]
        comparacoes.append({
            "mes_anterior": anterior["mes"], "mes_atual": atual["mes"],
            "diferenca_litros": diferenca,
            "variacao_percentual": diferenca * 100 / anterior["litros"] if anterior["litros"] else None,
            "base_zero": anterior["litros"] == 0,
        })
    return comparacoes


@tool("analisar_descarte_periodo", args_schema=PeriodoDescarteArgs)
def analisar_descarte_periodo(
    config: RunnableConfig, data_inicio: date | None = None, data_fim: date | None = None,
) -> dict:
    """Calcula indicadores B2B/B2C sobre TODOS os descartes válidos do período.

    Padrão: três últimos meses completos e mês atual parcial. Retorna litros,
    quantidade, média por operação, evolução mensal e taxa de sucesso só B2B.
    Compara apenas meses completos; base zero tem variação percentual nula.
    Não calcula ranking, certificados nem saldo de pontos.
    """
    try:
        user_id = usuario(config)
        periodo = periodo_descarte(data_inicio, data_fim)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                perfil = perfil_usuario(cur, user_id)
                cur.execute(consulta_periodo(perfil) + INDICADORES_SQL,
                            [user_id, periodo["inicio"], periodo["fim"]])
                rows = cur.fetchall()
        meses = _indicadores_mensais(periodo, rows, perfil)
        totais = _medidas(
            sum(row["quantidade"] for row in rows),
            sum((row["litros"] for row in rows), Decimal(0)),
            sum(row["sucessos"] for row in rows), perfil,
        )
        return serializar({
            "status": "ok", "perfil": perfil, "periodo": periodo,
            "totais": totais, "mensal": meses, "comparacoes_meses_completos": _comparacoes(meses),
        })
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    except (psycopg.Error, RuntimeError):
        return {"status": "error", "message": "Não foi possível consultar os indicadores de descarte."}


TOOLS_BUSINESS_ANALYST = [consultar_historico_descarte, analisar_descarte_periodo]
