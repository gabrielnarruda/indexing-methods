import asyncio
import json
import os
import sys
from datetime import timedelta

from jsonschema import Draft202012Validator, ValidationError, validate
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .common import ROOT, read_json, write_json
from .indexing import normalize
from .models import Models
from .telemetry import Run

SUPPORT_SCHEMA={'type':'object','properties':{'reason':{'type':'string','maxLength':400},'supported':{'type':'boolean'}},
                'required':['supported','reason'],'additionalProperties':False}


def answer_schema(value_schema):
    return {'type':'object','properties':{
        'status':{'type':'string','enum':['filled','not_found','conflicting','search_again']},
        'value':{'anyOf':[value_schema,{'type':'null'}]},
        'evidence':{'type':'array','maxItems':5,'items':{'type':'object','properties':{
            'chunk_id':{'type':'string'},'quote':{'type':'string'}},
            'required':['chunk_id','quote'],'additionalProperties':False}},
        'reason':{'type':'string'},'next_query':{'type':'string'}},
        'required':['status','value','evidence','reason','next_query'],'additionalProperties':False}


def verify_answer(answer, chunks, value_schema):
    errors=[]
    lookup={chunk['id']:chunk for chunk in chunks}
    for citation in answer.get('evidence',[]):
        chunk=lookup.get(citation.get('chunk_id'))
        quote=normalize(citation.get('quote',''))
        if chunk is None or len(quote)<10 or quote not in normalize(chunk['text']):
            errors.append('Citation does not match a supplied passage')
    if answer.get('status')=='filled':
        if not answer.get('evidence'):
            errors.append('Filled value requires evidence')
        errors.extend(error.message for error in Draft202012Validator(value_schema).iter_errors(answer.get('value')))
    elif answer.get('value') is not None:
        errors.append('Unresolved field must have a null value')
    return errors


def set_path(result,path,value):
    keys=path.strip('/').split('/')
    target=result
    for key in keys[:-1]:
        target=target.setdefault(key,{})
    target[keys[-1]]=value


async def call_tool(session,run,name,arguments,field,round_index):
    with run.span('mcp',name,field_path=field,round_index=round_index,arguments=arguments) as span:
        result=await session.call_tool(name,{**arguments,'parent_span_id':span['span_id']},read_timeout_seconds=timedelta(seconds=run.settings['request_timeout_seconds']+30))
        if result.isError:
            raise RuntimeError(str(result.content))
        content=result.structuredContent
        if content is None:
            content=json.loads(next(item.text for item in result.content if item.type=='text'))
        span['result_size_characters']=len(json.dumps(content))
        return content


async def extract_form(corpus_id,variant='F',repetition=0,field_ids=None,*,run=None,index_manifest=None,form=None,finish_run=True):
    run=run or Run(kind='extraction')
    try:
        with run.span('initialization','form_models_and_index',corpus_id=corpus_id):
            form=form or read_json(ROOT/'forms'/f'{corpus_id}.json')
            if field_ids is not None:
                unknown=set(field_ids)-{field['id'] for field in form['fields']}
                if not field_ids or unknown:
                    raise ValueError(f'Field selection must be nonempty and valid; unknown fields: {sorted(unknown)}')
                form['fields']=[field for field in form['fields'] if field['id'] in field_ids]
            result,field_results={},[]
            models=Models(run)
            params=StdioServerParameters(command=sys.executable,args=['-m','poc.mcp_server'],cwd=str(ROOT),
                env={**os.environ,'POC_CORPUS':corpus_id,'POC_RUN_ID':run.run_id,'PYTHONIOENCODING':'utf-8'})
            write_json(run.directory/'experiment.json',{'corpus_id':corpus_id,'variant':variant,
                       'repetition':repetition,'field_ids':[f['id'] for f in form['fields']],
                       'index':index_manifest or read_json(ROOT/'data/indexes'/f'{corpus_id}.json'),'model_digests':models.digests})
        async with stdio_client(params) as (reader,writer):
            async with ClientSession(reader,writer) as session:
                await session.initialize()
                tools=await session.list_tools()
                write_json(run.directory/'mcp-tools.json',[tool.model_dump(mode='json') for tool in tools.tools])
                for field in form['fields']:
                    check = getattr(run, 'check_cancelled', None)
                    if check:
                        check()
                    try:
                        entry=await extract_field(session,run,models,field,variant,repetition)
                    except Exception as exc:
                        entry={'id':field['id'],'path':field['path'],'question':field['question'],
                               'status':'error','value':None,'evidence':[],
                               'reason':f'{type(exc).__name__}: {str(exc)[:600]}','rounds':[]}
                    field_results.append(entry)
                    set_path(result,field['path'],entry['value'])
                    write_json(run.directory/'result.json',result)
                    write_json(run.directory/'fields.json',field_results)
                    print(f"{variant}/{corpus_id}/{field['id']}: {entry['status']}",flush=True)
        if finish_run:
            run.finish(status='partial' if any(e['status']=='error' for e in field_results) else 'complete',
                   corpus_id=corpus_id,variant=variant,repetition=repetition,
                   resolved=sum(entry['status']=='filled' for entry in field_results),fields=len(field_results))
        return run.run_id
    except BaseException:
        if finish_run:
            run.finish(status='failed',corpus_id=corpus_id,variant=variant,repetition=repetition)
        raise


async def extract_field(session,run,models,field,variant,repetition):
    query=field['question']
    tried=set()
    all_chunks={}
    rounds=[]
    answer={'value':None,'status':'limit_reached','evidence':[],'reason':'No supported answer'}
    max_rounds=run.settings['max_rounds_per_field'] if variant=='F' else 1
    with run.span('field','extract',field_path=field['path']) as field_span:
        for number in range(1,max_rounds+1):
            if query.casefold() in tried:
                break
            tried.add(query.casefold())
            with run.span('round','investigate',field_path=field['path'],round_index=number):
                found=await call_tool(session,run,'search_passages',{'query':query,'variant':variant,
                    'limit':run.settings['top_k']},field['path'],number)
                ids=[hit['id'] for hit in found['hits']]
                read=await call_tool(session,run,'read_passages',{'chunk_ids':ids},field['path'],number)
                for chunk in read['chunks']:
                    all_chunks[chunk['id']]=chunk
                # Keep a bounded memory so a follow-up can combine old and new evidence.
                previous=[chunk for cid,chunk in all_chunks.items() if cid not in ids]
                evidence=read['chunks']
                if previous and len(evidence)>1:
                    evidence=evidence[:run.settings['top_k']-1]+previous[-1:]
                prompt=json.dumps({'question':field['question'],'value_schema':field['value_schema'],
                    'instructions':'Extraia somente o que está sustentado nos trechos. Datas em AAAA-MM-DD. Use status filled quando houver resposta sustentada: value contém a resposta, evidence contém citação literal curta com chunk_id e next_query é vazio. Nos estados not_found, conflicting e search_again, value deve ser null. not_found significa que a informação não foi localizada nos trechos; isso não prova ausência no documento. Se faltar evidência, prefira search_again com uma consulta diferente e específica em next_query. Alegações preservam atribuição. Listas pedidas devem incluir todos os itens sustentados. Não use conhecimento externo.',
                    'previous_reason':answer.get('reason',''),'passages':evidence},ensure_ascii=False)
                if run.settings.get('answer_prompt'):
                    from workbench.configuration import render_prompt
                    prompt=render_prompt(run.settings['answer_prompt'],json.loads(prompt))
                try:
                    answer=models.generate(prompt,answer_schema(field['value_schema']),'generation',cache=False,seed=run.settings.get('seed',42)+repetition)
                    raw_answer=json.loads(json.dumps(answer))
                    validate(answer,answer_schema(field['value_schema']))
                    with run.span('validation','citations_and_schema',field_path=field['path']):
                        errors=verify_answer(answer,evidence,field['value_schema'])
                    support=None
                    if not errors and answer['status']=='filled':
                        support_payload={
                            'task':'Confira a resposta usando somente as passagens. Primeiro escreva reason com uma justificativa de até duas frases. Depois marque supported=true se as passagens sustentam o valor como resposta à pergunta. Marque false apenas quando houver erro factual, contradição ou falta de suporte. Considere atribuição, datas, negação e escopo. Maiúsculas, acentos e formatos equivalentes de datas não alteram o significado. Para listas, confira cada item.',
                            'question':field['question'],'proposed_value':answer['value'],
                            'citations':answer['evidence'],'passages':evidence}
                        if run.settings.get('verify_prompt'):
                            from workbench.configuration import render_prompt
                            support_prompt=render_prompt(run.settings['verify_prompt'],support_payload)
                        else:
                            support_prompt=json.dumps(support_payload,ensure_ascii=False)
                        support=models.generate(support_prompt,SUPPORT_SCHEMA,'support_validation',cache=False,seed=run.settings.get('seed',42)+repetition)
                        if not support['supported']:
                            errors.append(support['reason'])
                    if errors:
                        answer.update(status='search_again',value=None,reason='; '.join(errors),next_query=field['question']+' fonte literal')
                    rounds.append({'round':number,'query':query,'retrieved_ids':ids,'retrieval':found,'answer':answer.copy(),'raw_answer':raw_answer,
                                   'validation_errors':errors,'support_check':support})
                except (ValueError,ValidationError) as exc:
                    answer={'status':'search_again','value':None,'reason':str(exc),'evidence':[],
                            'next_query':field['question']+' trecho original'}
                    rounds.append({'round':number,'query':query,'retrieved_ids':ids,'retrieval':found,'answer':answer.copy(),'validation_errors':[str(exc)]})
                if answer['status'] in ('filled','conflicting'):
                    break
                next_query=answer.get('next_query','').strip()
                if not next_query:
                    break
                query=next_query
        status=answer['status']
        if status=='search_again':
            status='limit_reached'
        field_span.update(rounds=len(rounds),field_status=status)
    return {'id':field['id'],'path':field['path'],'question':field['question'],
            'status':status,'value':answer['value'] if status=='filled' else None,
            'evidence':[{**citation,'page':all_chunks[citation['chunk_id']]['page']}
                        for citation in answer.get('evidence',[]) if citation.get('chunk_id') in all_chunks],
            'reason':answer.get('reason',''),'rounds':rounds}
