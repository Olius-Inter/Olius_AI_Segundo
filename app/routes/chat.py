from fastapi import APIRouter
from app.graph import executar_fluxo
from app.schemas import ChatRequest, ChatResponse
from app.observabilidade import abrir_turno, fechar_turno, status_do_estado, rota_do_estado

router = APIRouter(tags=["chat"])

@router.post("/api/v1/chat")
def conversar(requisicao: ChatRequest) -> ChatResponse:
    
    turno_id = abrir_turno()
    status = "erro"
    rota = ""
    try:
        resposta = executar_fluxo(
            requisicao.pergunta,
            requisicao.session_id,
            requisicao.user_id
        )
        estado = {"agentes_chamados": resposta[1]}
        rota = rota_do_estado(estado)
        status = status_do_estado(estado)
        return ChatResponse(resposta=resposta[0])
    finally:
        fechar_turno(turno_id, session_id=requisicao.session_id, rota=rota, status=status)
