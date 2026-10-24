import unittest
from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from app.tools import routes_maps_tools as tools

USER = "00000000-0000-0000-0000-000000000001"
ADDRESS = UUID("00000000-0000-0000-0000-000000000002")
CONFIG = {"configurable": {"user_id": USER, "localizacao": {"latitude": -23.5, "longitude": -46.7}}}


def local(distance=Decimal("226.68"), **changes):
    return {"id": UUID(USER), "endereco_id": ADDRESS, "tipo": "PEV", "nome": "PEV teste",
            "rua": "Rua teste", "numero": "1", "bairro": "Centro", "cidade": "Osasco", "estado": "SP",
            "cep": "00000000", "latitude": Decimal("-23.5"), "longitude": Decimal("-46.7"),
            "distancia_linha_reta_metros": distance, **changes}


class RoutesMapsTests(unittest.IsolatedAsyncioTestCase):
    def test_radius_is_computed_without_query_per_step(self):
        raio, selected = tools.selecionar_raio([local(), local(Decimal(249)), local(Decimal(251))], 100, 5000)
        self.assertEqual(raio, 250)
        self.assertEqual(len(selected), 2)
        self.assertEqual(tools.selecionar_raio([], 100, 5000), (5000, []))
        self.assertEqual(tools.selecionar_raio([local(Decimal("100.4"))], 100, 5000)[0], 150)

    def test_no_geo_default_or_invalid_coordinates(self):
        for bad in (None, {"latitude": 91, "longitude": 0}, {"latitude": "nan", "longitude": 0}):
            with self.assertRaises(ValueError):
                tools.coordenadas(bad)
        with self.assertRaises(ValueError):
            tools.origem_execucao({})

    def test_origin_and_destination_can_be_addresses(self):
        self.assertEqual(tools.origem_execucao(CONFIG, "Osasco, SP"), {"address": "Osasco, SP"})
        point = tools._destino(local(latitude=None, longitude=None))
        self.assertIn("Rua teste", point["address"])
        args = tools._argumentos_rota({"travelMode": {}}, tools.origem_execucao(CONFIG), point, "WALK")
        self.assertIn("latLng", args["origin"])
        self.assertEqual(args["destination"], point)

    def test_query_is_parameterized_and_has_no_result_limit(self):
        conn = MagicMock()
        cur = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value = {"id": USER}
        cur.fetchall.return_value = [local()]
        city = "Osasco' OR '1'='1"
        with patch.object(tools, "get_conn", return_value=conn):
            rows = tools._consultar_locais(CONFIG, tools.origem_execucao(CONFIG), city, "SP")
        sql, params = cur.execute.call_args.args
        self.assertNotIn(city, sql)
        self.assertIn(city, params)
        self.assertNotIn("LIMIT", sql)
        self.assertIn("p.status = 'APPROVED'", sql)
        self.assertIn("u.status = 'ACTIVE'", sql)
        self.assertNotIn("public.establishment", sql)
        self.assertNotIn("UNION ALL", sql)
        self.assertEqual(len(rows), 1)

    def test_active_b2b_and_b2c_users_need_no_extra_permission(self):
        cur = MagicMock()
        for profile in ("ESTABLISHMENT", "CITIZENS"):
            cur.fetchone.return_value = {"id": USER, "perfil": profile}
            tools._validar_usuario(cur, CONFIG)
            self.assertIn("status = 'ACTIVE'", cur.execute.call_args.args[0])
        cur.fetchone.return_value = None
        with self.assertRaises(ValueError):
            tools._validar_usuario(cur, CONFIG)

    def test_schemas_hide_identity_and_location(self):
        for tool in tools.TOOLS_ROUTES_MAPS:
            schema = tool.tool_call_schema.model_json_schema()
            self.assertNotIn("user_id", schema["properties"])
            self.assertNotIn("config", schema["properties"])
            self.assertNotIn("tipo", schema["properties"])
        fields = tools.CalcularTemposDeslocamentoArgs.model_fields
        self.assertNotIn("limite", fields)
        self.assertNotIn("raio_maximo", fields)

    async def test_nearby_delegates_to_second_tool_and_reports_missing_coordinates(self):
        all_rows = [local(), local(None)]
        calculate = AsyncMock(return_value={"status": "ok", "quantidade": 1, "resultados": []})
        with patch.object(tools, "_consultar_locais", return_value=all_rows) as query, patch.object(tools, "calcular_tempos_deslocamento", SimpleNamespace(ainvoke=calculate)):
            result = await tools.buscar_locais_proximos.ainvoke({}, config=CONFIG)
        self.assertEqual(query.call_count, 1)
        self.assertNotIn("tipo", query.call_args.kwargs)
        self.assertEqual(result["raio_utilizado_metros"], 250)
        self.assertEqual(result["cadastros_sem_coordenadas"], 1)
        self.assertFalse(result["busca_completa"])
        self.assertEqual(calculate.call_args.args[0]["ids_enderecos"], [str(ADDRESS)])
        self.assertNotIn("tipo", calculate.call_args.args[0])

    async def test_nearby_without_candidates_does_not_call_maps(self):
        calculate = AsyncMock()
        with patch.object(tools, "_consultar_locais", return_value=[]), patch.object(tools, "calcular_tempos_deslocamento", SimpleNamespace(ainvoke=calculate)):
            result = await tools.buscar_locais_proximos.ainvoke({}, config=CONFIG)
        self.assertEqual(result["status"], "sem_resultados_no_raio")
        calculate.assert_not_called()

    async def test_direct_city_does_not_cut_results(self):
        rows = [local() for _ in range(125)]
        computed = [{**row, "trajetos": [{"status": "ok"}, {"status": "ok"}]} for row in rows]
        with patch.object(tools, "_consultar_locais", return_value=rows), patch.object(tools, "_calcular_todos", new_callable=AsyncMock, return_value=computed) as calculate:
            result = await tools.calcular_tempos_deslocamento.ainvoke({"cidade": "Osasco"}, config=CONFIG)
        self.assertEqual(result["quantidade"], 125)
        self.assertEqual(len(calculate.call_args.args[0]), 125)

    async def test_missing_identity_and_origin_do_not_query_database(self):
        for config in ({}, {"configurable": {"user_id": USER}}):
            with patch.object(tools, "_consultar_locais") as query:
                result = await tools.buscar_locais_proximos.ainvoke({}, config=config)
            self.assertEqual(result["status"], "error")
            query.assert_not_called()

    async def test_invalid_radius_and_missing_city(self):
        with patch.object(tools, "_consultar_locais") as query:
            result = await tools.buscar_locais_proximos.ainvoke({"raio_inicial_metros": 300, "raio_maximo_metros": 200}, config=CONFIG)
            self.assertEqual(result["status"], "error")
            result = await tools.calcular_tempos_deslocamento.ainvoke({}, config=CONFIG)
            self.assertEqual(result["status"], "error")
        query.assert_not_called()

    async def test_modes_independent_and_attribution_preserved(self):
        attribution = {"title": "Google Maps", "url": "https://maps.google.com"}
        response = SimpleNamespace(is_error=False, structured_content={"routes": [{"distanceMeters": 1200, "duration": "997s", "attribution": attribution}]})
        session = SimpleNamespace(
            list_tools=AsyncMock(return_value=SimpleNamespace(tools=[SimpleNamespace(name="compute_routes", input_schema={"properties": {"travel_mode": {}}})], next_cursor=None)),
            call_tool=AsyncMock(side_effect=[RuntimeError("SECRET"), response]),
        )

        @asynccontextmanager
        async def fake_session():
            yield session

        with patch.object(tools, "maps_session", fake_session):
            result = await tools._calcular_todos([local()], tools.origem_execucao(CONFIG))
        drive, walk = result[0]["trajetos"]
        self.assertEqual(drive["status"], "error")
        self.assertNotIn("SECRET", str(result))
        self.assertEqual(walk["duracao_minutos"], 16.6)
        self.assertEqual(walk["attribution"], attribution)
        self.assertIn("beta", walk["aviso"])
        self.assertEqual(tools._status_resultados(result), "parcial")

    def test_bad_route_does_not_become_zero(self):
        for distance in (None, -1, float("nan")):
            response = SimpleNamespace(is_error=False, structured_content={"routes": [{"distanceMeters": distance, "duration": "10s"}]})
            with self.assertRaises(ValueError):
                tools._resumir_rota(response, "DRIVE")
        empty = SimpleNamespace(is_error=False, structured_content={"routes": []})
        self.assertEqual(tools._resumir_rota(empty, "DRIVE")["status"], "sem_rota")
