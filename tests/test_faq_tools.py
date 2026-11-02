"""Testes unitários de app.tools.faq_tools sem Qdrant ou embeddings reais."""

import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def faq_tools(monkeypatch):
    """Importa app.tools.faq_tools com app.vectorstore substituído por um mock."""
    vectorstore_module = ModuleType("app.vectorstore")
    vectorstore_module.qdrant = MagicMock(name="qdrant")
    vectorstore_module.gerar_embedding = MagicMock(
        name="gerar_embedding", return_value=[0.1, 0.2, 0.3]
    )
    vectorstore_module.COLLECTION_FAQ = "faq_chunks"
    monkeypatch.setitem(sys.modules, "app.vectorstore", vectorstore_module)
    monkeypatch.delitem(sys.modules, "app.tools.faq_tools", raising=False)
    return importlib.import_module("app.tools.faq_tools"), vectorstore_module


def _pontos(*textos):
    return SimpleNamespace(
        points=[SimpleNamespace(payload={"page_content": t}) for t in textos]
    )

def test_faq_retriever_junta_trechos_encontrados(faq_tools):
    modulo, vectorstore = faq_tools
    vectorstore.qdrant.query_points.return_value = _pontos("trecho 1", "trecho 2")
    resultado = modulo.faq_retriever.invoke({"question": "O que é o Olius?"})
    assert resultado == "trecho 1\n\ntrecho 2"

def test_faq_retriever_consulta_qdrant_com_embedding_da_pergunta(faq_tools):
    modulo, vectorstore = faq_tools
    vectorstore.qdrant.query_points.return_value = _pontos("trecho")
    modulo.faq_retriever.invoke({"question": "Como descartar óleo?"})
    vectorstore.gerar_embedding.assert_called_once_with("Como descartar óleo?")
    vectorstore.qdrant.query_points.assert_called_once_with(
        collection_name="faq_chunks",
        query=[0.1, 0.2, 0.3],
        limit=6,
    )

def test_faq_retriever_sem_resultados_informa_que_nao_encontrou(faq_tools):
    modulo, vectorstore = faq_tools
    vectorstore.qdrant.query_points.return_value = _pontos()
    resultado = modulo.faq_retriever.invoke({"question": "pergunta sem resposta"})
    assert resultado == "Nenhum trecho relevante encontrado no FAQ."

def test_faq_retriever_com_um_unico_trecho_nao_adiciona_separador(faq_tools):
    modulo, vectorstore = faq_tools
    vectorstore.qdrant.query_points.return_value = _pontos("único")
    assert modulo.faq_retriever.invoke({"question": "q"}) == "único"

def test_faq_retriever_propaga_erro_do_qdrant(faq_tools):
    modulo, vectorstore = faq_tools
    vectorstore.qdrant.query_points.side_effect = ConnectionError("qdrant fora")
    with pytest.raises(ConnectionError):
        modulo.faq_retriever.invoke({"question": "q"})

def test_faq_retriever_declara_nome_e_descricao_para_o_agente(faq_tools):
    modulo, _ = faq_tools
    assert modulo.faq_retriever.name == "faq_retriever"
    assert "FAQ" in modulo.faq_retriever.description
