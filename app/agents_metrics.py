"""Instrumentação dos nós do grafo, preservando execução síncrona e assíncrona."""
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.runnables.base import coerce_to_runnable

from app.observability import medir_etapa


def instrumentar_no(nome: str, acao):
    runnable = coerce_to_runnable(acao)

    def executar(estado, config: RunnableConfig):
        with medir_etapa(nome):
            return runnable.invoke(estado, config=config)

    async def executar_async(estado, config: RunnableConfig):
        with medir_etapa(nome):
            return await runnable.ainvoke(estado, config=config)

    return RunnableLambda(executar, afunc=executar_async, name=nome)
