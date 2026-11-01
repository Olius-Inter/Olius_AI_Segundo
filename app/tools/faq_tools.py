from langchain.tools import tool
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from app.config import FAQ_PDF_PATH
from app.vectorstore import obter_embeddings

@tool
def faq_retriever(question: str) -> str:
    """Busca no FAQ oficial os trechos mais relevantes para entender a pergunta."""

    # Ler o PDF somente quando o FAQ for consultado, sem bloquear outros agentes.
    docs = PyPDFLoader(FAQ_PDF_PATH).load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=700,chunk_overlap=150)
    chunks = splitter.split_documents(docs)

    embedding = obter_embeddings()

    latent_space = FAISS.from_documents(chunks, embedding)

    results = latent_space.similarity_search(question,k=6)
    return results
