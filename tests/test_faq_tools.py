import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import langchain_community.document_loaders
import langchain_community.vectorstores
import langchain_text_splitters


def test_faq_carrega_pdf_e_reutiliza_embeddings_sob_demanda(monkeypatch):
    config = ModuleType("app.config")
    config.FAQ_PDF_PATH = Path("faq-teste.pdf")
    vectors = ModuleType("app.vectorstore")
    vectors.obter_embeddings = Mock()
    monkeypatch.setitem(sys.modules, "app.config", config)
    monkeypatch.setitem(sys.modules, "app.vectorstore", vectors)
    loader, splitter, faiss = Mock(), Mock(), Mock()
    monkeypatch.setattr(langchain_community.document_loaders, "PyPDFLoader", loader)
    monkeypatch.setattr(langchain_text_splitters, "RecursiveCharacterTextSplitter", splitter)
    monkeypatch.setattr(langchain_community.vectorstores, "FAISS", faiss)
    faiss.from_documents.return_value.similarity_search.return_value = ["Trecho oficial"]
    spec = importlib.util.spec_from_file_location("faq_under_test", Path(__file__).parents[1] / "app/tools/faq_tools.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    loader.assert_not_called()
    assert module.faq_retriever.invoke({"question": "Como descartar?"}) == ["Trecho oficial"]
    loader.assert_called_once_with(config.FAQ_PDF_PATH)
    vectors.obter_embeddings.assert_called_once()
    faiss.from_documents.assert_called_once_with(splitter.return_value.split_documents.return_value, vectors.obter_embeddings.return_value)
    faiss.from_documents.return_value.similarity_search.assert_called_once_with("Como descartar?", k=6)
