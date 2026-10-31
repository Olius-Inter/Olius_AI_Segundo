from fastapi import APIRouter
from app.graph import executar_fluxo
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])

@router.post("/api/v1/chat")
def conversar(requisicao: ChatRequest) -> ChatResponse:
    
    resposta = executar_fluxo(
        requisicao.pergunta,
        requisicao.session_id,
        requisicao.user_id
    )

    return ChatResponse(
        resposta=resposta[0],
    )