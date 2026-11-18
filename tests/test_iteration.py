import asyncio

from poc.extraction import extract_field
from poc.telemetry import Run
from poc.common import config


def test_repeated_query_stops_and_preserves_pending_field(tmp_path,monkeypatch):
    import poc.telemetry as telemetry
    import poc.extraction as extraction
    monkeypatch.setattr(telemetry,'ROOT',tmp_path)
    calls=[]

    async def fake_call(session,run,name,arguments,field,round_index):
        calls.append(name)
        return {'hits':[]} if name=='search_passages' else {'chunks':[]}

    class Model:
        def generate(self,*args,**kwargs):
            return {'status':'search_again','value':None,'evidence':[],'reason':'Missing','next_query':'same query'}

    monkeypatch.setattr(extraction,'call_tool',fake_call)
    run=Run(settings=config())
    field={'id':'test','path':'/x','question':'same query','value_schema':{'type':'string'}}
    result=asyncio.run(extract_field(None,run,Model(),field,'F',0))
    assert len(result['rounds'])==1
    assert result['status']=='limit_reached'
    assert result['value'] is None
    assert calls==['search_passages','read_passages']


def test_distinct_queries_respect_round_budget(tmp_path,monkeypatch):
    import poc.telemetry as telemetry
    import poc.extraction as extraction
    monkeypatch.setattr(telemetry,'ROOT',tmp_path)

    async def fake_call(session,run,name,arguments,field,round_index):
        return {'hits':[]} if name=='search_passages' else {'chunks':[]}

    class Model:
        counter=0
        def generate(self,*args,**kwargs):
            self.counter+=1
            return {'status':'search_again','value':None,'evidence':[],'reason':'Missing','next_query':f'query {self.counter}'}

    monkeypatch.setattr(extraction,'call_tool',fake_call)
    run=Run(settings={**config(),'max_rounds_per_field':3})
    field={'id':'test','path':'/x','question':'query 0','value_schema':{'type':'string'}}
    result=asyncio.run(extract_field(None,run,Model(),field,'F',0))
    assert len(result['rounds'])==3
    assert result['status']=='limit_reached'
