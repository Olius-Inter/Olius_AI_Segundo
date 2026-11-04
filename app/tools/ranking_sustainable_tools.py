import psycopg
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from app.tools.db import get_conn
from app.tools.discard_tools import (
    consultar_historico_descarte,
    perfil_usuario as _perfil,
    serializar as _serializar,
    usuario as _usuario,
)


class ConsultarNivelRankingArgs(BaseModel):
    """Identidade recebida pela configuração da execução, não pelo modelo."""


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


TOOLS_RANKING_SUSTAINABLE = [consultar_nivel_ranking, consultar_historico_descarte]
