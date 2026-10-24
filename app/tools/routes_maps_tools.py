"""Destinos do Olius no PostgreSQL; distância e duração pelo Google Maps MCP."""

import asyncio
import json
from decimal import Decimal
from math import ceil, isfinite
from uuid import UUID

from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.maps_mcp import maps_session
from app.tools.db import get_conn
from app.tools.discard_tools import serializar, usuario

PASSO_RAIO = 50
AVISO_TEMPO = "Os tempos de deslocamento são estimativas do Google Maps e podem variar conforme o trânsito, obras, clima e outros fatores."


class BuscarLocaisProximosArgs(BaseModel):
    raio_inicial_metros: int = Field(default=100, ge=1, le=50000)
    raio_maximo_metros: int = Field(default=5000, ge=1, le=50000)


class CalcularTemposDeslocamentoArgs(BaseModel):
    cidade: str | None = Field(default=None, min_length=1, max_length=100, description="Consulta TODOS os PEVs aprovados desta cidade; sem limite de raio ou quantidade.")
    estado: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$", description="UF para desambiguar a cidade.")
    ids_enderecos: list[UUID] | None = Field(default=None, min_length=1, description="Alternativa à cidade: endereços cadastrados selecionados pela busca próxima.")
    origem_endereco: str | None = Field(default=None, min_length=1, max_length=500, description="Origem textual explicitamente informada pelo usuário; se ausente usa a localização enviada pelo dispositivo.")


LOCAIS_SQL = """
    SELECT p.id AS id, a.id AS endereco_id, 'PEV'::text AS tipo,
           CASE WHEN p.establishment_id IS NOT NULL THEN u.name
                ELSE 'PEV - ' || a.street || ', ' || a.number END AS nome,
           a.street AS rua, a.number AS numero, a.neighborhood AS bairro,
           a.city AS cidade, a.state AS estado, a.cep, a.latitude, a.longitude
    FROM public.pev p
    JOIN public.users u ON u.id = COALESCE(p.establishment_id, p.citizen_id)
    JOIN public.addresses a ON a.id = p.address_id
    WHERE p.status = 'APPROVED' AND u.status = 'ACTIVE'

"""


def coordenadas(localizacao):
    try:
        lat, lon = float(localizacao["latitude"]), float(localizacao["longitude"])
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError("Envie latitude e longitude da origem pelo web/mobile.") from None
    if not isfinite(lat) or not isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Coordenadas da origem inválidas.")
    return {"latitude": lat, "longitude": lon}


def origem_execucao(config, endereco=None):
    if endereco is not None:
        if not endereco.strip():
            raise ValueError("Informe um endereço de origem válido.")
        return {"address": endereco.strip()}
    localizacao = (config or {}).get("configurable", {}).get("localizacao")
    return {"lat_lng": coordenadas(localizacao)}


def _validar_usuario(cur, config):
    cur.execute("SELECT id FROM public.users WHERE id = %s AND status = 'ACTIVE'", (usuario(config),))
    if not cur.fetchone():
        raise ValueError("Usuário indisponível.")


def _expressao_distancia(origem):
    if "lat_lng" not in origem:
        return "NULL::double precision", []
    location = origem["lat_lng"]
    return """CASE WHEN latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180 THEN
        12742000 * asin(sqrt(least(1.0, greatest(0.0,
            power(sin(radians(latitude::double precision - %s) / 2), 2)
            + cos(radians(%s)) * cos(radians(latitude::double precision))
            * power(sin(radians(longitude::double precision - %s) / 2), 2)
        )))) END""", [location["latitude"], location["latitude"], location["longitude"]]


def _consultar_locais(config, origem, cidade=None, estado=None, ids_enderecos=None, raio_maximo=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            _validar_usuario(cur, config)
            conditions, params = ["TRUE"], []
            if cidade is not None:
                conditions.append("lower(btrim(cidade)) = lower(btrim(%s))")
                params.append(cidade)
            if estado:
                conditions.append("upper(estado) = upper(%s)")
                params.append(estado)
            if ids_enderecos is not None:
                conditions.append("endereco_id = ANY(%s::uuid[])")
                params.append(ids_enderecos)
            distancia, geo_params = _expressao_distancia(origem)
            query = "WITH locais AS (" + LOCAIS_SQL + "), selecionados AS (SELECT * FROM locais WHERE "
            query += " AND ".join(conditions) + "), medidos AS (SELECT *, " + distancia + " AS distancia_linha_reta_metros FROM selecionados) SELECT * FROM medidos"
            if raio_maximo is not None:
                query += " WHERE distancia_linha_reta_metros <= %s OR distancia_linha_reta_metros IS NULL"
                geo_params.append(raio_maximo)
            query += " ORDER BY distancia_linha_reta_metros NULLS LAST, nome, endereco_id"
            cur.execute(query, [*params, *geo_params])
            return cur.fetchall()


def selecionar_raio(locais, raio_inicial, raio_maximo):
    if not 0 < raio_inicial <= raio_maximo <= 50000:
        raise ValueError("Use 0 < raio inicial <= raio máximo <= 50000 m.")
    candidatos = [local for local in locais if local["distancia_linha_reta_metros"] is not None]
    if not candidatos:
        return raio_maximo, []
    menor = min(local["distancia_linha_reta_metros"] for local in candidatos)
    raio = raio_inicial + max(0, ceil((menor - raio_inicial) / PASSO_RAIO)) * PASSO_RAIO
    raio = min(raio, raio_maximo)
    return raio, [local for local in candidatos if local["distancia_linha_reta_metros"] <= raio]


def _destino(local):
    try:
        return {"lat_lng": coordenadas(local)}
    except ValueError:
        endereco = f"{local['rua']}, {local['numero']}, {local['bairro']}, {local['cidade']}, {local['estado']}, {local['cep']}, Brasil"
        return {"address": endereco}


def _argumentos_rota(campos, origem, destino, modo):
    snake = "travel_mode" in campos
    def waypoint(ponto):
        if "address" in ponto:
            return ponto
        return {"lat_lng" if snake else "latLng": ponto["lat_lng"]}
    return {"origin": waypoint(origem), "destination": waypoint(destino), "travel_mode" if snake else "travelMode": modo}


def _dados_rota(resultado):
    if resultado.is_error:
        raise ValueError("MCP reportou erro de cálculo.")
    dados = resultado.structured_content
    if dados is None:
        text = next(item.text for item in resultado.content if item.type == "text")
        dados = json.loads(text)
    if not isinstance(dados, dict) or not isinstance(dados.get("routes"), list):
        raise ValueError("Retorno inválido.")
    return dados["routes"]


def _duracao(valor):
    if isinstance(valor, dict) and "seconds" in valor:
        segundos = Decimal(str(valor["seconds"])) + Decimal(str(valor.get("nanos", 0))) / 1000000000
    elif isinstance(valor, str) and valor.endswith("s"):
        segundos = Decimal(valor[:-1])
    else:
        raise ValueError("Duração ausente.")
    if not segundos.is_finite() or segundos < 0:
        raise ValueError("Duração inválida.")
    return segundos


def _resumir_rota(resultado, modo):
    rotas = _dados_rota(resultado)
    if not rotas:
        return {"status": "sem_rota", "modo": modo}
    rota = rotas[0]
    metros = rota.get("distanceMeters", rota.get("distance_meters"))
    if isinstance(metros, bool) or not isinstance(metros, (int, float)) or not isfinite(metros) or metros < 0:
        raise ValueError("Distância inválida.")
    segundos = _duracao(rota.get("duration"))
    result = {"status": "ok", "modo": modo, "distancia_metros": metros,
              "distancia_km": round(metros / 1000, 3), "duracao_segundos": str(segundos),
              "duracao_minutos": round(float(segundos / 60), 1), "attribution": rota.get("attribution")}
    if modo == "WALK":
        result["aviso"] = AVISO_TEMPO
    return result


async def _campos_rota(session):
    from mcp import types
    params = None
    while True:
        pagina = await session.list_tools(params=params)
        for item in pagina.tools:
            if item.name == "compute_routes":
                return item.input_schema["properties"]
        if not pagina.next_cursor:
            raise RuntimeError("compute_routes indisponível no MCP.")
        params = types.PaginatedRequestParams(cursor=pagina.next_cursor)


async def _calcular_todos(locais, origem):
    resultados = []
    # Uma sessão, sem manter conexões ao banco durante as chamadas remotas.
    async with maps_session() as session:
        campos = await _campos_rota(session)
        for local in locais:
            trajetos = []
            for modo in ("DRIVE", "WALK"):
                try:
                    resposta = await session.call_tool("compute_routes", arguments=_argumentos_rota(campos, origem, _destino(local), modo))
                    trajetos.append(_resumir_rota(resposta, modo))
                except Exception:
                    # Um destino/modo com erro não apaga os demais resultados.
                    trajetos.append({"status": "error", "modo": modo, "mensagem": "Não foi possível calcular este trajeto."})
            resultados.append({**local, "trajetos": trajetos})
    return resultados


def _status_resultados(resultados):
    sucessos = sum(rota["status"] == "ok" for local in resultados for rota in local["trajetos"])
    if sucessos == len(resultados) * 2:
        return "ok"
    return "parcial" if sucessos else "sem_trajetos_calculados"


@tool("calcular_tempos_deslocamento", args_schema=CalcularTemposDeslocamentoArgs)
async def calcular_tempos_deslocamento(
    config: RunnableConfig, cidade: str | None = None, estado: str | None = None,
    ids_enderecos: list[UUID] | None = None, origem_endereco: str | None = None,
) -> dict:
    """Consulta PEVs aprovados por cidade ou IDs e calcula DRIVE/WALK para TODOS.

    Sem limite de raio ou quantidade. Não inventa tempos, não calcula viagens
    entre destinos: cada trajeto parte da mesma origem. Identidade e localização
    vêm de configurable.user_id e configurable.localizacao, validados pelo backend.
    Disponível a usuários ativos B2B e B2C. Cidade e IDs podem ser combinados como filtros.
    """
    try:
        usuario(config)
        if cidade is None and not ids_enderecos:
            raise ValueError("Informe uma cidade ou os IDs dos endereços cadastrados.")
        if cidade is not None and not cidade.strip():
            raise ValueError("Informe uma cidade válida.")
        origem = origem_execucao(config, origem_endereco)
        locais = await asyncio.to_thread(_consultar_locais, config, origem, cidade, estado, ids_enderecos)
        if not locais:
            return {"status": "sem_resultados", "quantidade": 0, "resultados": []}
        resultados = await _calcular_todos(locais, origem)
        return serializar({"status": _status_resultados(resultados), "origem": origem,
                          "quantidade": len(resultados), "resultados": resultados})
    except ValueError as exc:
        return {"status": "error", "mensagem": str(exc)}
    except Exception:
        return {"status": "error", "mensagem": "Consulta ao banco ou ao Google Maps indisponível."}


@tool("buscar_locais_proximos", args_schema=BuscarLocaisProximosArgs)
async def buscar_locais_proximos(
    config: RunnableConfig, raio_inicial_metros: int = 100, raio_maximo_metros: int = 5000,
) -> dict:
    """Busca somente PEVs aprovados próximos do dispositivo e calcula tempos DRIVE/WALK.

    Uma consulta ao banco calcula distâncias e simula raios de 100 m, +50 m,
    até o primeiro raio com resultados ou o máximo informado. Devolve TODOS os
    PEVs desse raio, para usuários B2B e B2C. B2Bs comuns não entram nesta busca.
    A tool calcular_tempos_deslocamento é chamada com os endereços selecionados.
    """
    try:
        usuario(config)
        if not 0 < raio_inicial_metros <= raio_maximo_metros <= 50000:
            raise ValueError("Use 0 < raio inicial <= raio máximo <= 50000 m.")
        origem = origem_execucao(config)
        locais = await asyncio.to_thread(_consultar_locais, config, origem, raio_maximo=raio_maximo_metros)
        faltantes = sum(local["distancia_linha_reta_metros"] is None for local in locais)
        raio, selecionados = selecionar_raio(locais, raio_inicial_metros, raio_maximo_metros)
        info = {"raio_utilizado_metros": raio, "raio_maximo_metros": raio_maximo_metros,
                "passo_metros": PASSO_RAIO, "cadastros_sem_coordenadas": faltantes,
                "busca_completa": faltantes == 0}
        if not selecionados:
            return {"status": "sem_resultados_no_raio", "quantidade": 0, "resultados": [], **info}
        resultado = await calcular_tempos_deslocamento.ainvoke(
            {"ids_enderecos": [str(local["endereco_id"]) for local in selecionados]}, config=config,
        )
        return {**resultado, **info}
    except ValueError as exc:
        return {"status": "error", "mensagem": str(exc)}
    except Exception:
        return {"status": "error", "mensagem": "Não foi possível consultar os locais próximos."}


TOOLS_ROUTES_MAPS = [buscar_locais_proximos, calcular_tempos_deslocamento]
