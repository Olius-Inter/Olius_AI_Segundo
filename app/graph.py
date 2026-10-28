import operator
from typing import Annotated
from cohere import ChatResponse
from langgraph.graph import StateGraph, MessagesState, END
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import RemoveMessage
from app.guardrail import guardrail_entrada, guardrail_saida, anonimizar_entrada
from app.memory import iniciar_sessao, salvar_mensagem, encerrar_sessao
from app.agents import AGENTS

faq_app = AGENTS["faq"]
oil_advisor_app = AGENTS["oil_advisor"]
business_analyst_app = AGENTS["business_analyst"]
routes_maps_app = AGENTS["routes_maps"]
ranking_sustainable_app = AGENTS["ranking_sustainable"]
router_app = AGENTS["router"]
orchestrator_app = AGENTS["orchestrator"]

class Estado(MessagesState):
    agentes_chamados: Annotated[list[str], operator.add]
    rota: str
    mapa_pii: dict
    session_id: str
    user_id: str

def no_guardrail_entrada(estado: Estado) -> dict:

    human_message = list(estado["messages"])[-1]

    texto_anonimizado, mapa = anonimizar_entrada(human_message.text)

    resultado = guardrail_entrada(texto_anonimizado)

    salvar_mensagem(
        session_id=estado["session_id"],
        user_id=estado["user_id"],
        role="human",
        content=texto_anonimizado
    )

    if resultado["bloqueado"]:

        salvar_mensagem(
        session_id=estado["session_id"],
        user_id=estado["user_id"],
        role="assistant",
        content=resultado["mensagem"]
    )

        return {
            "messages": [{"role": "assistant", "content": resultado["mensagem"]}],
            "rota": "fim",
            "mapa_pii": {},
            "agentes_chamados": [f"guardrail_entrada:{resultado['motivo']}"],
        }

    return {
        "messages": [
            RemoveMessage(id=human_message.id),
            {"role": "human", "content": texto_anonimizado},
        ],
        "mapa_pii": mapa,
        "agentes_chamados": ["guardrail_entrada:aprovado"],
        "rota": "router",
    }

def router_node(estado: Estado, config: RunnableConfig) -> dict:
    saida = router_app.invoke({"messages": list(estado["messages"])})
    texto = saida["messages"][-1].text

    if "ROUTE=" not in texto:

        salvar_mensagem(
            session_id=estado["session_id"],
            user_id=estado["user_id"],
            role="assistant",
            content=texto
        )

        return {
            "agentes_chamados": ["router"],
            "rota": "fim",
            "messages": [{"role": "assistant", "content": texto}],
        }

    rota = "fim"
    for linha in texto.splitlines():
        if linha.startswith("ROUTE="):
            rota = linha.split("=", 1)[1].strip()
            break

    return {
        "agentes_chamados": ["router", rota],
        "rota": rota,
    }

def orchestrator_node(estado: Estado) -> dict:
    ultima_especialista = ""
    for mensagem in reversed(estado["messages"]):
        if mensagem.type == "ai" and mensagem.content:
            ultima_especialista = mensagem.content
            break
    
    saida = orchestrator_app.invoke({
        "messages": {"role": "human", "content": ultima_especialista}
    })

    return {
        "agentes_chamados": ["orchestrator"],
        "messages": [{"role": "assistant", "content": saida["messages"][-1].text}]
    }

def no_guardrail_saida(estado: Estado) -> dict:

    ultima_resposta = list(estado["messages"])[-1]

    resultado = guardrail_saida(ultima_resposta.text, estado.get("mapa_pii", {}))

    salvar_mensagem(
        session_id=estado["session_id"],
        user_id=estado["user_id"], 
        role="assistant",
        content=resultado["conteudo"]
    )

    return {
        "messages": [RemoveMessage(id=ultima_resposta.id), {"role": "assistant", "content": resultado["conteudo"]}],
        "agentes_chamados": ["guardrail_saida"],
    }


def decidir_especialista(estado: Estado) -> str:
    return estado["rota"] if estado["rota"] in ("oil_advisor", "maps", "sustainability_agent", "business_analyst", "faq") else "fim"

def decidir_pos_guardrail_entrada(estado: Estado) -> str:
    return estado["rota"]

grafo = StateGraph(Estado)

grafo.add_node("guardrail_entrada", no_guardrail_entrada)
grafo.add_node("router", router_node)
grafo.add_node("oil_advisor", oil_advisor_app)
grafo.add_node("routes_maps", routes_maps_app)
grafo.add_node("ranking_sustainable", ranking_sustainable_app)
grafo.add_node("business_analyst", business_analyst_app)
grafo.add_node("faq", faq_app)
grafo.add_node("orchestrator", orchestrator_node)
grafo.add_node("guardrail_saida", no_guardrail_saida)

grafo.set_entry_point("guardrail_entrada")

grafo.add_conditional_edges(
    "router",
    decidir_especialista,
    {
        "oil_advisor": "oil_advisor",
        "routes_maps": "routes_maps",
        "ranking_sustainable": "ranking_sustainable",
        "business_analyst": "business_analyst",
        "faq": "faq",
        "fim": END,
    },
)

grafo.add_conditional_edges(
    "guardrail_entrada",
    decidir_pos_guardrail_entrada,
    {"router": "router", "fim": END},
)

grafo.add_edge("oil_advisor", "orchestrator")
grafo.add_edge("maps", "orchestrator")
grafo.add_edge("sustainability_agent", "orchestrator")
grafo.add_edge("business_analyst", "orchestrator")
grafo.add_edge("orchestrator", "guardrail_saida")
grafo.add_edge("guardrail_saida", END)
grafo.add_edge("faq", END)

memory = MemorySaver()
fluxo_agentes = grafo.compile(checkpointer=memory)

def executar_fluxo(pergunta_usuario: str, session_id_user: str, user_id: str) -> list:
    iniciar_sessao(session_id=session_id_user, user_id=user_id)

    estado_inicial = {
        "messages": [{"role": "human", "content": pergunta_usuario}],
        "agentes_chamados": [],
        "rota": "",
        "mapa_pii": {},
        "session_id": session_id_user,
        "user_id": user_id
    }

    estado_final = fluxo_agentes.invoke(
        estado_inicial,
        config={"configurable": {"thread_id": session_id_user, "user_id": user_id}},
    ) 
    
    return [
        estado_final["messages"][-1].text,
        estado_final["agentes_chamados"],
        estado_final["rota"]
    ]