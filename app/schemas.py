from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """O que o navegador envia no POST /chat."""

    user_id: str = Field(
        default="usuario_teste",
        description="Identifica o usuário de forma estável entre sessões. "
                    "É o que permite a memória de longo prazo Entre usuários funcionar.",
        examples=["usuario_teste"],
    )

    session_id: str = Field(
            ...,
            description="Identifica a conversa.",
            examples=["550e8400-e29b-41d4-a716-446655440000"],
        )

    pergunta: str = Field(
        ...,
        min_length=1,
        description="A mensagem do usuário.",
        examples=["Quais os impactos do vazamento de óleo em canais?"],
    )
    
class ChatResponse(BaseModel):
    """O que a API devolve no POST /chat."""
    resposta: str

class SessionResponse(BaseModel):
    session_id: str
    resumo: str | None = None