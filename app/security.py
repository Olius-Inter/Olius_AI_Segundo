"""A Core valida o token, a sessão de login e o perfil vigente."""
import asyncio
import os
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError
from typing import Literal

DEFAULT_CORE_AUTH_URL = "https://tvkgo0evuj.execute-api.us-east-1.amazonaws.com/api/v1/auth/session"

bearer = HTTPBearer(auto_error=False)


class UsuarioAutenticado(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    user_id: UUID
    session_id: UUID
    user_type: Literal["ADMIN", "CITIZENS", "ESTABLISHMENT"]


class SessaoCore(BaseModel):
    """SessionIdentity publicado no OpenAPI da Core; nomes internos independentes."""
    user_id: UUID = Field(validation_alias="userId")
    session_id: UUID = Field(validation_alias="sessionId")
    user_type: Literal["ADMIN", "CITIZENS", "ESTABLISHMENT"] = Field(validation_alias="userType")
    expires_at: AwareDatetime = Field(validation_alias="sessionExpiresAt")


def auth_url() -> str:
    url = os.getenv("CORE_AUTH_URL", DEFAULT_CORE_AUTH_URL)
    partes = urlsplit(url)
    if partes.scheme != "https" or not partes.hostname or partes.username or partes.password or partes.fragment or partes.query:
        raise ValueError("CORE_AUTH_URL deve ser uma URL HTTPS fixa, sem credenciais, query ou fragmento.")
    return url


async def exigir_usuario(
    credenciais: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> UsuarioAutenticado:
    if credenciais is None or credenciais.scheme.lower() != "bearer" or not 1 <= len(credenciais.credentials) <= 8192:
        raise HTTPException(401, "Autenticação necessária.", headers={"WWW-Authenticate": "Bearer"})
    try:
        url = auth_url()
        async with asyncio.timeout(5):
            async with httpx.AsyncClient(timeout=3, follow_redirects=False, trust_env=False) as client:
                async with client.stream("GET", url, headers={"Authorization": f"Bearer {credenciais.credentials}"}) as response:
                    if response.status_code in (401, 403):
                        raise HTTPException(401, "Login inválido ou expirado.")
                    if response.status_code != 200:
                        raise HTTPException(503, "Validação de login indisponível.")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 16384:
                            raise HTTPException(503, "Resposta de autenticação inválida.")
        import json
        dados = json.loads(body)
        sessao = SessaoCore.model_validate(dados)
        if sessao.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(401, "Login inválido ou expirado.")
        return UsuarioAutenticado(
            user_id=sessao.user_id, session_id=sessao.session_id, user_type=sessao.user_type,
        )
    except (ValueError, KeyError, ValidationError, httpx.HTTPError, TimeoutError):
        raise HTTPException(503, "Validação de login indisponível.") from None


async def exigir_admin(usuario: UsuarioAutenticado = Depends(exigir_usuario)) -> UsuarioAutenticado:
    if usuario.user_type != "ADMIN":
        raise HTTPException(403, "Acesso restrito à administração.")
    return usuario
