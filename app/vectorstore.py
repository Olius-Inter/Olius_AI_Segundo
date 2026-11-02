"""
Cliente Qdrant e função de embedding — centralizados aqui.

Dois consumidores:
  - memory.py → salva/busca resumos no Qdrant.
  - tools/faq_tools.py → indexa o PDF em FAISS sob demanda.

Ambos usam text-embedding-3-small com 768 dimensões e a chave CHATGPT_API_KEY.
"""

from functools import lru_cache
from qdrant_client import QdrantClient, models
from langchain_openai import OpenAIEmbeddings
from app.config import QDRANT_URL, QDRANT_API_KEY, CHATGPT_API_KEY

qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Não mistura espaços vetoriais diferentes nem altera o índice antigo.
COLLECTION_MEMORIA = "memoria_resumos_openai_768"
EMBEDDING_DIM = 768

@lru_cache(maxsize=1)
def obter_embeddings() -> OpenAIEmbeddings:
    """Cria o cliente sob demanda, após a validação de configuração da API."""
    if not CHATGPT_API_KEY:
        raise RuntimeError("Variável ausente no .env: CHATGPT_API_KEY")
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=CHATGPT_API_KEY,
        dimensions=EMBEDDING_DIM,
    )


@lru_cache(maxsize=1)
def _garantir_colecao_memoria() -> None:
    if not qdrant.collection_exists(COLLECTION_MEMORIA):
        qdrant.create_collection(
            collection_name=COLLECTION_MEMORIA,
            vectors_config=models.VectorParams(size=EMBEDDING_DIM, distance=models.Distance.COSINE),
        )


def gerar_embedding(texto: str) -> list[float]:
    """Gera um vetor de 768 dimensões para o texto informado."""
    vetor = obter_embeddings().embed_query(texto)
    _garantir_colecao_memoria()
    return vetor


def gerar_embeddings_batch(textos: list[str]) -> list[list[float]]:
    """Gera embeddings para uma lista de textos de uma vez (mais eficiente)."""
    return obter_embeddings().embed_documents(textos)
