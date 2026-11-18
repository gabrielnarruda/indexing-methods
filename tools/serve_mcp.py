"""Stdio entry point for an external MCP client, with server-side call metrics."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP
from poc import mcp_server as implementation
from poc.telemetry import Run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--corpus', choices=['adpf54', 'dom-casmurro'], required=True)
    args = parser.parse_args()
    os.chdir(ROOT)
    run = Run(kind='external-mcp')
    os.environ['POC_CORPUS'] = args.corpus
    os.environ['POC_RUN_ID'] = run.run_id

    class ObservedServer(FastMCP):
        async def call_tool(self, name, arguments):
            with run.span('mcp', name, arguments=arguments, corpus_id=args.corpus) as span:
                return await super().call_tool(name, {**arguments, 'parent_span_id': span['span_id']})

    server = ObservedServer('indexing-methods')
    for function in (implementation.search_passages, implementation.read_passages,
                     implementation.list_sections, implementation.follow_links):
        server.tool()(function)
    print(f'Metrics run: {run.run_id}', file=sys.stderr, flush=True)
    status = 'complete'
    try:
        server.run(transport='stdio')
    except BaseException:
        status = 'interrupted'
        raise
    finally:
        if implementation.retriever is not None:
            implementation.retriever.storage.close()
        run.finish(status=status, corpus_id=args.corpus)


if __name__ == '__main__':
    main()
