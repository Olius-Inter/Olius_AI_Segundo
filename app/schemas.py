from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from app.limits import MAX_QUESTION

class ChatRequest(BaseModel):
    """O que o navegador envia no POST /chat."""

    model_config = ConfigDict(extra="forbid")
    session_id: UUID

    pergunta: str = Field(
        ...,
        min_length=1,
        max_length=MAX_QUESTION,
        description="A mensagem do usuário.",
        examples=["Quais os impactos do vazamento de óleo em canais?"],
    )
    
class ChatResponse(BaseModel):
    """O que a API devolve no POST /chat."""
    resposta: str

class SessionResponse(BaseModel):
    session_id: str
    resumo: str | None = None