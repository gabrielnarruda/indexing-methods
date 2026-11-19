"""Convert real events to non-overlapping stage metrics; unknown is not zero."""
from datetime import datetime
import json

from poc.common import ROOT, read_json
from . import database as db
from .pipeline import STAGES

def events_for(run_id):
    events=[]
    for file in (ROOT/'runs'/run_id).glob('events-*.jsonl'):
        for line in file.read_text(encoding='utf-8').splitlines():
            try: events.append(json.loads(line))
            except json.JSONDecodeError: pass  # An append in progress; the next poll sees it.
    return events

def elapsed(start,end):
    return (datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds()*1000

def measure(job):
    events=events_for(job['id'])
    groups={'retrieval':{'mcp'},'generation':{'generation'},'verification':{'validation','support_validation'},'evaluation':{'evaluation'}}
    stages={s['name']:dict(s) for s in job['stages']}
    terminal=job['status'] in {'complete','partial','failed','cancelled','interrupted'}
    for name,raw in groups.items():
        items=[e for e in events if e['stage'] in raw]
        row=stages.setdefault(name,{'name':name,'status':'pending','duration_ms':None,'detail':{}})
        if items:
            row['duration_ms']=sum(e['duration_ms'] for e in items)
            row['status']='partial' if any(e['status']=='error' for e in items) else 'complete' if terminal else 'running'
            row['calls']=len(items)
            row['duration_is_partial']=not terminal or job['status']=='interrupted'
            row['started_at']=min((e['started_at'] for e in items if e.get('started_at')),default=row.get('started_at'))
            row['ended_at']=max((e['ended_at'] for e in items if e.get('ended_at')),default=row.get('ended_at')) if terminal else None
        elif terminal and row['status'] in ('pending','running'):
            row['status']='not_executed'
    for name,row in stages.items():
        if not terminal and row['status']=='running' and name not in groups and row.get('started_at'):
            row['duration_ms']=max(0,elapsed(row['started_at'],db.now()))
            row['duration_is_running']=True
        if terminal and row['status']=='running':
            row['status']='interrupted'
            completed_calls=[e for e in events if e['stage']==name]
            if row.get('duration_ms') is None and completed_calls:
                row['duration_ms']=sum(e['duration_ms'] for e in completed_calls)
                row['duration_is_partial']=True
        operations=[e for e in events if (e['stage']==name or name=='verification' and e['stage']=='support_validation' or name=='retrieval' and e['stage']=='query_embedding')]
        usage=[e for e in operations if e.get('billable')]
        row.update(model_calls=len(usage),cached_operations=sum(bool(e.get('cache_hit')) for e in operations),input_tokens=sum(e.get('input_tokens') or 0 for e in usage),
                   output_tokens=sum(e.get('output_tokens') or 0 for e in usage),
                   usage_unknown_calls=sum(e.get('input_tokens') is None for e in usage),
                   api_cost=sum(e.get('api_cost',0) for e in usage))
    directory=ROOT/'runs'/job['id']
    run=read_json(directory/'run.json') if (directory/'run.json').exists() else {}
    wall=run.get('wall_seconds')
    upper_bound=None
    if wall is None and job['status']=='interrupted' and job['started_at']:
        upper_bound=elapsed(job['started_at'],job['ended_at'])/1000
    elif wall is None and job['started_at']:
        wall=elapsed(job['started_at'],job['ended_at'] or db.now())/1000
    queue=elapsed(job['created_at'],job['started_at'] or job['ended_at'] or db.now())
    all_usage=[e for e in events if e.get('billable')]
    recipe=job['request']['recipe']
    rate=recipe['machine_hour_rate']
    api=sum(e.get('api_cost',0) for e in all_usage)
    machine=wall/3600*rate if wall is not None and rate is not None else None
    for row in stages.values():
        row['machine_cost_estimate']=row.get('duration_ms',0)/3600000*rate if rate is not None and row.get('duration_ms') is not None else None
    return {'stages':[dict(stages.get(name,{'name':name,'status':'pending','duration_ms':None}),label=label) for name,label in STAGES],
            'wall_seconds':wall,'wall_seconds_upper_bound':upper_bound,'queue_seconds':queue/1000 if queue is not None else None,
            'total_seconds':wall+queue/1000 if wall is not None and queue is not None else None,
            'model_calls':len(all_usage),'mcp_calls':sum(e['stage']=='mcp' for e in events),
            'cached_operations':sum(bool(e.get('cache_hit')) for e in events),
            'agent_rounds':sum(e['stage']=='round' for e in events),
            'input_tokens':sum(e.get('input_tokens') or 0 for e in all_usage),
            'output_tokens':sum(e.get('output_tokens') or 0 for e in all_usage),
            'usage_unknown_calls':sum(e.get('input_tokens') is None for e in all_usage),
            'api_cost':api,'machine_cost_estimate':machine,'total_cost':api+machine if machine is not None else None,
            'currency':recipe['currency'],'cost_status':'configured_hardware_estimate' if machine is not None else 'hardware_unpriced',
            'timing_note':'Durações por etapa são disjuntas. MCP inclui espera da ferramenta e embedding da consulta; spans internos não são somados novamente. Total medido inclui inicialização e orquestração.'}
