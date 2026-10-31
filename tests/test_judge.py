import json
import urllib.error
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from app import judge

class _RespostaFalsa:
    def __init__(self, dados):
        self._corpo = json.dumps(dados).encode()

    def read(self):
        return self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

def _dados(choice, noul):
    return {"answers": {"veredito": {"choice": choice}, "apoiada": {"noul": noul}}}

@pytest.fixture()
def chave(monkeypatch):
    monkeypatch.setattr(judge, "TYPESAFE_API_KEY", "chave-de-teste")

@pytest.fixture()
def api(monkeypatch, chave):
    """Substitui urlopen e guarda o pedido enviado; configure api['dados']."""
    capturado = {"dados": _dados("apoiada", 0.95)}

    def urlopen_falso(pedido, timeout=None):
        capturado["pedido"] = pedido
        capturado["timeout"] = timeout
        return _RespostaFalsa(capturado["dados"])

    monkeypatch.setattr(judge.urllib.request, "urlopen", urlopen_falso)
    return capturado

def _estado(resposta="Resposta do agente"):
    return {"messages": [
        HumanMessage(content="Quanto descartei?"),
        ToolMessage(content="março=120 L", name="analisar", tool_call_id="1"),
        AIMessage(content=resposta),
    ]}

def test_texto_retorna_string_pura():
    assert judge._texto(AIMessage(content="olá")) == "olá"

def test_texto_junta_partes_de_lista():
    mensagem = AIMessage(content=["a", {"text": "b"}, {"outro": 1}, {"text": None}])
    assert judge._texto(mensagem) == "a\nb"

def test_texto_converte_outros_tipos():
    class Fake:
        content = 42

    assert judge._texto(Fake()) == "42"
    assert judge._texto(object()) == ""

def test_coleta_separa_pergunta_resposta_e_evidencia():
    pergunta, resposta, evidencia = judge._coleta(_estado("Foram 120 L"))
    assert pergunta == "Quanto descartei?"
    assert resposta == "Foram 120 L"
    assert "[analisar]\nmarço=120 L" in evidencia

def test_coleta_inclui_chamadas_de_tool_como_evidencia():
    chamada = AIMessage(
        content="",
        tool_calls=[{"name": "buscar", "args": {"cidade": "São Paulo"}, "id": "1"}],
    )
    estado = {"messages": [HumanMessage(content="oi"), chamada, AIMessage(content="ok")]}

    _, _, evidencia = judge._coleta(estado)

    assert '[chamada buscar]\n{"cidade": "São Paulo"}' in evidencia

def test_coleta_nova_pergunta_descarta_evidencia_anterior():
    estado = {"messages": [
        HumanMessage(content="primeira"),
        ToolMessage(content="dado antigo", name="t", tool_call_id="1"),
        AIMessage(content="r1"),
        HumanMessage(content="segunda"),
        AIMessage(content="r2"),
    ]}

    pergunta, resposta, evidencia = judge._coleta(estado)

    assert pergunta == "segunda"
    assert resposta == "r2"
    assert "dado antigo" not in evidencia

def test_coleta_sem_tools_usa_texto_padrao():
    estado = {"messages": [HumanMessage(content="oi"), AIMessage(content="olá")]}

    _, _, evidencia = judge._coleta(estado)

    assert evidencia == "(nenhuma tool devolveu conteúdo neste turno)"

def test_coleta_trunca_evidencia_nos_ultimos_6000_caracteres():
    estado = {"messages": [
        HumanMessage(content="oi"),
        ToolMessage(content="x" * 7000 + "FIM", name="t", tool_call_id="1"),
        AIMessage(content="r"),
    ]}

    _, _, evidencia = judge._coleta(estado)

    assert len(evidencia) == 6000
    assert evidencia.endswith("FIM")

def test_coleta_usa_nome_padrao_quando_tool_sem_nome():
    class ToolSemNome:
        type = "tool"
        content = "dado"
        name = ""

    estado = {"messages": [ToolSemNome()]}

    _, _, evidencia = judge._coleta(estado)

    assert evidencia.startswith("[tool]\ndado")

def test_publicar_mesma_resposta_nao_reenvia_mensagem(capsys):
    resultado = judge._publicar("  igual ", "apoiada", "igual")

    assert resultado == {"agentes_chamados": ["juiz:apoiada"]}
    assert "[juiz] apoiada" in capsys.readouterr().out

def test_publicar_resposta_diferente_substitui_mensagem():
    resultado = judge._publicar(judge.FRASE_SEGURA, "sem_apoio", "outra")

    assert resultado["messages"] == [
        {"role": "assistant", "content": judge.FRASE_SEGURA}
    ]
    assert resultado["agentes_chamados"] == ["juiz:sem_apoio"]

def test_publicar_aceita_resposta_original_vazia():
    resultado = judge._publicar("texto", "r", None)

    assert resultado["messages"][0]["content"] == "texto"

def test_sem_chave_devolve_frase_segura(monkeypatch):
    monkeypatch.setattr(judge, "TYPESAFE_API_KEY", None)
    resultado = judge._julgar_jev("p", "resposta", "e")
    assert resultado["messages"][0]["content"] == judge.FRASE_SEGURA
    assert resultado["agentes_chamados"] == ["juiz:sem_chave"]

def test_apoiada_acima_do_limiar_mantem_resposta(api):
    api["dados"] = _dados("apoiada", 0.95)
    resultado = judge._julgar_jev("p", "resposta", "e")
    assert "messages" not in resultado
    assert resultado["agentes_chamados"] == ["juiz:apoiada noul=0.95"]

def test_apoiada_exatamente_no_limiar_e_aprovada(api):
    api["dados"] = _dados("apoiada", judge.LIMIAR)
    resultado = judge._julgar_jev("p", "resposta", "e")
    assert "messages" not in resultado

def test_apoiada_abaixo_do_limiar_e_reprovada(api):
    api["dados"] = _dados("apoiada", 0.48)
    resultado = judge._julgar_jev("p", "resposta", "e")
    assert resultado["messages"][0]["content"] == judge.FRASE_SEGURA
    assert resultado["agentes_chamados"] == ["juiz:apoiada:abaixo_do_limiar noul=0.48"]

@pytest.mark.parametrize("veredito", ["parcial", "sem_apoio"])
def test_vereditos_nao_apoiados_sao_reprovados(api, veredito):
    api["dados"] = _dados(veredito, 0.99)
    resultado = judge._julgar_jev("p", "resposta", "e")
    assert resultado["messages"][0]["content"] == judge.FRASE_SEGURA
    assert resultado["agentes_chamados"] == [f"juiz:{veredito} noul=0.99"]

def test_erro_http_devolve_frase_segura_com_codigo(monkeypatch, chave):
    def urlopen_falha(pedido, timeout=None):
        raise urllib.error.HTTPError(judge.JEV_URL, 503, "indisponível", {}, None)

    monkeypatch.setattr(judge.urllib.request, "urlopen", urlopen_falha)

    resultado = judge._julgar_jev("p", "resposta", "e")

    assert resultado["messages"][0]["content"] == judge.FRASE_SEGURA
    assert resultado["agentes_chamados"] == ["juiz:erro http 503"]

def test_pedido_enviado_ao_servico_tem_url_headers_e_corpo(api):
    judge._julgar_jev("Quanto descartei?", "Foram 120 L", "março=120 L")

    pedido = api["pedido"]
    corpo = json.loads(pedido.data.decode())

    assert pedido.full_url == judge.JEV_URL
    assert pedido.get_method() == "POST"
    assert pedido.get_header("Authorization") == "Bearer chave-de-teste"
    assert pedido.get_header("Content-type") == "application/json"
    assert api["timeout"] == 30
    assert corpo["model"] == judge.JEV_MODELO
    assert corpo["state"] == {
        "pergunta": "Quanto descartei?",
        "resposta": "Foram 120 L",
        "evidencia": "março=120 L",
        "regras": judge.REGRAS,
    }
    assert set(corpo["questions"]) == {"veredito", "apoiada"}
    assert set(corpo["questions"]["veredito"]["criteria"]) == {
        "apoiada", "parcial", "sem_apoio",
    }

def test_no_juiz_sem_resposta_nao_chama_servico(monkeypatch):
    def nao_deve_chamar(*args, **kwargs):
        raise AssertionError("não deveria chamar o serviço")

    monkeypatch.setattr(judge, "_julgar_jev", nao_deve_chamar)

    resultado = judge.no_juiz({"messages": [HumanMessage(content="oi")]})

    assert resultado == {"agentes_chamados": ["juiz:sem_resposta"]}

def test_no_juiz_aprova_resposta_fiel(api):
    api["dados"] = _dados("apoiada", 0.9)

    resultado = judge.no_juiz(_estado("Foram 120 L"))

    assert "messages" not in resultado
    assert resultado["agentes_chamados"] == ["juiz:apoiada noul=0.90"]

def test_no_juiz_reprova_resposta_sem_apoio(api):
    api["dados"] = _dados("sem_apoio", 0.1)

    resultado = judge.no_juiz(_estado("Foram 999 L"))

    assert resultado["messages"][0]["content"] == judge.FRASE_SEGURA

def test_no_juiz_trata_erro_de_rede_com_frase_segura(monkeypatch, chave, capsys):
    def urlopen_falha(pedido, timeout=None):
        raise urllib.error.URLError("sem rede")

    monkeypatch.setattr(judge.urllib.request, "urlopen", urlopen_falha)

    resultado = judge.no_juiz(_estado())

    assert resultado["messages"][0]["content"] == judge.FRASE_SEGURA
    assert resultado["agentes_chamados"] == ["juiz:erro"]
    assert "[juiz] erro" in capsys.readouterr().out

def test_no_juiz_trata_resposta_malformada_com_frase_segura(api):
    api["dados"] = {"sem": "answers"}

    resultado = judge.no_juiz(_estado())

    assert resultado["messages"][0]["content"] == judge.FRASE_SEGURA
    assert resultado["agentes_chamados"] == ["juiz:erro"]
