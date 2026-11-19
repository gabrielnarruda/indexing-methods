"""Planning, immutable input snapshots and read-only result inspection."""
from itertools import product
import json
import uuid

import httpx

from poc.common import ROOT, config, digest, read_json
from . import database as db
from .configuration import Recipe, page_selection
from .metrics import measure, events_for

def corpus():
    return read_json(ROOT/'data/corpus-manifest.json')

def datasets():
    cases=read_json(ROOT/'evaluation/cases.json')
    result=[]
    for source in corpus():
        versions=db.dataset_versions(source['id'])
        if not versions:
            original={'form':read_json(ROOT/'forms'/f"{source['id']}.json"),'cases':[c for c in cases['cases'] if c['corpus_id']==source['id']],
                      'reference_status':'provisório; não revisado por humano'}
            versions=[db.dataset_version(source['id'],original)]
        result.append({'source':source,**versions[0], 'versions':[{'id':v['id'],'revision':v['revision']} for v in versions]})
    return result

def save_dataset(corpus_id,form,cases):
    import re
    from jsonschema import Draft202012Validator, validate
    source=next((s for s in corpus() if s['id']==corpus_id),None)
    if not source:raise ValueError('Documento não encontrado.')
    if form.get('corpus_id')!=corpus_id or not isinstance(form.get('fields'),list) or not 1<=len(form['fields'])<=200:
        raise ValueError('Formulário precisa de corpus_id e 1 a 200 campos.')
    ids=set();paths=set()
    for field in form['fields']:
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',field.get('id','')) or field['id'] in ids:
            raise ValueError('IDs de campo devem ser únicos e simples.')
        path=field.get('path','')
        if not re.fullmatch(r'(?:/[a-zA-Z0-9_-]+)+',path) or any(path==p or path.startswith(p+'/') or p.startswith(path+'/') for p in paths):
            raise ValueError('Caminhos JSON devem ser distintos, sem colisão entre pai e filho.')
        if not isinstance(field.get('question'),str) or not 3<=len(field['question'])<=5000:
            raise ValueError('Pergunta inválida.')
        def check_inline(value):
            if isinstance(value,dict):
                if '$ref' in value:raise ValueError('Use schemas de valor inline, sem $ref externo ou interno.')
                for item in value.values():check_inline(item)
            elif isinstance(value,list):
                for item in value:check_inline(item)
        check_inline(field['value_schema'])
        Draft202012Validator.check_schema(field['value_schema'])
        ids.add(field['id']);paths.add(path)
    if not isinstance(cases,list) or len({c['field_id'] for c in cases})!=len(cases):raise ValueError('Referências duplicadas ou inválidas.')
    fields={f['id']:f for f in form['fields']}
    for case in cases:
        if case.get('field_id') not in ids or case.get('corpus_id')!=corpus_id or case.get('split') not in ('development','held_out'):
            raise ValueError('Referência fora do formulário ou conjunto inválido.')
        if any(not isinstance(p,int) or not 1<=p<=source['pages'] for p in case.get('reference_pages',[])):
            raise ValueError('Página de referência fora do documento.')
        if case.get('expected') is not None:validate(case['expected'],fields[case['field_id']]['value_schema'])
    return db.dataset_version(corpus_id,{'form':form,'cases':cases,'reference_status':'editado pelo usuário; estado de revisão por campo'})

def model_catalog():
    settings=config()
    with httpx.Client(timeout=5) as client:
        tags=client.get(settings['ollama_url']+'/api/tags').raise_for_status().json()['models']
        result=[]
        for model in tags:
            info=client.post(settings['ollama_url']+'/api/show',json={'model':model['name']}).raise_for_status().json()
            result.append({'name':model['name'],'digest':model['digest'],'size':model['size'],'capabilities':info.get('capabilities',[])})
    return result

def plan(base, axes, documents, repetitions, field_ids=None, mode='end_to_end', split='development',dataset_versions=None):
    if not documents or len(set(documents))!=len(documents):
        raise ValueError('Selecione documentos distintos.')
    if not 1<=repetitions<=10:
        raise ValueError('Escolha entre 1 e 10 repetições.')
    if mode not in ('end_to_end','index_only') or split not in ('development','held_out','all'):
        raise ValueError('Modo ou conjunto de avaliação inválido.')
    allowed=set(Recipe.model_fields)-{'name'}
    if len(axes)>5 or not set(axes)<=allowed or any(not isinstance(v,list) or not v or len(v)>10 for v in axes.values()):
        raise ValueError('Use até cinco eixos válidos com uma a dez alternativas cada.')
    count=repetitions*len(documents)
    for values in axes.values():count*=len(values)
    if count>200:raise ValueError('A bateria local permite até 200 runs por envio.')
    rows=[]
    dataset_lookup={d['source']['id']:d for d in datasets()}
    for doc,version in (dataset_versions or {}).items():
        if doc not in dataset_lookup:raise ValueError('Versão de documento inválida.')
        snapshot=next((v for v in db.dataset_versions(doc) if v['id']==version),None)
        if not snapshot:raise ValueError('Versão do formulário não encontrada.')
        dataset_lookup[doc]={**dataset_lookup[doc],**snapshot}
    for doc in documents:
        if doc not in dataset_lookup:raise ValueError('Documento não encontrado.')
    for combination in product(*axes.values()):
        recipe=Recipe.model_validate({**base,**dict(zip(axes,combination))})
        selections={}
        for doc in documents:
            dataset=dataset_lookup[doc]
            page_selection(recipe.pages,dataset['source']['pages'])
            by_id={f['id']:f for f in dataset['form']['fields']}
            requested=(field_ids or {}).get(doc)
            permitted={c['field_id'] for c in dataset['cases'] if split=='all' or c.get('split')==split}
            selected=list(by_id) if split=='all' else [key for key in by_id if key in permitted]
            if requested is not None:
                if set(requested)-by_id.keys() or not requested:raise ValueError('Seleção de campos inválida.')
                selected=[key for key in selected if key in requested]
            if not selected and mode!='index_only':raise ValueError(f'Nenhum campo elegível para {doc} no conjunto {split}.')
            selections[doc]=selected
        rows.append({'recipe':recipe.model_dump(),'fields':selections})
    return {'configurations':rows,'configuration_count':len(rows),'run_count':count,
            'documents':documents,'repetitions':repetitions,'mode':mode,'split':split,
            'datasets':{doc:dataset_lookup[doc] for doc in documents},
            'notice':'Custos de API locais são zero; hardware exige tarifa. Não há previsão de duração sem medições compatíveis.'}

def launch(planned, parent_id=None):
    models=model_catalog();available={m['name']:m for m in models}
    # Validate every configuration before inserting any run.
    for row in planned['configurations']:
        recipe=row['recipe']
        for key in ('graph_model','summary_model','answer_model','verify_model','embedding_model'):
            name=recipe[key]
            if name not in available:raise ValueError(f'Modelo não instalado: {name}')
            capability='embedding' if key=='embedding_model' else 'completion'
            if capability not in available[name]['capabilities']:raise ValueError(f'{name} não oferece {capability}.')
    datasets_by_id=planned['datasets']
    batch_id=uuid.uuid4().hex; jobs=[]
    for row in planned['configurations']:
        saved=db.configuration(row['recipe'],parent_id)
        recipe=row['recipe']
        used={recipe[k] for k in ['graph_model','summary_model','answer_model','verify_model','embedding_model']}
        for doc in planned['documents']:
            dataset=datasets_by_id[doc]
            snapshot={'recipe':recipe,'source':dataset['source'],'form':dataset['form'],'cases':dataset['cases'],
                      'dataset_version':dataset['id'],
                      'field_ids':row['fields'][doc],'mode':planned['mode'],'split':planned['split'],
                      'model_digests':{m:available[m]['digest'] for m in used}}
            snapshot['input_hash']=digest(json.dumps([snapshot['source']['sha256'],snapshot['form'],snapshot['cases'],snapshot['field_ids'],recipe['pages']],sort_keys=True).encode())
            for rep in range(planned['repetitions']):
                jobs.append(db.enqueue(saved['id'],doc,rep,snapshot,batch_id))
    return {'batch_id':batch_id,'jobs':jobs}

def detail(job_id,include_events=False):
    job=db.get_job(job_id)
    job['metrics']=measure(job)
    directory=ROOT/'runs'/job_id
    manifest=read_json(directory/'run.json') if (directory/'run.json').exists() else {}
    job['provenance']=manifest.get('provenance')
    for key,filename in [('fields','fields.json'),('output','result.json')]:
        job[key]=read_json(directory/filename) if (directory/filename).exists() else ([] if key=='fields' else {})
    if include_events:job['events']=events_for(job_id)
    return job

def jobs():
    with db.connect() as connection:
        ids=[r['id'] for r in connection.execute('SELECT id FROM jobs ORDER BY created_at DESC LIMIT 1000')]
    result=[]
    for job_id in ids:
        job=db.get_job(job_id);job['metrics']=measure(job)
        result.append(job)
    return result

def comparison(a,b):
    first,second=detail(a,True),detail(b,True)
    differences={k:{'reference':v,'candidate':second['request']['recipe'].get(k)} for k,v in first['request']['recipe'].items() if v!=second['request']['recipe'].get(k)}
    compatible=first['request']['input_hash']==second['request']['input_hash']
    return {'reference':first,'candidate':second,'compatible':compatible,'differences':differences,
            'warning':None if compatible else 'Documentos, páginas, perguntas ou gabaritos diferem. As médias de qualidade não são diretamente comparáveis.'}
