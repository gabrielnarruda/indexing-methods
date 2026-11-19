"""Loopback-only HTTP API and built frontend. No external-account dependency."""
from contextlib import asynccontextmanager
import csv
import io
import json
import os
from urllib.parse import urlparse

import httpx
import pymupdf
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from jsonschema import ValidationError as SchemaValidationError, SchemaError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from poc.common import ROOT, config, read_json
from . import database as db, service
from .configuration import Recipe
from .coordinator import Coordinator
from .reporting import report

class ConfigRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    recipe: Recipe
    parent_id: str | None = None

class ExperimentRequest(ConfigRequest):
    axes: dict[str,list] = Field(default_factory=dict)
    documents: list[str]
    repetitions: int = Field(default=1,ge=1,le=10)
    field_ids: dict[str,list[str]] | None = None
    mode: str = 'end_to_end'
    split: str = 'development'
    dataset_versions: dict[str,str] = Field(default_factory=dict)

class DatasetRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    form: dict
    cases: list[dict]

def create_app(start_coordinator=True):
    coordinator=Coordinator()
    @asynccontextmanager
    async def lifespan(app):
        db.initialize()
        if not db.configs():db.configuration(Recipe().model_dump())
        service.datasets()
        if start_coordinator:coordinator.start()
        yield
        if start_coordinator:coordinator.stop()
    app=FastAPI(title='Indexing Methods local workbench',lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','testserver'])

    @app.middleware('http')
    async def local_requests(request:Request,call_next):
        origin=request.headers.get('origin')
        expected=f'{request.url.scheme}://{request.url.netloc}'
        if origin and origin!=expected:
            return JSONResponse({'detail':'Origem externa não permitida.'},status_code=403)
        if request.method not in ('GET','HEAD','OPTIONS'):
            if request.headers.get('x-workbench')!='local' or not request.headers.get('content-type','').startswith('application/json'):
                return JSONResponse({'detail':'Use a interface local ou JSON com X-Workbench: local.'},status_code=403)
            if int(request.headers.get('content-length','0'))>2000000:
                return JSONResponse({'detail':'Pedido muito grande.'},status_code=413)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Cache-Control']='no-store'
        return response

    @app.exception_handler(KeyError)
    async def missing(request,exc):return JSONResponse({'detail':str(exc)},status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request,exc):return JSONResponse({'detail':str(exc)},status_code=422)

    @app.exception_handler(SchemaValidationError)
    @app.exception_handler(SchemaError)
    async def invalid_schema(request,exc):return JSONResponse({'detail':str(exc)[:1500]},status_code=422)

    @app.exception_handler(httpx.HTTPError)
    async def provider_error(request,exc):return JSONResponse({'detail':f'Serviço local indisponível: {type(exc).__name__}. Confira Docker e modelos.'},status_code=503)

    @app.get('/api/bootstrap')
    def bootstrap():
        try:models=service.model_catalog();model_error=None
        except Exception as exc:models=[];model_error=f'Ollama indisponível: {type(exc).__name__}'
        return {'configurations':db.configs(),'defaults':Recipe().model_dump(),'datasets':service.datasets(),
                'models':models,'model_error':model_error,'stages':dict(__import__('workbench.pipeline',fromlist=['STAGES']).STAGES),
                'prototype':False,'provider':'Ollama local','external_apis':'Not configured; no paid provider calls'}

    @app.get('/api/health')
    def health():
        settings=config();result={}
        for key,url in [('opensearch',settings['opensearch_url']+'/_cluster/health'),('ollama',settings['ollama_url']+'/api/tags')]:
            try:
                response=httpx.get(url,timeout=2);response.raise_for_status();result[key]={'ok':True}
            except Exception as exc:result[key]={'ok':False,'error':type(exc).__name__}
        from neo4j import GraphDatabase
        try:
            with GraphDatabase.driver(settings['neo4j_url'],auth=None,connection_timeout=2) as driver:driver.verify_connectivity()
            result['neo4j']={'ok':True}
        except Exception as exc:result['neo4j']={'ok':False,'error':type(exc).__name__}
        return result

    @app.post('/api/configurations')
    def save_configuration(body:ConfigRequest):return db.configuration(body.recipe.model_dump(),body.parent_id)

    @app.post('/api/experiments/preview')
    def preview(body:ExperimentRequest):
        return service.plan(body.recipe.model_dump(),body.axes,body.documents,body.repetitions,body.field_ids,body.mode,body.split,body.dataset_versions)

    @app.post('/api/experiments')
    def launch(body:ExperimentRequest):return service.launch(preview(body),body.parent_id)

    @app.get('/api/runs')
    def runs():return service.jobs()

    @app.get('/api/runs/{job_id}')
    def detail(job_id:str):return service.detail(job_id,True)

    @app.post('/api/runs/{job_id}/cancel')
    def cancel(job_id:str):
        job=db.get_job(job_id)
        if job['status']=='queued':db.update_job(job_id,cancel_requested=1,status='cancelled',ended_at=db.now())
        elif job['status'] in ('starting','running'):db.update_job(job_id,cancel_requested=1)
        else:raise ValueError('Esta run já terminou.')
        return db.get_job(job_id)

    @app.post('/api/runs/{job_id}/retry')
    def retry(job_id:str):
        job=db.get_job(job_id)
        if job['status'] in ('queued','starting','running'):raise ValueError('A run ainda está em execução.')
        return db.enqueue(job['config_id'],job['corpus_id'],job['repetition'],job['request'],retry_of=job_id)

    @app.get('/api/compare')
    def compare(reference:str,candidate:str):return service.comparison(reference,candidate)

    @app.get('/api/runs/{job_id}/export')
    def export(job_id:str,format:str='json'):
        data=service.detail(job_id,True)
        filename=job_id+'.'+format
        if format=='json':content=json.dumps(data,ensure_ascii=False,indent=2);mime='application/json'
        elif format=='csv':
            stream=io.StringIO();writer=csv.writer(stream)
            writer.writerow(['stage','status','duration_ms','partial','historical_ms','api_cost','machine_cost_estimate','currency','model_calls','cached_operations','input_tokens','output_tokens'])
            for row in data['metrics']['stages']:
                writer.writerow([row['label'],row['status'],row.get('duration_ms'),bool(row.get('duration_is_partial') or row.get('duration_is_running')),row.get('history_ms'),row.get('api_cost'),row.get('machine_cost_estimate'),data['metrics']['currency'],row.get('model_calls'),row.get('cached_operations'),row.get('input_tokens'),row.get('output_tokens')])
            content=stream.getvalue();mime='text/csv; charset=utf-8'
        elif format=='html':
            content=report(data);mime='text/html'
        else:raise ValueError('Formato: json, csv ou html.')
        return Response(content,media_type=mime,headers={'Content-Disposition':f'attachment; filename="{filename}"'})

    def source(doc_id):
        try:return next(s for s in service.corpus() if s['id']==doc_id)
        except StopIteration:raise KeyError('Documento não encontrado')

    @app.get('/api/documents/{doc_id}/pdf')
    def pdf(doc_id:str):return FileResponse(ROOT/'data/raw'/source(doc_id)['filename'],media_type='application/pdf')

    @app.post('/api/documents/{doc_id}/dataset')
    def save_dataset(doc_id:str,body:DatasetRequest):return service.save_dataset(doc_id,body.form,body.cases)

    @app.get('/api/documents/{doc_id}/datasets')
    def versions(doc_id:str):
        source(doc_id)
        return db.dataset_versions(doc_id)

    @app.get('/api/documents/{doc_id}/pages/{number}')
    def page(doc_id:str,number:int):
        with pymupdf.open(ROOT/'data/raw'/source(doc_id)['filename']) as pdf:
            if not 1<=number<=len(pdf):raise ValueError('Página fora do documento.')
            page=pdf[number-1]
            return {'page':number,'pages':len(pdf),'text':page.get_text(sort=True),'blocks':page.get_text('blocks',sort=True)}

    @app.get('/api/runs/{job_id}/graph')
    def graph(job_id:str,offset:int=0,limit:int=100):
        job=db.get_job(job_id)
        index=(job['result'] or {}).get('index')
        if not index:return {'facts':[],'total':0,'note':'Esta run ainda não publicou um grafo.'}
        if offset<0 or not 1<=limit<=500:raise ValueError('Paginação inválida.')
        relations=read_json(ROOT/index['directory']/'relations.json')
        facts=[f for s in relations for f in s['facts']]
        document=read_json(ROOT/index['directory']/'document.json')
        pages={c['id']:c['page'] for c in document['chunks']}
        return {'facts':[{**f,'page':pages[f['chunk_id']]} for f in facts[offset:offset+limit]],
                'total':len(facts),'rejected':sum(s['rejected'] for s in relations),'version':index['graph_name'],'offset':offset}

    @app.get('/api/runs/{job_id}/passages/{chunk_id}')
    def passage(job_id:str,chunk_id:str):
        job=db.get_job(job_id);index=(job['result'] or {}).get('index')
        if not index:
            path=ROOT/'runs'/job_id/'index.json'
            if not path.exists():raise KeyError('Índice ainda não publicado')
            index=read_json(path)
        document=read_json(ROOT/index['directory']/'document.json')
        try:return next(c for c in document['chunks'] if c['id']==chunk_id)
        except StopIteration:raise KeyError('Trecho fora desta versão')

    @app.get('/history/{filename}')
    def history(filename:str):
        if filename not in ('relatorio.html','grafo.html'):raise KeyError('Relatório não encontrado')
        return FileResponse(ROOT/'reports/full'/filename,media_type='text/html')

    dist=ROOT/'frontend/dist'
    if dist.exists():app.mount('/',StaticFiles(directory=dist,html=True),name='interface')
    else:
        @app.get('/')
        def no_build():return HTMLResponse('<h1>Indexing Methods</h1><p>Compile a interface: cd frontend &amp;&amp; npm ci &amp;&amp; npm run build.</p>',status_code=503)
    return app

app=create_app()
