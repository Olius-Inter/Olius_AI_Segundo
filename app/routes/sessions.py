"""Operações de conversa sempre vinculadas ao titular autenticado."""
import asyncio
from uuid import UUID
from fastapi import APIRouter, Depends
from app.security import exigir_usuario, UsuarioAutenticado
from app.resource_limits import operacao
from app.memory import encerrar_sessao, iniciar_sessao
from app.schemas import SessionResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/{session_id}/iniciar", response_model=SessionResponse)
async def iniciar(session_id: UUID, usuario: UsuarioAutenticado = Depends(exigir_usuario)) -> SessionResponse:
    async with operacao(str(usuario.user_id)):
        await asyncio.to_thread(iniciar_sessao, str(session_id), str(usuario.user_id))
    return SessionResponse(session_id=str(session_id), resumo=None)


@router.post("/{session_id}/encerrar", response_model=SessionResponse)
async def encerrar(session_id: UUID, usuario: UsuarioAutenticado = Depends(exigir_usuario)) -> SessionResponse:
    async with operacao(str(usuario.user_id)):
        resumo = await asyncio.to_thread(encerrar_sessao, str(session_id), str(usuario.user_id))
    return SessionResponse(session_id=str(session_id), resumo=resumo or None)
