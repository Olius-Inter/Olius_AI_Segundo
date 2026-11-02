"""Inicialização real dos agentes e da API, com serviços externos bloqueados."""
import subprocess
import sys
from pathlib import Path


def test_aplicacao_real_inicia_e_recusa_acesso_anonimo():
    script = '''
import os
from unittest.mock import patch
import dotenv
import qdrant_client
import pymongo
from fastapi.testclient import TestClient

dotenv.load_dotenv = lambda *args, **kwargs: False
os.environ.update({
    "CHATGPT_API_KEY": "sk-test-not-a-real-key",
    "GROQ_API_KEY": "gsk_test_not_a_real_key",
    "MONGODB_URI": "mongodb://test.invalid",
    "DATABASE_URL": "postgresql://test:test@test.invalid/test",
    "CORE_AUTH_URL": "https://core.test.invalid/auth/status",
    "CORS_ORIGINS": "http://localhost:8000",
    "QDRANT_URL": "https://qdrant.test.invalid",
    "QDRANT_API_KEY": "not-a-real-key",
})
with patch.object(qdrant_client, "QdrantClient"), patch.object(pymongo, "MongoClient", side_effect=AssertionError("Acesso ao MongoDB inesperado")):
    from app.main import app
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/monitor").status_code == 200
        assert client.get("/api/v1/monitor").status_code == 401
        response = client.post("/api/v1/chat", json={
            "session_id": "00000000-0000-0000-0000-000000000001", "pergunta": "Olá",
        })
        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"
'''
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=Path(__file__).parents[1],
        capture_output=True, text=True, timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
