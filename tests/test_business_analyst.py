import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import psycopg

from app.tools import business_analyst_tools as analyst
from app.tools import discard_tools as shared
from app.tools import ranking_sustainable_tools as ranking
from test_ranking_sustainable import CONFIG, USER_ID, database


class BusinessAnalystTests(unittest.TestCase):
    def setUp(self):
        patched = patch.object(shared, "hoje_local", return_value=date(2026, 10, 20))
        patched.start()
        self.addCleanup(patched.stop)

    def test_default_window_and_current_month(self):
        period = shared.periodo_descarte()
        self.assertEqual(period["inicio"], date(2026, 7, 1))
        self.assertEqual(period["fim"], date(2026, 10, 20))
        self.assertEqual([m["parcial"] for m in period["meses"]], [False, False, False, True])

    def test_year_boundary_and_leap_year(self):
        with patch.object(shared, "hoje_local", return_value=date(2024, 3, 1)):
            period = shared.periodo_descarte()
        self.assertEqual(period["inicio"], date(2023, 12, 1))
        self.assertEqual(period["meses"][2]["fim"], date(2024, 2, 29))
        self.assertTrue(period["meses"][-1]["parcial"])

    def test_explicit_clipped_months_are_partial(self):
        period = shared.periodo_descarte(date(2026, 7, 15), date(2026, 9, 10))
        self.assertEqual([m["parcial"] for m in period["meses"]], [True, False, True])

    def test_future_dates_are_rejected(self):
        with self.assertRaises(ValueError):
            shared.periodo_descarte(data_fim=date(2026, 10, 21))

    def test_history_is_same_tool_for_both_agents(self):
        self.assertIs(analyst.TOOLS_BUSINESS_ANALYST[0], ranking.TOOLS_RANKING_SUSTAINABLE[1])
        self.assertNotIn(analyst.analisar_descarte_periodo, ranking.TOOLS_RANKING_SUSTAINABLE)

    def test_history_pagination_and_default_period(self):
        conn, cur = database("CITIZENS", rows=[{"id": 1}, {"id": 2}, {"id": 3}])
        with patch.object(shared, "get_conn", return_value=conn):
            result = shared.consultar_historico_descarte.invoke({"limite": 2, "pagina": 2}, config=CONFIG)
        self.assertEqual(cur.execute.call_args.args[1], [USER_ID, date(2026, 7, 1), date(2026, 10, 20), 3, 2])
        self.assertEqual(result["count"], 2)
        self.assertTrue(result["tem_proxima_pagina"])
        self.assertTrue(result["periodo"]["meses"][-1]["parcial"])

    def test_indicators_aggregate_all_rows_and_comparisons(self):
        rows = [
            {"mes": "2026-07", "quantidade": 120, "litros": Decimal(120), "sucessos": 60},
            {"mes": "2026-08", "quantidade": 10, "litros": Decimal(180), "sucessos": 10},
            {"mes": "2026-10", "quantidade": 2, "litros": Decimal(10), "sucessos": 2},
        ]
        conn, cur = database("ESTABLISHMENT", rows=rows)
        with patch.object(analyst, "get_conn", return_value=conn):
            result = analyst.analisar_descarte_periodo.invoke({}, config=CONFIG)
        self.assertEqual(result["totais"]["quantidade"], 132)
        self.assertEqual(result["totais"]["litros"], "310")
        self.assertEqual(result["mensal"][0]["taxa_sucesso_percentual"], "50")
        self.assertEqual(result["mensal"][2]["quantidade"], 0)
        self.assertEqual(len(result["comparacoes_meses_completos"]), 2)
        self.assertEqual(result["comparacoes_meses_completos"][0]["variacao_percentual"], "50")
        sql, params = cur.execute.call_args.args
        self.assertNotIn("LIMIT", sql)
        self.assertIn("SUM(litros)", sql)
        self.assertIn("establishment_id = %s", sql)
        self.assertEqual(params[0], USER_ID)

    def test_citizen_has_no_success_rate_and_zero_base_is_null(self):
        conn, _ = database("CITIZENS", rows=[
            {"mes": "2026-08", "quantidade": 1, "litros": Decimal(4), "sucessos": 0},
        ])
        with patch.object(analyst, "get_conn", return_value=conn):
            result = analyst.analisar_descarte_periodo.invoke({}, config=CONFIG)
        self.assertIsNone(result["totais"]["taxa_sucesso_percentual"])
        self.assertIsNone(result["totais"]["coletas_bem_sucedidas"])
        self.assertTrue(result["comparacoes_meses_completos"][0]["base_zero"])
        self.assertIsNone(result["comparacoes_meses_completos"][0]["variacao_percentual"])

    def test_empty_period_has_zero_volume_and_no_average(self):
        conn, _ = database("CITIZENS")
        with patch.object(analyst, "get_conn", return_value=conn):
            result = analyst.analisar_descarte_periodo.invoke({}, config=CONFIG)
        self.assertEqual(result["totais"]["litros"], "0")
        self.assertIsNone(result["totais"]["media_litros_por_operacao"])
        self.assertEqual(len(result["mensal"]), 4)

    def test_identity_and_database_error(self):
        with patch.object(analyst, "get_conn") as connect:
            result = analyst.analisar_descarte_periodo.invoke({}, config={})
        self.assertEqual(result["status"], "error")
        connect.assert_not_called()
        with patch.object(analyst, "get_conn", side_effect=psycopg.OperationalError("SECRET")):
            result = analyst.analisar_descarte_periodo.invoke({}, config=CONFIG)
        self.assertEqual(result["status"], "error")
        self.assertNotIn("SECRET", str(result))


if __name__ == "__main__":
    unittest.main()
