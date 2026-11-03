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
    pymongo_module.ReturnDocument = SimpleNamespace(AFTER=True)

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


def test_importacao_nao_conecta_ao_mongodb(memory_module):
    memory_module.mongo_client.assert_not_called()
    memory_module.collection.create_index.assert_not_called()


def test_conexao_usa_timeout_e_reutiliza_colecao(memory_module):
    primeira = memory_module.module._obter_colecao_sessoes()
    assert memory_module.module._obter_colecao_sessoes() is primeira
    memory_module.mongo_client.assert_called_once_with(
        "mongodb://test.invalid", serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000, socketTimeoutMS=5000,
    )
    assert memory_module.collection.create_index.call_count == 3


def test_falha_na_conexao_fecha_cliente_e_permite_nova_tentativa(memory_module):
    memory_module.collection.create_index.side_effect = RuntimeError("Falha de rede")
    with pytest.raises(RuntimeError, match="Falha de rede"):
        memory_module.module._obter_colecao_sessoes()
    memory_module.mongo_client.return_value.close.assert_called_once()
    memory_module.collection.create_index.side_effect = None
    assert memory_module.module._obter_colecao_sessoes() is memory_module.collection


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
    memory_module.llm.invoke.return_value.text = "  Resumo da conversa.  "

    resumo = memory_module.module._gerar_resumo([
        {"role": "usuario", "content": "Olá"}
    ])

    assert resumo == "Resumo da conversa."
    memory_module.llm.invoke.assert_called_once()
    assert "usuario: Olá" in memory_module.llm.invoke.call_args.args[0]


def documento(**changes):
    return {"_id": "doc-1", "user_id": "dono", "session_id": "sessao-1",
            "security_version": 2, "estado": "aberta", "turnos": 0,
            "iniciada_em": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "mensagens": [{"role": "human", "content": "Descartei óleo."}], **changes}


def test_proprietario_imutavel_e_indice_unico(memory_module):
    memory_module.collection.find_one_and_update.return_value = documento()
    memory_module.module.iniciar_sessao("sessao-1", "dono")
    query, update = memory_module.collection.find_one_and_update.call_args.args
    assert query == {"session_id": "sessao-1"}
    assert update["$setOnInsert"]["user_id"] == "dono"
    assert "$set" not in update
    memory_module.collection.create_index.assert_any_call("session_id", unique=True, name="session_id_unique_v2")


@pytest.mark.parametrize("operation", ["iniciar_sessao", "recuperar_contexto", "encerrar_sessao"])
def test_outro_usuario_nao_acessa_conversa(memory_module, operation):
    from fastapi import HTTPException
    memory_module.collection.find_one_and_update.return_value = documento()
    memory_module.collection.find_one.return_value = None
    with pytest.raises(HTTPException) as exc:
        getattr(memory_module.module, operation)("sessao-1", "intruso")
    assert exc.value.status_code == 404
    memory_module.llm.invoke.assert_not_called()
    memory_module.qdrant.upsert.assert_not_called()
    if operation != "iniciar_sessao":
        assert memory_module.collection.find_one.call_args.args[0]["user_id"] == "intruso"


@pytest.mark.parametrize("changes", [{"security_version": 1}, {"estado": "encerrada"}])
def test_sessao_antiga_ou_encerrada_nao_reabre(memory_module, changes):
    from fastapi import HTTPException
    memory_module.collection.find_one_and_update.return_value = documento(**changes)
    with pytest.raises(HTTPException) as exc:
        memory_module.module.iniciar_sessao("sessao-1", "dono")
    assert exc.value.status_code == 409


def test_contexto_tem_limite_e_proprietario(memory_module):
    memory_module.collection.find_one.return_value = documento(mensagens=[{"role": "human", "content": str(i)} for i in range(70)])
    result = memory_module.module.recuperar_contexto("sessao-1", "dono")
    assert len(result) == 12
    assert result[-1]["content"] == "69"
    assert memory_module.collection.find_one.call_args.args[0]["user_id"] == "dono"


def test_limite_de_turnos_recusa_sem_modificacao(memory_module):
    from fastapi import HTTPException
    memory_module.collection.update_one.return_value.modified_count = 0
    with pytest.raises(HTTPException) as exc:
        memory_module.module.reservar_turno("sessao-1", "dono")
    assert exc.value.status_code == 409
    assert memory_module.collection.update_one.call_args.args[0]["user_id"] == "dono"


def test_salvar_confere_dono_estado_e_limite(memory_module):
    memory_module.collection.update_one.return_value.modified_count = 1
    memory_module.module.salvar_mensagem("sessao-1", "human", "Mensagem", "dono")
    query, update = memory_module.collection.update_one.call_args.args
    assert query["user_id"] == "dono" and query["estado"] == "aberta"
    assert "$expr" in query
    assert update["$push"]["mensagens"]["content"] == "Mensagem"
    with pytest.raises(ValueError):
        memory_module.module.salvar_mensagem("sessao-1", "human", "x" * 8001, "dono")


def test_encerramento_idempotente_nao_chama_llm(memory_module):
    memory_module.collection.find_one.return_value = documento(estado="encerrada", resumo="Resumo")
    assert memory_module.module.encerrar_sessao("sessao-1", "dono") == "Resumo"
    memory_module.llm.invoke.assert_not_called()


def test_encerramento_sem_mensagens_e_sem_custo(memory_module):
    memory_module.collection.find_one.return_value = documento(mensagens=[])
    memory_module.collection.update_one.return_value.modified_count = 1
    assert memory_module.module.encerrar_sessao("sessao-1", "dono") == ""
    memory_module.llm.invoke.assert_not_called()


def test_encerramento_salva_resumo_com_dono_e_versao(memory_module, monkeypatch):
    memory_module.collection.find_one.return_value = documento()
    memory_module.collection.update_one.return_value.modified_count = 1
    monkeypatch.setattr(memory_module.module, "_gerar_resumo", lambda messages: "Resumo seguro")
    assert memory_module.module.encerrar_sessao("sessao-1", "dono") == "Resumo seguro"
    point = memory_module.qdrant.upsert.call_args.kwargs["points"][0]
    assert point.payload["user_id"] == "dono" and point.payload["security_version"] == 2
    assert memory_module.collection.update_one.call_args.args[0]["user_id"] == "dono"


def test_falha_no_resumo_restabelece_estado_sem_expor_segredo(memory_module, monkeypatch):
    memory_module.collection.find_one.return_value = documento()
    memory_module.collection.update_one.return_value.modified_count = 1
    monkeypatch.setattr(memory_module.module, "_gerar_resumo", MagicMock(side_effect=RuntimeError("Falha")))
    with pytest.raises(RuntimeError):
        memory_module.module.encerrar_sessao("sessao-1", "dono")
    assert memory_module.collection.update_one.call_args.args[1]["$set"]["estado"] == "aberta"


def test_historico_vetorial_filtra_dono_e_versao(memory_module):
    memory_module.qdrant.query_points.return_value.points = [SimpleNamespace(id="d", payload={"resumo": "Seguro", "iniciada_em": "2026-01-01"})]
    result = memory_module.module.recuperar_historico("dono", "descarte")
    assert result[0]["resumo"] == "Seguro"
    filters = memory_module.qdrant.query_points.call_args.kwargs["query_filter"].must
    assert {(f.key, f.match.value) for f in filters} == {("user_id", "dono"), ("security_version", 2)}


def test_historico_mongo_e_mensagens_exigem_dono(memory_module):
    memory_module.collection.find.return_value = FakeCursor([])
    assert memory_module.module.recuperar_historico("dono") == []
    assert memory_module.collection.find.call_args.args[0]["user_id"] == "dono"
    memory_module.collection.find_one.return_value = None
    assert memory_module.module.recuperar_mensagens("doc", "dono") == []
    assert memory_module.collection.find_one.call_args.args[0] == {"_id": "doc", "user_id": "dono", "security_version": 2}
