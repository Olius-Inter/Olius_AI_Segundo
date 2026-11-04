"""Testes unitários de app.ingest_faq sem PDF real, Qdrant ou embeddings."""

import importlib
import runpy
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock
import pytest
from langchain_core.documents import Document
from qdrant_client import models

def _chunks(quantidade):
    return [
        Document(
            page_content=f"chunk {i}",
            metadata={"page": i, "source": f"faq-{i}.pdf"},
        )
        for i in range(quantidade)
    ]


@pytest.fixture
def ingest(monkeypatch):
    """Importa app.ingest_faq com vectorstore, leitor de PDF e splitter falsos."""
    vectorstore_module = ModuleType("app.vectorstore")
    vectorstore_module.qdrant = MagicMock(name="qdrant")
    vectorstore_module.qdrant.get_collection.return_value = SimpleNamespace(
        points_count=0
    )
    vectorstore_module.gerar_embeddings_batch = MagicMock(
        side_effect=lambda textos: [[float(i)] for i, _ in enumerate(textos)]
    )
    vectorstore_module.COLLECTION_FAQ = "faq_chunks"

    monkeypatch.setitem(sys.modules, "app.vectorstore", vectorstore_module)
    monkeypatch.delitem(sys.modules, "app.ingest_faq", raising=False)

    modulo = importlib.import_module("app.ingest_faq")

    loader = MagicMock(name="PyPDFLoader_instance")
    loader.load.return_value = ["pagina"]
    monkeypatch.setattr(modulo, "PyPDFLoader", MagicMock(return_value=loader))

    splitter = MagicMock(name="splitter_instance")
    splitter.split_documents.return_value = _chunks(3)
    monkeypatch.setattr(
        modulo, "RecursiveCharacterTextSplitter", MagicMock(return_value=splitter)
    )

    return SimpleNamespace(
        modulo=modulo,
        vectorstore=vectorstore_module,
        loader=loader,
        splitter=splitter,
    )


def test_ingerir_faq_retorna_quantidade_de_chunks(ingest):
    assert ingest.modulo.ingerir_faq() == 3


def test_ingerir_faq_carrega_o_pdf_configurado(ingest):
    ingest.modulo.ingerir_faq()

    ingest.modulo.PyPDFLoader.assert_called_once_with(
        str(ingest.modulo.FAQ_PDF_PATH)
    )
    ingest.splitter.split_documents.assert_called_once_with(["pagina"])


def test_ingerir_faq_configura_splitter_com_tamanho_e_overlap(ingest):
    ingest.modulo.ingerir_faq()

    ingest.modulo.RecursiveCharacterTextSplitter.assert_called_once_with(
        chunk_size=700, chunk_overlap=150
    )


def test_ingerir_faq_nao_limpa_colecao_vazia(ingest):
    ingest.modulo.ingerir_faq()

    ingest.vectorstore.qdrant.delete.assert_not_called()


def test_ingerir_faq_limpa_colecao_com_pontos_existentes(ingest):
    qdrant = ingest.vectorstore.qdrant
    qdrant.get_collection.return_value = SimpleNamespace(points_count=12)

    ingest.modulo.ingerir_faq()

    qdrant.delete.assert_called_once()
    kwargs = qdrant.delete.call_args.kwargs
    assert kwargs["collection_name"] == "faq_chunks"
    assert isinstance(kwargs["points_selector"], models.FilterSelector)
    assert kwargs["points_selector"].filter.must == []


def test_ingerir_faq_limpa_antes_de_inserir(ingest):
    qdrant = ingest.vectorstore.qdrant
    qdrant.get_collection.return_value = SimpleNamespace(points_count=5)
    ordem = []
    qdrant.delete.side_effect = lambda **kw: ordem.append("delete")
    qdrant.upsert.side_effect = lambda **kw: ordem.append("upsert")

    ingest.modulo.ingerir_faq()

    assert ordem == ["delete", "upsert"]


def test_ingerir_faq_gera_pontos_com_vetor_e_payload(ingest):
    ingest.modulo.ingerir_faq()

    upsert = ingest.vectorstore.qdrant.upsert
    upsert.assert_called_once()
    assert upsert.call_args.kwargs["collection_name"] == "faq_chunks"

    pontos = upsert.call_args.kwargs["points"]
    assert len(pontos) == 3
    for i, ponto in enumerate(pontos):
        assert ponto.vector == [float(i)]
        assert ponto.payload == {
            "page_content": f"chunk {i}",
            "page_number": i,
            "source": f"faq-{i}.pdf",
        }


def test_ingerir_faq_gera_ids_unicos(ingest):
    ingest.modulo.ingerir_faq()

    pontos = ingest.vectorstore.qdrant.upsert.call_args.kwargs["points"]
    ids = [ponto.id for ponto in pontos]

    assert len(set(ids)) == len(ids)


def test_ingerir_faq_usa_valores_padrao_sem_metadados(ingest):
    ingest.splitter.split_documents.return_value = [Document(page_content="solto")]

    ingest.modulo.ingerir_faq()

    ponto = ingest.vectorstore.qdrant.upsert.call_args.kwargs["points"][0]
    assert ponto.payload["page_number"] == 0
    assert ponto.payload["source"] == ""


def test_ingerir_faq_processa_em_lotes(ingest, monkeypatch):
    monkeypatch.setattr(ingest.modulo, "BATCH_SIZE", 2)
    ingest.splitter.split_documents.return_value = _chunks(5)

    total = ingest.modulo.ingerir_faq()

    embeddings = ingest.vectorstore.gerar_embeddings_batch
    upsert = ingest.vectorstore.qdrant.upsert
    assert total == 5
    assert embeddings.call_count == 3
    assert [len(c.args[0]) for c in embeddings.call_args_list] == [2, 2, 1]
    assert [len(c.kwargs["points"]) for c in upsert.call_args_list] == [2, 2, 1]


def test_ingerir_faq_envia_textos_dos_chunks_para_embedding(ingest):
    ingest.modulo.ingerir_faq()

    ingest.vectorstore.gerar_embeddings_batch.assert_called_once_with(
        ["chunk 0", "chunk 1", "chunk 2"]
    )


def test_ingerir_faq_sem_chunks_nao_insere_nada(ingest):
    ingest.splitter.split_documents.return_value = []

    assert ingest.modulo.ingerir_faq() == 0

    ingest.vectorstore.gerar_embeddings_batch.assert_not_called()
    ingest.vectorstore.qdrant.upsert.assert_not_called()


def test_ingerir_faq_propaga_erro_de_leitura_do_pdf(ingest):
    ingest.loader.load.side_effect = FileNotFoundError("faq.pdf")

    with pytest.raises(FileNotFoundError):
        ingest.modulo.ingerir_faq()

    ingest.vectorstore.qdrant.upsert.assert_not_called()


def test_ingerir_faq_imprime_progresso(ingest, capsys):
    ingest.modulo.ingerir_faq()

    saida = capsys.readouterr().out
    assert "3 chunk(s) gerado(s)" in saida
    assert "Concluído! 3 chunk(s) indexado(s)" in saida


def test_execucao_como_script_dispara_a_ingestao(ingest, monkeypatch):
    loader = MagicMock()
    loader.load.return_value = ["pagina"]
    splitter = MagicMock()
    splitter.split_documents.return_value = _chunks(2)
    monkeypatch.setattr(
        "langchain_community.document_loaders.PyPDFLoader",
        MagicMock(return_value=loader),
    )
    monkeypatch.setattr(
        "langchain_text_splitters.RecursiveCharacterTextSplitter",
        MagicMock(return_value=splitter),
    )

    monkeypatch.delitem(sys.modules, "app.ingest_faq")

    runpy.run_module("app.ingest_faq", run_name="__main__")

    ingest.vectorstore.qdrant.upsert.assert_called_once()
    assert len(ingest.vectorstore.qdrant.upsert.call_args.kwargs["points"]) == 2
