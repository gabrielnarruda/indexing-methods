import os

from mcp.server.fastmcp import FastMCP

from .retrieval import Retriever
from .telemetry import Run, PARENT

server=FastMCP('indexing-methods')
retriever=None


def get_retriever():
    global retriever
    if retriever is None:
        retriever=Retriever(os.environ['POC_CORPUS'],Run(run_id=os.environ['POC_RUN_ID']))
    return retriever


@server.tool()
def search_passages(query:str,variant:str='B',limit:int=4,parent_span_id:str='')->dict:
    """Busca passagens dentro do corpus selecionado. Retorna IDs para leitura."""
    token=PARENT.set(parent_span_id or None)
    try:
        return get_retriever().search(query,variant,limit)
    finally:
        PARENT.reset(token)


@server.tool()
def read_passages(chunk_ids:list[str],parent_span_id:str='')->dict:
    """Abre o texto original e a localização dos trechos do corpus selecionado."""
    return get_retriever().read(chunk_ids)


@server.tool()
def list_sections(offset:int=0,limit:int=20,parent_span_id:str='')->dict:
    """Lista grupos contíguos de trechos e permite percorrer o documento."""
    return get_retriever().sections(offset,limit)


@server.tool()
def follow_links(chunk_ids:list[str],query:str='',parent_span_id:str='')->dict:
    """Segue entidades compartilhadas no grafo e devolve trechos relacionados."""
    return get_retriever().follow(chunk_ids,query)


if __name__=='__main__':
    server.run(transport='stdio')
