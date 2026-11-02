"""Embeddings sem chamadas a provedores ou ao Qdrant."""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest
import langchain_openai
import qdrant_client


@pytest.fixture
def vectorstore(monkeypatch):
    config = ModuleType("app.config")
    config.CHATGPT_API_KEY = "test-chatgpt-key"
    config.QDRANT_URL = "http://localhost:6333"
    config.QDRANT_API_KEY = None
    monkeypatch.setitem(sys.modules, "app.config", config)
    embeddings = Mock()
    embeddings.embed_query.return_value = [0.1] * 768
    embeddings.embed_documents.return_value = [[0.2] * 768]
    factory = Mock(return_value=embeddings)
    monkeypatch.setattr(langchain_openai, "OpenAIEmbeddings", factory)
    qdrant = Mock()
    qdrant.collection_exists.return_value = False
    monkeypatch.setattr(qdrant_client, "QdrantClient", Mock(return_value=qdrant))
    path = Path(__file__).parents[1] / "app/vectorstore.py"
    spec = importlib.util.spec_from_file_location("vectorstore_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, factory, embeddings, qdrant


def test_cliente_lazy_com_chave_existente_e_dimensoes_corretas(vectorstore):
    module, factory, embeddings, qdrant = vectorstore
    factory.assert_not_called()
    assert len(module.gerar_embedding("Resumo")) == 768
    assert module.gerar_embeddings_batch(["FAQ"]) == [[0.2] * 768]
    factory.assert_called_once_with(model="text-embedding-3-small", api_key="test-chatgpt-key", dimensions=768)
    embeddings.embed_query.assert_called_once_with("Resumo")
    embeddings.embed_documents.assert_called_once_with(["FAQ"])
    qdrant.create_collection.assert_called_once()
    assert qdrant.create_collection.call_args.kwargs["collection_name"] == "memoria_resumos_openai_768"
    qdrant.delete_collection.assert_not_called()


def test_reutiliza_colecao_sem_recriar(vectorstore):
    module, _, _, qdrant = vectorstore
    qdrant.collection_exists.return_value = True
    module.gerar_embedding("Primeiro")
    module.gerar_embedding("Segundo")
    qdrant.collection_exists.assert_called_once()
    qdrant.create_collection.assert_not_called()


def test_chave_ausente_nao_tenta_autenticacao_google(vectorstore, monkeypatch):
    module, factory, _, qdrant = vectorstore
    monkeypatch.setattr(module, "CHATGPT_API_KEY", None)
    with pytest.raises(RuntimeError, match="CHATGPT_API_KEY"):
        module.obter_embeddings()
    factory.assert_not_called()
    qdrant.create_collection.assert_not_called()
