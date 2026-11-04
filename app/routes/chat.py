from fastapi import APIRouter, Depends
from app.security import exigir_usuario, UsuarioAutenticado
from app.resource_limits import operacao
from app.graph import executar_fluxo_async
from app.schemas import ChatRequest, ChatResponse
from app.observability import abrir_turno, fechar_turno, status_do_estado, rota_do_estado

router = APIRouter(tags=["chat"])

@router.post("/api/v1/chat")
async def conversar(requisicao: ChatRequest, usuario: UsuarioAutenticado = Depends(exigir_usuario)) -> ChatResponse:
    
    turno_id = abrir_turno()
    status = "erro"
    rota = ""
    try:
        async with operacao(str(usuario.user_id)):
            resposta = await executar_fluxo_async(
                requisicao.pergunta, str(requisicao.session_id), str(usuario.user_id),
            )
        estado = {"agentes_chamados": resposta[1]}
        rota = rota_do_estado(estado)
        status = status_do_estado(estado)
        return ChatResponse(resposta=resposta[0])
    finally:
        fechar_turno(turno_id, session_id=str(requisicao.session_id), rota=rota, status=status)
