import asyncio
import json
import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from poc.common import ROOT, read_json
from poc.extraction import call_tool
from poc.telemetry import Run


@pytest.mark.integration
def test_real_mcp_search_read_and_invalid_scope():
    if not (ROOT/'data/indexes/adpf54.json').exists():
        pytest.skip('Published judicial index required')

    async def scenario():
        run=Run(kind='mcp-integration')
        params=StdioServerParameters(command=sys.executable,args=['-m','poc.mcp_server'],cwd=str(ROOT),
            env={**os.environ,'POC_CORPUS':'adpf54','POC_RUN_ID':run.run_id,'PYTHONIOENCODING':'utf-8'})
        async with stdio_client(params) as (reader,writer):
            async with ClientSession(reader,writer) as session:
                await session.initialize()
                tools=await session.list_tools()
                assert {tool.name for tool in tools.tools}=={'search_passages','read_passages','list_sections','follow_links'}
                result=await call_tool(session,run,'search_passages',{'query':'relator Marco Aurélio','variant':'A','limit':2},'/test',1)
                assert result['hits']
                ids=[item['id'] for item in result['hits']]
                passages=await call_tool(session,run,'read_passages',{'chunk_ids':ids},'/test',1)
                assert all(c['corpus_id']=='adpf54' for c in passages['chunks'])
                with pytest.raises(RuntimeError):
                    await call_tool(session,run,'read_passages',{'chunk_ids':['dom-casmurro-invalid']},'/test',1)
                with pytest.raises(RuntimeError):
                    await call_tool(session,run,'search_passages',{'query':'test','variant':'invalid'},'/test',1)
        metrics=run.finish()
        assert metrics['mcp_calls']==4
        assert metrics['errors']==2
    asyncio.run(scenario())


@pytest.mark.integration
def test_external_client_entrypoint_records_calls():
    if not (ROOT/'data/indexes/dom-casmurro.json').exists():
        pytest.skip('Published book index required')
    before=set((ROOT/'runs').glob('external-mcp-*'))

    async def scenario():
        params=StdioServerParameters(command=sys.executable,
            args=[str(ROOT/'tools/serve_mcp.py'),'--corpus','dom-casmurro'],cwd=str(ROOT),
            env={**os.environ,'PYTHONIOENCODING':'utf-8'})
        async with stdio_client(params) as (reader,writer):
            async with ClientSession(reader,writer) as session:
                await session.initialize()
                assert len((await session.list_tools()).tools)==4
                sections=await session.call_tool('list_sections',{'offset':0,'limit':1})
                assert not sections.isError
                content=sections.structuredContent or json.loads(sections.content[0].text)
                assert content['total']==38
                assert len(content['sections'])==1
                invalid=await session.call_tool('read_passages',{'chunk_ids':['adpf54-foreign-id']})
                assert invalid.isError
    asyncio.run(scenario())
    created=set((ROOT/'runs').glob('external-mcp-*'))-before
    assert len(created)==1
    directory=created.pop()
    metrics=read_json(directory/'metrics.json')
    assert metrics['mcp_calls']==2
    assert metrics['errors']==1
