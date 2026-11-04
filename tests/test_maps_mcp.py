import unittest
from io import StringIO
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app import maps_mcp


def tool(name):
    return SimpleNamespace(name=name, description="test", input_schema={"type": "object"})


class MapsDiagnosticTests(unittest.TestCase):
    def test_diagnostic_prints_only_tool_names(self):
        result = [{"name": name, "input_schema": {"secret": "PRIVATE_SCHEMA"}} for name in maps_mcp.MAPS_TOOLS]
        with patch.object(maps_mcp, "listar_ferramentas_maps", new_callable=AsyncMock, return_value=result), patch("sys.stdout", new_callable=StringIO) as output:
            self.assertEqual(maps_mcp.main(), 0)
        self.assertIn("compute_routes", output.getvalue())
        self.assertIn("search_places", output.getvalue())
        self.assertNotIn("PRIVATE_SCHEMA", output.getvalue())

    def test_diagnostic_hides_remote_exception_details(self):
        with patch.object(maps_mcp, "listar_ferramentas_maps", new_callable=AsyncMock, side_effect=RuntimeError("SECRET_API_KEY")), patch("sys.stdout", new_callable=StringIO) as output:
            self.assertEqual(maps_mcp.main(), 1)
        self.assertNotIn("SECRET_API_KEY", output.getvalue())
        self.assertIn("Não foi possível validar", output.getvalue())

    def test_diagnostic_reports_configuration_error(self):
        with patch.object(maps_mcp, "listar_ferramentas_maps", new_callable=AsyncMock, side_effect=ValueError("GOOGLE_MAPS_API_KEY não configurada.")), patch("sys.stdout", new_callable=StringIO) as output:
            self.assertEqual(maps_mcp.main(), 1)
        self.assertIn("GOOGLE_MAPS_API_KEY não configurada.", output.getvalue())


class MapsMcpTests(unittest.IsolatedAsyncioTestCase):
    async def test_session_initializes_and_closes(self):
        client = MagicMock()
        client.__aenter__.return_value = client
        session = MagicMock()
        session.__aenter__.return_value = session
        session.initialize = AsyncMock()

        @asynccontextmanager
        async def transport(*args, **kwargs):
            yield ("read", "write")

        with patch.object(maps_mcp, "GOOGLE_MAPS_API_KEY", "test-only"), patch.object(maps_mcp, "GOOGLE_MAPS_API_URL", maps_mcp.MAPS_ENDPOINT), patch.object(maps_mcp, "create_mcp_http_client", return_value=client) as connect, patch.object(maps_mcp, "streamable_http_client", transport), patch.object(maps_mcp, "ClientSession", return_value=session):
            async with maps_mcp.maps_session() as opened:
                self.assertIs(opened, session)
        session.initialize.assert_awaited_once()
        session.__aexit__.assert_awaited_once()
        client.__aexit__.assert_awaited_once()
        self.assertEqual(connect.call_args.kwargs["headers"]["X-Goog-Api-Key"], "test-only")

    async def test_missing_key_rejected_before_connection(self):
        with patch.object(maps_mcp, "GOOGLE_MAPS_API_KEY", ""), patch.object(maps_mcp, "create_mcp_http_client") as client:
            with self.assertRaises(ValueError):
                async with maps_mcp.maps_session():
                    self.fail("Não deve abrir a sessão sem chave")
        client.assert_not_called()

    async def test_key_is_never_sent_to_another_endpoint(self):
        with patch.object(maps_mcp, "GOOGLE_MAPS_API_KEY", "test-only"), patch.object(maps_mcp, "GOOGLE_MAPS_API_URL", "https://example.org/mcp"), patch.object(maps_mcp, "create_mcp_http_client") as client:
            with self.assertRaises(ValueError):
                async with maps_mcp.maps_session():
                    self.fail("Não deve enviar a chave para outro destino")
        client.assert_not_called()

    async def test_lists_only_selected_tools_and_follows_pagination(self):
        session = SimpleNamespace(list_tools=AsyncMock(side_effect=[
            SimpleNamespace(tools=[tool("search_places"), tool("lookup_weather")], next_cursor="page2"),
            SimpleNamespace(tools=[tool("compute_routes")], next_cursor=None),
        ]))

        @asynccontextmanager
        async def fake_session():
            yield session

        with patch.object(maps_mcp, "maps_session", fake_session):
            result = await maps_mcp.listar_ferramentas_maps()
        self.assertEqual([item["name"] for item in result], list(maps_mcp.MAPS_TOOLS))
        self.assertEqual(session.list_tools.await_count, 2)
        self.assertEqual(session.list_tools.call_args.kwargs["params"].cursor, "page2")

    async def test_missing_remote_tool_is_reported(self):
        session = SimpleNamespace(list_tools=AsyncMock(return_value=SimpleNamespace(tools=[tool("search_places")], next_cursor=None)))

        @asynccontextmanager
        async def fake_session():
            yield session

        with patch.object(maps_mcp, "maps_session", fake_session):
            with self.assertRaisesRegex(RuntimeError, "compute_routes"):
                await maps_mcp.listar_ferramentas_maps()
