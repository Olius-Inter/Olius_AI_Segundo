"""Primeira etapa: conectar ao Google Maps MCP e descobrir as tools escolhidas."""

import asyncio
from contextlib import asynccontextmanager

from mcp import ClientSession, types
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from app.config import GOOGLE_MAPS_API_KEY, GOOGLE_MAPS_API_URL

MAPS_ENDPOINT = "https://mapstools.googleapis.com/mcp"
MAPS_TOOLS = ("search_places", "compute_routes")


@asynccontextmanager
async def maps_session():
    """Abre, inicializa e fecha a sessão MCP. Não realiza buscas."""
    if not GOOGLE_MAPS_API_KEY or not GOOGLE_MAPS_API_KEY.strip():
        raise ValueError("GOOGLE_MAPS_API_KEY não configurada.")
    if GOOGLE_MAPS_API_URL != MAPS_ENDPOINT:
        raise ValueError("GOOGLE_MAPS_API_URL deve apontar para o endpoint oficial do MCP.")

    # A chave fica no cabeçalho, sem aparecer na URL ou no retorno.
    headers = {
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "Accept": "application/json, text/event-stream",
    }
    async with create_mcp_http_client(headers=headers) as client:
        async with streamable_http_client(MAPS_ENDPOINT, http_client=client) as streams:
            read, write = streams
            async with ClientSession(read, write, read_timeout_seconds=20) as session:
                await session.initialize()
                yield session


async def listar_ferramentas_maps():
    """Confirma as duas tools escolhidas e devolve seus schemas reais."""
    found = {}
    async with asyncio.timeout(30):
        async with maps_session() as session:
            params = None
            while True:
                result = await session.list_tools(params=params)
                for tool in result.tools:
                    if tool.name in MAPS_TOOLS:
                        found[tool.name] = {
                            "name": tool.name,
                            "description": tool.description,
                            "input_schema": tool.input_schema,
                        }
                if len(found) == len(MAPS_TOOLS) or not result.next_cursor:
                    break
                params = types.PaginatedRequestParams(cursor=result.next_cursor)
    missing = set(MAPS_TOOLS) - found.keys()
    if missing:
        raise RuntimeError("Ferramentas não disponíveis no MCP: " + ", ".join(sorted(missing)))
    return [found[name] for name in MAPS_TOOLS]


def main():
    """Teste manual: python -m app.maps_mcp. Nunca imprime a credencial."""
    try:
        tools = asyncio.run(listar_ferramentas_maps())
    except ValueError as exc:
        print(str(exc))
        return 1
    except Exception:
        print("Não foi possível validar o MCP. Confira acesso à rede, serviço habilitado e credencial.")
        return 1
    print("Conexão MCP validada. Ferramentas disponíveis:")
    for tool in tools:
        print("- " + tool["name"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
