import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from poc.common import config, digest, read_json, write_json
from poc.telemetry import Run
from workbench import database as db
from workbench.api import create_app
from workbench.configuration import Recipe, page_selection
from workbench.metrics import measure
from workbench.pipeline import Pipeline
from workbench.service import plan

@pytest.fixture
def database(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DATA',tmp_path/'workbench')
    db.initialize()
    return tmp_path

def job(recipe=None):
    recipe=recipe or Recipe().model_dump()
    saved=db.configuration(recipe)
    return db.enqueue(saved['id'],'adpf54',0,{'recipe':recipe,'input_hash':'same','field_ids':['x'],'form':{},'cases':[]})

def test_saved_recipe_and_queued_request_are_immutable(database):
    first=db.configuration(Recipe().model_dump())
    request={'recipe':first['body'],'input_hash':'same','field_ids':['x']}
    queued=db.enqueue(first['id'],'adpf54',0,request)
    changed={**first['body'],'answer_prompt':first['body']['answer_prompt']+'\nPreserve autoria.'}
    second=db.configuration(changed,first['id'])
    assert second['revision']==2
    assert db.get_config(first['id'])['body']['answer_prompt']!=second['body']['answer_prompt']
    assert db.get_job(queued['id'])['request']['recipe']==first['body']

def test_recipe_rejects_unsupported_and_conflicting_parameters():
    for changes in [{'overlap_characters':1800},{'section_characters':1000},{'graph_enabled':False},{'parser':'pretend'},
                    {'answer_prompt':'No evidence variables'},{'pages':'../secrets'},{'top_k':13}]:
        with pytest.raises(ValidationError):Recipe(**changes)
    assert page_selection('1-3,8',10)==[1,2,3,8]
    with pytest.raises(ValueError):page_selection('1-50',2)

def test_matrix_has_real_cartesian_count_and_reserved_cases(database):
    base=Recipe().model_dump()
    result=plan(base,{'top_k':[4,8],'temperature':[0,.1]},['adpf54','dom-casmurro'],3,split='held_out')
    assert result['configuration_count']==4 and result['run_count']==24
    assert all(row['fields']['adpf54'] and row['fields']['dom-casmurro'] for row in result['configurations'])
    with pytest.raises(ValueError):plan(base,{'top_k':[4,8]*10},['adpf54'],10)
    with pytest.raises(ValueError):plan(base,{},['adpf54'],1,{'adpf54':['nonexistent']})

def test_artifact_reuse_checks_integrity_and_preserves_historical_time(database,monkeypatch):
    import poc.telemetry as telemetry
    monkeypatch.setattr(telemetry,'ROOT',database)
    first=job();run=Run(run_id=first['id'],settings=config())
    pipeline=Pipeline.__new__(Pipeline)
    pipeline.job=first;pipeline.recipe=first['request']['recipe'];pipeline.run=run;pipeline.artifacts={}
    calls=[]
    def produce():calls.append(1);return {'value':'real artifact'}
    output=pipeline.artifact('parse',['source-sha'],{'parser':'v1'},produce)
    key=pipeline.key('parse')
    second=job();pipeline.job=second
    assert pipeline.artifact('parse',['source-sha'],{'parser':'v1'},produce)==output
    assert len(calls)==1
    stage=db.get_job(second['id'])['stages'][0]
    assert stage['status']=='reused' and stage['source_run']==first['id']
    assert stage['duration_ms']>=0 and stage['history_ms']>0
    write_json(db.DATA/'artifacts'/key/'value.json',{'value':'corrupted'})
    assert pipeline.artifact('parse',['source-sha'],{'parser':'v1'},produce)==output
    assert len(calls)==2

def test_cache_keys_depend_on_stage_parameters_not_entire_recipe(database,monkeypatch):
    import poc.telemetry as telemetry
    monkeypatch.setattr(telemetry,'ROOT',database)
    first=job();p=Pipeline.__new__(Pipeline)
    p.job=first;p.recipe=first['request']['recipe'];p.run=Run(run_id=first['id'],settings=config());p.artifacts={}
    calls=[]
    def vector():calls.append(1);return [[1,2,3]]
    p.artifact('embedding',['same-chunks'],{'model':'embedding-v1'},vector)
    key=p.key('embedding')
    p.recipe={**p.recipe,'graph_prompt':p.recipe['graph_prompt']+'\nExtraia datas.'}
    p.artifact('embedding',['same-chunks'],{'model':'embedding-v1'},vector)
    assert p.key('embedding')==key and len(calls)==1
    p.artifact('embedding',['same-chunks'],{'model':'embedding-v2'},vector)
    assert p.key('embedding')!=key and len(calls)==2

def test_metrics_do_not_double_count_mcp_children_or_hide_unknown_cost(database,monkeypatch):
    import workbench.metrics as metrics
    monkeypatch.setattr(metrics,'ROOT',database)
    queued=job();directory=database/'runs'/queued['id'];directory.mkdir(parents=True)
    data=[{'stage':'mcp','duration_ms':150,'status':'ok'},
          {'stage':'retrieval','duration_ms':140,'status':'ok'},
          {'stage':'query_embedding','duration_ms':1,'status':'ok','cache_hit':True,'billable':False},
          {'stage':'query_embedding','duration_ms':50,'status':'ok','billable':True,'api_cost':0,'input_tokens':10},
          {'stage':'generation','duration_ms':200,'status':'ok','billable':True,'api_cost':0,'input_tokens':15,'output_tokens':5}]
    (directory/'events-1.jsonl').write_text('\n'.join(json.dumps(x) for x in data),encoding='utf-8')
    write_json(directory/'run.json',{'wall_seconds':.5})
    db.update_job(queued['id'],status='complete',started_at=queued['created_at'],ended_at=db.now())
    result=measure(db.get_job(queued['id']))
    assert result['model_calls']==2 and result['mcp_calls']==1
    assert result['input_tokens']==25 and result['total_cost'] is None
    assert result['cached_operations']==1
    assert next(s for s in result['stages'] if s['name']=='retrieval')['duration_ms']==150
    assert next(s for s in result['stages'] if s['name']=='verification')['duration_ms'] is None

def test_api_blocks_cross_origin_mutation_and_preserves_cancelled_queue(database):
    with TestClient(create_app(start_coordinator=False)) as client:
        body={'recipe':Recipe().model_dump()}
        assert client.post('/api/configurations',json=body).status_code==403
        assert client.post('/api/configurations',json=body,headers={'X-Workbench':'local','Origin':'https://untrusted.example'}).status_code==403
        response=client.post('/api/configurations',json=body,headers={'X-Workbench':'local'})
        assert response.status_code==200
        queued=job()
        cancelled=client.post('/api/runs/'+queued['id']+'/cancel',json={},headers={'X-Workbench':'local'})
        assert cancelled.json()['status']=='cancelled'
        assert client.get('/api/runs/'+queued['id']).json()['metrics']['wall_seconds'] is None
        repeated=client.post('/api/runs/'+queued['id']+'/retry',json={},headers={'X-Workbench':'local'}).json()
        assert repeated['id']!=queued['id'] and repeated['retry_of']==queued['id']
        assert repeated['request']==queued['request']

def test_restart_recovers_only_verified_dead_worker(database,monkeypatch):
    from workbench.coordinator import Coordinator
    import workbench.coordinator as coordinator
    queued=job()
    db.update_job(queued['id'],status='running',started_at=db.now(),pid=99999,process_created=1)
    monkeypatch.setattr(coordinator,'process_alive',lambda job:True)
    runner=Coordinator();runner.tick()
    assert db.get_job(queued['id'])['status']=='running'
    monkeypatch.setattr(coordinator,'process_alive',lambda job:None)
    runner.tick()
    assert db.get_job(queued['id'])['status']=='running'
    monkeypatch.setattr(coordinator,'process_alive',lambda job:False)
    runner.tick()
    assert db.get_job(queued['id'])['status']=='interrupted'

def test_form_versions_preserve_inputs_and_reject_external_schema(database):
    from workbench.service import datasets, save_dataset
    first=datasets()[0]
    form=json.loads(json.dumps(first['form']))
    form['fields'][0]['question']+=' Responda somente sobre a ação principal.'
    second=save_dataset(first['source']['id'],form,first['cases'])
    assert second['revision']==2
    old=db.dataset_versions(first['source']['id'])[-1]
    assert old['form']['fields'][0]['question']!=form['fields'][0]['question']
    planned=plan(Recipe().model_dump(),{},[first['source']['id']],1,dataset_versions={first['source']['id']:first['id']})
    assert planned['datasets'][first['source']['id']]['form']==first['form']
    form['fields'][0]['value_schema']={'$ref':'http://internal.invalid/schema'}
    with pytest.raises(ValueError,match='inline'):save_dataset(first['source']['id'],form,first['cases'])

def test_partial_failure_and_unknown_time_are_not_success(database,monkeypatch):
    import workbench.metrics as metrics
    monkeypatch.setattr(metrics,'ROOT',database)
    queued=job();db.stage(queued['id'],'relations',status='running')
    db.update_job(queued['id'],status='interrupted',started_at=queued['created_at'],ended_at=db.now())
    value=measure(db.get_job(queued['id']))
    row=next(x for x in value['stages'] if x['name']=='relations')
    assert row['status']=='interrupted' and row['duration_ms'] is None
    assert value['total_cost'] is None
    assert value['wall_seconds'] is None and value['wall_seconds_upper_bound']>=0


def test_live_stage_and_completed_calls_use_distinct_clocks(database,monkeypatch):
    import workbench.metrics as metrics
    monkeypatch.setattr(metrics,'ROOT',database)
    queued=job()
    started=(datetime.now(timezone.utc)-timedelta(seconds=10)).isoformat()
    db.update_job(queued['id'],status='running',started_at=started)
    db.stage(queued['id'],'relations',status='running',started_at=started)
    directory=database/'runs'/queued['id'];directory.mkdir(parents=True)
    (directory/'events-1.jsonl').write_text(json.dumps({'stage':'generation','duration_ms':200,'status':'ok'}),encoding='utf-8')
    measured=measure(db.get_job(queued['id']))
    relation=next(s for s in measured['stages'] if s['name']=='relations')
    generation=next(s for s in measured['stages'] if s['name']=='generation')
    assert relation['duration_ms']>=10000 and relation['duration_is_running']
    assert generation['duration_ms']==200 and generation['duration_is_partial']


def test_process_permission_denied_is_not_a_dead_worker(monkeypatch):
    import psutil
    from workbench.coordinator import process_alive
    def denied(pid):raise psutil.AccessDenied(pid)
    monkeypatch.setattr(psutil,'Process',denied)
    assert process_alive({'pid':123,'process_created':1}) is None


def test_mismatched_embedding_rejected_on_every_query(monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace
    import poc.retrieval as retrieval
    retriever=retrieval.Retriever.__new__(retrieval.Retriever)
    retriever.run=SimpleNamespace(settings={'embedding_model':'new'},span=lambda *a,**k:nullcontext())
    retriever.manifest={'index_name':'versioned','embedding':{'model':'old','digest':'old-digest'}}
    retriever.storage=SimpleNamespace(search=lambda *a,**k:[])
    retriever.models=None
    monkeypatch.setattr(retrieval,'Models',lambda run:SimpleNamespace(digests={'new':'new-digest'}))
    for _ in range(2):
        with pytest.raises(ValueError,match='does not match'):retriever.search('same query')


def test_exports_preserve_stage_units_unknown_cost_and_escape_text(database):
    import csv
    import io
    queued=job(Recipe(name='Receita <script>alert(1)</script>').model_dump())
    db.stage(queued['id'],'parse',status='complete',duration_ms=1250)
    db.update_job(queued['id'],status='complete',started_at=queued['created_at'],ended_at=db.now())
    with TestClient(create_app(start_coordinator=False)) as client:
        route='/api/runs/'+queued['id']+'/export'
        exported=client.get(route).json()
        assert exported['metrics']['total_cost'] is None
        rows=list(csv.DictReader(io.StringIO(client.get(route+'?format=csv').text)))
        assert float(rows[0]['duration_ms'])==1250 and rows[0]['machine_cost_estimate']==''
        page=client.get(route+'?format=html').text
        assert '1,250 s' in page and 'Tempo de cada etapa' in page
        assert '<script>' not in page and '&lt;script&gt;' in page
