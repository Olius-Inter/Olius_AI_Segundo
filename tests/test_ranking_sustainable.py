"""Testes das duas tools, sem credenciais, rede ou banco real."""

import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import psycopg
from pydantic import ValidationError

from app.tools import db
from app.tools import ranking_sustainable_tools as tools
from app.tools import discard_tools as shared

USER_ID = "00000000-0000-0000-0000-000000000001"
CONFIG = {"configurable": {"user_id": USER_ID}}


def database(profile, ranking=None, rows=None):
    conn = MagicMock()
    cur = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
    cur.fetchone.side_effect = [{"perfil": profile} if profile else None, ranking]
    cur.fetchall.return_value = rows or []
    return conn, cur


class RankingToolsTests(unittest.TestCase):
    def test_identity_is_hidden_from_model(self):
        for tool in tools.TOOLS_RANKING_SUSTAINABLE:
            properties = tool.tool_call_schema.model_json_schema().get("properties", {})
            self.assertNotIn("config", properties)
            self.assertNotIn("user_id", properties)

    def test_missing_or_invalid_identity_never_opens_database(self):
        for config in ({}, {"configurable": {"user_id": "invalid"}}):
            with patch.object(tools, "get_conn") as connect, patch.object(shared, "get_conn") as history_connect:
                for tool in tools.TOOLS_RANKING_SUSTAINABLE:
                    self.assertEqual(tool.invoke({}, config=config)["status"], "error")
                connect.assert_not_called()
                history_connect.assert_not_called()

    def test_citizen_without_ranking(self):
        conn, cur = database("CITIZENS")
        with patch.object(tools, "get_conn", return_value=conn):
            result = tools.consultar_nivel_ranking.invoke({}, config=CONFIG)
        self.assertFalse(result["participa_ranking"])
        self.assertIsNone(result["nivel_atual"])
        self.assertEqual(result["situacao_niveis"], "nao_aplicavel_cidadao")
        self.assertEqual(cur.execute.call_args.args[1], (USER_ID, "B2C"))
        self.assertEqual(cur.execute.call_count, 3)
        conn.__exit__.assert_called_once()

    def test_establishment_certificate_progress(self):
        levels = [
            {"is_level_reached": True, "required_liters": Decimal("10.00")},
            {"is_level_reached": False, "required_liters": Decimal("20.00")},
        ]
        conn, cur = database("ESTABLISHMENT", {"ranking_position": 2}, levels)
        with patch.object(tools, "get_conn", return_value=conn):
            result = tools.consultar_nivel_ranking.invoke({}, config=CONFIG)
        self.assertEqual(result["ranking"]["ranking_position"], 2)
        self.assertEqual(result["nivel_atual"]["required_liters"], "10.00")
        self.assertEqual(result["proximo_nivel"]["required_liters"], "20.00")
        self.assertIn("get_certificate_progress", cur.execute.call_args.args[0])

    def test_no_configured_levels(self):
        conn, _ = database("ESTABLISHMENT")
        with patch.object(tools, "get_conn", return_value=conn):
            result = tools.consultar_nivel_ranking.invoke({}, config=CONFIG)
        self.assertEqual(result["situacao_niveis"], "sem_niveis_cadastrados")
        self.assertIsNone(result["proximo_nivel"])

    def test_inactive_missing_or_admin_not_participant(self):
        for profile in (None, "ADMIN"):
            conn, cur = database(profile)
            with patch.object(tools, "get_conn", return_value=conn):
                result = tools.consultar_nivel_ranking.invoke({}, config=CONFIG)
            self.assertEqual(result["status"], "error")
            self.assertEqual(cur.execute.call_count, 2)
            self.assertIn("status = 'ACTIVE'", cur.execute.call_args.args[0])

    def test_history_filters_ownership_and_serialization(self):
        for profile, table, owner in (
            ("CITIZENS", "delivery_pev", "citizen_id"),
            ("ESTABLISHMENT", "collection", "establishment_id"),
        ):
            conn, cur = database(profile, rows=[{"litros": Decimal("2.50")}])
            with patch.object(shared, "get_conn", return_value=conn):
                result = tools.consultar_historico_descarte.invoke(
                    {"data_inicio": "2026-10-01", "data_fim": "2026-10-19", "limite": 5},
                    config=CONFIG,
                )
            sql, params = cur.execute.call_args.args
            self.assertIn("public." + table, sql)
            self.assertIn(owner + " = %s", sql)
            self.assertIn("record_status = 'RECORDED'", sql)
            self.assertIn("INTERVAL '1 day'", sql)
            self.assertIn("America/Sao_Paulo", sql)
            self.assertEqual(params, [USER_ID, date(2026, 10, 1), date(2026, 10, 19), 6, 0])
            self.assertEqual(result["results"][0]["litros"], "2.50")
            self.assertEqual(result["count"], 1)

    def test_empty_history_is_success_not_error(self):
        conn, _ = database("CITIZENS")
        with patch.object(shared, "get_conn", return_value=conn):
            result = tools.consultar_historico_descarte.invoke({}, config=CONFIG)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["results"], [])

    def test_invalid_period_never_opens_database(self):
        with patch.object(tools, "get_conn") as connect, patch.object(shared, "get_conn") as history_connect:
            result = tools.consultar_historico_descarte.invoke(
                {"data_inicio": "2026-10-20", "data_fim": "2026-10-19"}, config=CONFIG,
            )
        self.assertEqual(result["status"], "error")
        connect.assert_not_called()

    def test_schema_rejects_invalid_dates_and_limits(self):
        for args in ({"limite": 0}, {"limite": 101}, {"data_inicio": "2026-02-30"}):
            with self.assertRaises(ValidationError):
                shared.ConsultarHistoricoDescarteArgs(**args)

    def test_database_failure_is_sanitized_and_resources_close(self):
        for tool in tools.TOOLS_RANKING_SUSTAINABLE:
            conn, cur = database("CITIZENS")
            cur.execute.side_effect = psycopg.OperationalError("SECRET")
            with patch.object(tools, "get_conn", return_value=conn), patch.object(shared, "get_conn", return_value=conn):
                result = tool.invoke({}, config=CONFIG)
            self.assertEqual(result["status"], "error")
            self.assertNotIn("SECRET", str(result))
            conn.__exit__.assert_called_once()

    def test_connection_requires_database_url(self):
        with patch.object(db, "DATABASE_URL", None), patch.object(db.psycopg, "connect") as connect:
            with self.assertRaises(RuntimeError):
                db.get_conn()
        connect.assert_not_called()

    def test_connection_is_read_only_and_has_timeout(self):
        with patch.object(db, "DATABASE_URL", "test-dsn"), patch.object(db.psycopg, "connect") as connect:
            db.get_conn()
        self.assertIn("default_transaction_read_only=on", connect.call_args.kwargs["options"])
        self.assertEqual(connect.call_args.kwargs["connect_timeout"], 5)


if __name__ == "__main__":
    unittest.main()
