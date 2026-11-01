"""Testes unitários de app.memory sem MongoDB, Qdrant ou chamadas reais a LLM."""

import importlib
import sys
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, call
import pytest

class FakeCursor(list):
    def sort(self, *args, **kwargs):
        return self

    def limit(self, amount):
        return FakeCursor(self[:amount])

@pytest.fixture
def memory_module(monkeypatch):
    """Importa app.memory com todos os serviços externos substituídos por mocks."""
    collection = MagicMock(name="col_sessoes")
    collection.find.return_value = FakeCursor([])

    mongo_client = MagicMock(name="MongoClient")
    database = MagicMock(name="database")
    mongo_client.return_value.__getitem__.return_value = database
    database.__getitem__.return_value = collection

    pymongo_module = ModuleType("pymongo")
    pymongo_module.MongoClient = mongo_client

    class FakePointStruct:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FakeFilter:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FakeFieldCondition:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FakeMatchValue:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    qdrant_models = SimpleNamespace(
        PointStruct=FakePointStruct,
        Filter=FakeFilter,
        FieldCondition=FakeFieldCondition,
        MatchValue=FakeMatchValue,
    )
    qdrant_client_module = ModuleType("qdrant_client")
    qdrant_client_module.models = qdrant_models

    llms_module = ModuleType("app.llms")
    llms_module.llm_rapido = MagicMock(name="llm_rapido")

    config_module = ModuleType("app.config")
    config_module.MONGODB_URI = "mongodb://test.invalid"
    config_module.QDRANT_URL = "https://qdrant.test.invalid"
    config_module.QDRANT_API_KEY = "test-key"
    config_module.GEMINI_API_KEY = "test-key"

    qdrant = MagicMock(name="qdrant")
    vectorstore_module = ModuleType("app.vectorstore")
    vectorstore_module.qdrant = qdrant
    vectorstore_module.gerar_embedding = MagicMock(return_value=[0.1, 0.2, 0.3])
    vectorstore_module.COLLECTION_MEMORIA = "memoria_resumos"

    replacements = {
        "pymongo": pymongo_module,
        "qdrant_client": qdrant_client_module,
        "app.llms": llms_module,
        "app.config": config_module,
        "app.vectorstore": vectorstore_module,
    }

    with monkeypatch.context() as patcher:
        for name, module in replacements.items():
            patcher.setitem(sys.modules, name, module)
        sys.modules.pop("app.memory", None)
        memory = importlib.import_module("app.memory")
        memory._sessoes_ativas.clear()
        yield SimpleNamespace(
            module=memory,
            collection=collection,
            mongo_client=mongo_client,
            llm=llms_module.llm_rapido,
            qdrant=qdrant,
            vectorstore=vectorstore_module,
        )
        sys.modules.pop("app.memory", None)


def test_agora_retorna_datetime_com_fuso_utc(memory_module):
    agora = memory_module.module._agora()

    assert isinstance(agora, datetime)
    assert agora.tzinfo == timezone.utc


def test_formatar_conversa_junta_papeis_e_conteudos(memory_module):
    mensagens = [
        {"role": "usuario", "content": "Quero descartar óleo."},
        {"role": "assistente", "content": "Procure um ponto de coleta."},
    ]

    assert memory_module.module._formatar_conversa(mensagens) == (
        "usuario: Quero descartar óleo.\n"
        "assistente: Procure um ponto de coleta."
    )


def test_gerar_resumo_chama_llm_e_remove_espacos(memory_module):
    memory_module.llm.invoke.return_value.content = "  Resumo da conversa.  "

    resumo = memory_module.module._gerar_resumo([
        {"role": "usuario", "content": "Olá"}
    ])

    assert resumo == "Resumo da conversa."
    memory_module.llm.invoke.assert_called_once()
    assert "usuario: Olá" in memory_module.llm.invoke.call_args.args[0]


def test_iniciar_sessao_cria_documento_e_indices(memory_module):
    memory_module.collection.find_one.return_value = None

    memory_module.module.iniciar_sessao("sessao-1", "usuario-1")

    memory_module.collection.insert_one.assert_called_once()
    documento = memory_module.collection.insert_one.call_args.args[0]
    assert documento["session_id"] == "sessao-1"
    assert documento["user_id"] == "usuario-1"
    assert documento["resumo"] == ""
    assert documento["mensagens"] == []
    assert isinstance(documento["_id"], str)
    assert memory_module.collection.create_index.call_args_list == [
        call("session_id"), call("user_id"), call("iniciada_em")
    ]


def test_iniciar_sessao_nao_duplica_sessao_ativa(memory_module):
    memory_module.collection.find_one.return_value = None
    memory_module.module._sessoes_ativas["sessao-existente"] = "doc-1"

    memory_module.module.iniciar_sessao("sessao-existente", "usuario-1")

    memory_module.collection.insert_one.assert_not_called()


def test_salvar_mensagem_insere_mensagem_e_atualiza_data(memory_module):
    memory_module.module._sessoes_ativas["sessao-1"] = "doc-1"

    memory_module.module.salvar_mensagem(
        "sessao-1", "usuario", "Como descartar óleo?", "usuario-1"
    )

    memory_module.collection.update_one.assert_called_once()
    filtro, atualizacao = memory_module.collection.update_one.call_args.args
    assert filtro == {"_id": "doc-1"}
    assert atualizacao["$push"]["mensagens"] == {
        "role": "usuario", "content": "Como descartar óleo?"
    }
    assert "atualizada_em" in atualizacao["$set"]


def test_encerrar_sessao_sem_documento_retorna_string_vazia(memory_module):
    memory_module.collection.find_one.return_value = None

    assert memory_module.module.encerrar_sessao("inexistente") == ""


def test_encerrar_sessao_sem_mensagens_limpa_sessao_ativa(memory_module):
    memory_module.module._sessoes_ativas["sessao-1"] = "doc-1"
    memory_module.collection.find_one.return_value = {"_id": "doc-1", "mensagens": []}

    assert memory_module.module.encerrar_sessao("sessao-1") == ""
    assert "sessao-1" not in memory_module.module._sessoes_ativas


def test_encerrar_sessao_gera_resumo_e_salva_no_qdrant(memory_module, monkeypatch):
    inicio = datetime(2026, 1, 1, tzinfo=timezone.utc)
    memory_module.module._sessoes_ativas["sessao-1"] = "doc-1"
    memory_module.collection.find_one.return_value = {
        "_id": "doc-1",
        "user_id": "usuario-1",
        "iniciada_em": inicio,
        "mensagens": [{"role": "usuario", "content": "Descartei óleo."}],
    }
    monkeypatch.setattr(memory_module.module, "_gerar_resumo", lambda mensagens: "Resumo salvo")

    resumo = memory_module.module.encerrar_sessao("sessao-1")

    assert resumo == "Resumo salvo"
    assert memory_module.collection.update_one.call_args.args[1]["$set"]["resumo"] == "Resumo salvo"
    memory_module.vectorstore.gerar_embedding.assert_called_once_with("Resumo salvo")
    memory_module.qdrant.upsert.assert_called_once()
    kwargs = memory_module.qdrant.upsert.call_args.kwargs
    assert kwargs["collection_name"] == "memoria_resumos"
    ponto = kwargs["points"][0]
    assert ponto.id == "doc-1"
    assert ponto.payload["user_id"] == "usuario-1"
    assert ponto.payload["session_id"] == "sessao-1"
    assert ponto.payload["resumo"] == "Resumo salvo"
    assert "sessao-1" not in memory_module.module._sessoes_ativas


def test_recuperar_historico_usa_qdrant_quando_busca_tem_resultados(memory_module):
    memory_module.vectorstore.gerar_embedding.return_value = [0.4, 0.5]
    memory_module.qdrant.query_points.return_value.points = [
        SimpleNamespace(
            id="doc-1",
            payload={"iniciada_em": "2026-01-01", "resumo": "Resumo anterior"},
        )
    ]

    historico = memory_module.module.recuperar_historico("usuario-1", "pontos de coleta", 2)

    assert historico == [{
        "doc_id": "doc-1",
        "iniciada_em": "2026-01-01",
        "resumo": "Resumo anterior",
    }]
    memory_module.vectorstore.gerar_embedding.assert_called_once_with("pontos de coleta")
    memory_module.qdrant.query_points.assert_called_once()
    memory_module.collection.find.assert_not_called()


def test_recuperar_historico_faz_fallback_para_mongodb(memory_module):
    memory_module.qdrant.query_points.return_value.points = []
    memory_module.collection.find.return_value = FakeCursor([
        {"_id": "doc-2", "iniciada_em": "2026-02-01", "resumo": "Resumo do Mongo"}
    ])

    historico = memory_module.module.recuperar_historico("usuario-1", "busca sem resultado", 3)

    assert historico == [{
        "doc_id": "doc-2",
        "iniciada_em": "2026-02-01",
        "resumo": "Resumo do Mongo",
    }]
    memory_module.collection.find.assert_called_once_with(
        {"user_id": "usuario-1", "resumo": {"$nin": ["", None]}},
        {"resumo": 1, "iniciada_em": 1},
    )


def test_recuperar_mensagens_retorna_lista_ou_vazia(memory_module):
    memory_module.collection.find_one.side_effect = [
        {"mensagens": [{"role": "usuario", "content": "Oi"}]},
        None,
    ]

    assert memory_module.module.recuperar_mensagens("doc-1") == [
        {"role": "usuario", "content": "Oi"}
    ]
    assert memory_module.module.recuperar_mensagens("nao-existe") == []
