import json
import urllib.error
import urllib.request
from langchain_core.messages import RemoveMessage
from app.config import TYPESAFE_API_KEY

JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODELO = "jev-latest"
LIMIAR = 0.70
FRASE_SEGURA = "Não tenho evidências para afirmar isso."

REGRAS = (
    "A pergunta do usuário também é evidência do que ele disse que fez. "
    "Somas, contagens, datas convertidas para o horário de Brasília e "
    "reformatação de valores tirados da evidência contam como apoiada. "
    "Esclarecimento, saudação, oferta de ajuda, sugestão de próximo passo "
    "e ausência de registro contam como apoiada. "
    "Opinião do usuário pode ser citada como fala dele. "
    "[business_analyst] Tool: março=120 L, abril=150 L. Resposta: Seu descarte subiu 25% de março para abril. -> apoiada (150/120 = 1,25)."
    "[business_analyst] Tool: março=120 L, abril=150 L. Resposta: Você descartou 300L no trimestre. -> sem_apoio (300 L não está na evidência)."
    "[ranking_sustainable] Tool: ranking=null. Resposta: Você está em último lugar. -> sem_apoio (null é ausência de participação, não posição)."
    "[routes_maps] Tool: PEV Centro, 1,2 km, 14 min a pé. Resposta: O PEV Centro fica a 14 minutos a pé. -> apoiada."
    "[routes_maps] Tool: PEV Centro, sem horário. Resposta: Ele abre às 8h. -> sem_apoio."
    "[faq] FAQ não cita prazo. Resposta: O ponto é creditado em 24 horas. -> sem_apoio."
)

def _texto(mensagem) -> str:
    conteudo = getattr(mensagem, "content", "")
    if isinstance(conteudo, str):
        return conteudo
    if isinstance(conteudo, list):
        pedacos = []
        for parte in conteudo:
            if isinstance(parte, str):
                pedacos.append(parte)
            elif isinstance(parte, dict):
                pedacos.append(str(parte.get("text") or ""))
        return "\n".join(p for p in pedacos if p)
    return str(conteudo or "")

def _coleta(estado):
    """Devolve pergunta, resposta, evidência e o id da mensagem da resposta.

    A evidência vem só do que o usuário disse e do que as tools devolveram;
    os argumentos das tool calls são escritos pelo agente e não contam.
    """
    pergunta = ""
    resposta = ""
    id_resposta = None
    evidencias = []
    for mensagem in estado["messages"]:
        tipo = getattr(mensagem, "type", "")
        texto = _texto(mensagem).strip()
        if tipo == "human" and texto:
            pergunta = texto
            resposta = ""
            id_resposta = None
            evidencias = []
        elif tipo == "tool" and texto:
            nome = getattr(mensagem, "name", "") or "tool"
            evidencias.append(f"[{nome}]\n{texto}")
        elif tipo == "ai" and texto:
            resposta = texto
            id_resposta = getattr(mensagem, "id", None)
    evidencia = "\n\n".join(evidencias).strip()
    if not evidencia:
        evidencia = "(nenhuma tool devolveu conteúdo neste turno)"
    return pergunta, resposta, evidencia[-6000:], id_resposta

def _publicar(texto, rotulo, resposta_original, id_resposta=None):
    print(f"[juiz] {rotulo}")
    if texto.strip() == (resposta_original or "").strip():
        return {"agentes_chamados": [f"juiz:{rotulo}"]}
    mensagens = [RemoveMessage(id=id_resposta)] if id_resposta else []
    mensagens.append({"role": "assistant", "content": texto.strip()})
    return {
        "messages": mensagens,
        "agentes_chamados": [f"juiz:{rotulo}"],
    }

def _julgar_jev(pergunta, resposta, evidencia, id_resposta=None):
    if not TYPESAFE_API_KEY:
        return _publicar(FRASE_SEGURA, "sem_chave", resposta, id_resposta)
    corpo = json.dumps({
        "model": JEV_MODELO,
        "state": {
            "pergunta": pergunta,
            "resposta": resposta,
            "evidencia": evidencia,
            "regras": REGRAS,
        },
        "questions": {
            "veredito": {
                "type": "choice",
                "instructions": "Seguindo as regras, a resposta só afirma o que a evidência sustenta?",
                "criteria": {
                    "apoiada": "toda afirmação factual aparece na evidência",
                    "parcial": "parte aparece e parte não",
                    "sem_apoio": "há fato, número, regra ou opinião sem evidência",
                },
            },
            "apoiada": {
                "type": "noul",
                "instructions": (
                    "Seguindo as regras, a resposta é fiel à evidência: todo valor, registro, local, "
                    "data e fato dela sai da evidência, da fala do usuário ou de contas sobre elas?"
                ),
            },
        },
    }).encode()
    pedido = urllib.request.Request(
        JEV_URL,
        data=corpo,
        headers={
            "Authorization": f"Bearer {TYPESAFE_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(pedido, timeout=10) as resp:
            dados = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return _publicar(FRASE_SEGURA, f"erro http {exc.code}", resposta, id_resposta)
    respostas = dados["answers"]
    choice = respostas["veredito"]["choice"]
    noul = float(respostas["apoiada"]["noul"])
    if choice == "apoiada" and noul >= LIMIAR:
        return _publicar(resposta, f"apoiada noul={noul:.2f}", resposta, id_resposta)
    rotulo = "apoiada:abaixo_do_limiar" if choice == "apoiada" else choice
    return _publicar(FRASE_SEGURA, f"{rotulo} noul={noul:.2f}", resposta, id_resposta)

def no_juiz(estado: dict) -> dict:
    pergunta, resposta, evidencia, id_resposta = _coleta(estado)
    if not resposta:
        return {"agentes_chamados": ["juiz:sem_resposta"]}
    try:
        return _julgar_jev(pergunta, resposta, evidencia, id_resposta)
    except Exception as exc:
        print(f"[juiz] erro {exc}")
        return _publicar(FRASE_SEGURA, "erro", resposta, id_resposta)