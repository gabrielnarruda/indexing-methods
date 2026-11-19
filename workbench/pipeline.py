"""Real pipeline with per-stage artifacts, provenance and independent cache keys."""
from contextlib import contextmanager
import json
import re
import time

import pymupdf
from jsonschema import validate

from poc.common import ROOT, digest, read_json, write_json
from poc.documents import split_text
from poc.indexing import accepted_facts
from poc.models import Models
from poc.storage import Storage
from . import database as db
from .configuration import page_selection, render_prompt

STAGES = [('parse','Leitura do PDF'),('ocr','OCR'),('chunk','Recortes e pacotes'),
          ('relations','Entidades, eventos e relações'),('summary','Resumos'),
          ('embedding','Embeddings dos trechos'),('summary_embedding','Embeddings dos resumos'),
          ('search_index','Gravação no OpenSearch'),('graph_index','Gravação no Neo4j'),
          ('retrieval','Recuperação / MCP'),('generation','Extração JSON'),
          ('verification','Verificação'),('evaluation','Avaliação')]

def artifact_path(path):
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)

class Cancelled(BaseException):
    pass

class Pipeline:
    def __init__(self, job, run):
        self.job, self.run = job, run
        self.recipe = job['request']['recipe']
        self.models = Models(run)
        self.storage = Storage(run.settings)
        self.artifacts = {}
        self.partial_history = {}
        self.run.check_cancelled = self.check
        for name,_ in STAGES:
            db.stage(job['id'],name,status='pending')
        for model,expected in job['request'].get('model_digests',{}).items():
            if self.models.digests.get(model) != expected:
                raise ValueError(f'O modelo {model} mudou desde o planejamento. Crie outra run.')

    def check(self):
        if db.get_job(self.job['id'])['cancel_requested']:
            raise Cancelled('Cancelada pelo usuário; resultados parciais preservados.')

    def close(self):
        self.models.client.close()
        self.storage.close()

    def model_key(self, stage):
        model = self.recipe[stage+'_model']
        return {key:self.recipe[key] for key in [stage+'_model',stage+'_prompt','temperature','seed','max_output_tokens','context_tokens']} | {'model_digest':self.models.digests[model]}

    def artifact(self, name, inputs, parameters, produce, verify=None):
        self.check()
        nonce = self.job['id'] if self.recipe['cache_policy']=='rebuild' else None
        key = digest(json.dumps(['workbench-stage-v1',name,inputs,parameters,nonce],sort_keys=True).encode())
        directory = db.DATA/'artifacts'/key
        output, manifest = directory/'value.json', directory/'manifest.json'
        start = time.perf_counter()
        db.stage(self.job['id'],name,status='running',started_at=db.now(),artifact_key=key)
        try:
            cached = None
            if manifest.exists() and output.exists():
                meta = read_json(manifest)
                if meta.get('sha256') == digest(output.read_bytes()):
                    cached = read_json(output)
                    if verify and not verify(cached):
                        cached = None
            if cached is not None:
                elapsed = (time.perf_counter()-start)*1000
                db.stage(self.job['id'],name,status='reused',ended_at=db.now(),duration_ms=elapsed,
                         history_ms=meta['duration_ms'],source_run=meta['run_id'],detail={'new_work':'checksum, load and availability check'})
                self.artifacts[name] = {'key':key,'directory':artifact_path(directory),'reused':True,'source_run':meta['run_id']}
                return cached
            with self.run.span('pipeline',name,artifact_key=key) as event:
                value = produce()
            if verify and not verify(value):
                raise ValueError(f'Artefato {name} incompleto; não foi publicado.')
            self.check()
            write_json(output,value)
            elapsed = (time.perf_counter()-start)*1000
            historical=getattr(self,'partial_history',{}).get(name,0)
            write_json(manifest,{'key':key,'run_id':self.run.run_id,'stage':name,'duration_ms':elapsed+historical,
                                 'new_duration_ms':elapsed,'partial_historical_ms':historical,
                                 'sha256':digest(output.read_bytes()),'inputs':inputs,'parameters':parameters,'created_at':db.now()})
            self.artifacts[name] = {'key':key,'directory':artifact_path(directory),'reused':False,'source_run':self.run.run_id}
            db.stage(self.job['id'],name,status='complete',ended_at=db.now(),duration_ms=elapsed,history_ms=historical or None,source_run=self.run.run_id)
            return value
        except BaseException as exc:
            db.stage(self.job['id'],name,status='cancelled' if isinstance(exc,Cancelled) else 'failed',
                     ended_at=db.now(),duration_ms=(time.perf_counter()-start)*1000,detail={'error':str(exc)[:600]})
            raise

    def skip(self, name, reason):
        db.stage(self.job['id'],name,status='skipped',detail={'reason':reason})

    def key(self, name):
        return self.artifacts[name]['key']

    def progress(self,name,done,total):
        self.check()
        db.stage(self.job['id'],name,detail={'completed':done,'total':total})

    def build(self):
        recipe, source = self.recipe, self.job['request']['source']
        path = ROOT/'data/raw'/source['filename']
        if digest(path.read_bytes()) != source['sha256']:
            raise ValueError('O PDF mudou desde o planejamento da run.')
        def parse():
            pages=[]
            with pymupdf.open(path) as pdf:
                for number in page_selection(recipe['pages'],len(pdf)):
                    self.check()
                    page=pdf[number-1]
                    blocks=[{'text':re.sub(r'\s+',' ',b[4]).strip(),'bbox':list(b[:4])} for b in page.get_text('blocks',sort=True) if b[4].strip()]
                    if recipe['parser']=='pymupdf_dedup':
                        seen=set();unique=[]
                        for block in blocks:
                            if block['text'] not in seen:
                                unique.append(block);seen.add(block['text'])
                        blocks=unique
                    text='\n'.join(b['text'] for b in blocks)
                    pages.append({'page':number,'text':text,'blocks':blocks,'needs_ocr':len(text.strip())<20 and bool(page.get_images())})
            return {'source':source,'pages':pages}
        parsed=self.artifact('parse',[source['sha256']],{'pages':recipe['pages'],'parser':recipe['parser'],'version':pymupdf.__version__},parse)
        missing=[p['page'] for p in parsed['pages'] if p['needs_ocr']]
        if missing:
            if recipe['ocr']=='off':
                raise ValueError(f'As páginas {missing[:20]} precisam de OCR. Habilite OCR automático e instale Tesseract com os idiomas necessários.')
            def ocr():
                result=json.loads(json.dumps(parsed))
                with pymupdf.open(path) as pdf:
                    for page in result['pages']:
                        if page['needs_ocr']:
                            self.check()
                            textpage=pdf[page['page']-1].get_textpage_ocr(language=recipe['ocr_language'],dpi=200,full=True)
                            page.update(text=pdf[page['page']-1].get_text(textpage=textpage,sort=True),needs_ocr=False,ocr=True)
                return result
            parsed=self.artifact('ocr',[self.key('parse')],{'language':recipe['ocr_language'],'dpi':200},ocr)
        else:
            self.skip('ocr','Nenhuma página selecionada precisa de OCR.')
        text_key=self.key('ocr') if 'ocr' in self.artifacts else self.key('parse')
        def segment():
            chunks=[]
            for page in parsed['pages']:
                for start,end,text in split_text(page['text'],recipe['chunk_characters'],recipe['overlap_characters']):
                    chunks.append({'id':f"{source['id']}-{text_key[:10]}-p{page['page']}-c{start}",
                                   'page':page['page'],'start':start,'end':end,'text':text,
                                   'corpus_id':source['id'],'document_hash':source['sha256']})
            groups=[]; group=[]; length=0
            for chunk in chunks:
                if group and length+len(chunk['text'])>recipe['section_characters']:
                    groups.append(group);group=[];length=0
                group.append(chunk['id']);length+=len(chunk['text'])
            if group: groups.append(group)
            return {**parsed,'chunks':chunks,'sections':[{'id':f'section-{i}','chunk_ids':g} for i,g in enumerate(groups)]}
        document=self.artifact('chunk',[text_key],{k:recipe[k] for k in ['chunk_characters','overlap_characters','section_characters']},segment)
        if not document['chunks']:
            raise ValueError('As páginas selecionadas não produziram texto pesquisável.')
        chunks={c['id']:c for c in document['chunks']}
        # Independent calls and cache keys: changing relation extraction never changes embeddings.
        def enrich(kind):
            result=[]
            artifact_key=next(s for s in db.get_job(self.job['id'])['stages'] if s['name']==kind)['artifact_key']
            checkpoint_dir=db.DATA/'artifacts'/artifact_key/'sections'
            reused=0
            for i,section in enumerate(document['sections']):
                self.progress(kind,i,len(document['sections']))
                checkpoint=checkpoint_dir/(str(i)+'.json')
                if checkpoint.exists():
                    saved=read_json(checkpoint)
                    if saved.get('sha256')==digest(json.dumps(saved['value'],sort_keys=True).encode()):
                        with self.run.span(kind,'section_checkpoint',cache_hit=True,billable=False,source_run=saved['run_id']):
                            result.append(saved['value'])
                        self.partial_history[kind]=self.partial_history.get(kind,0)+saved['duration_ms']
                        reused+=1
                        continue
                members=[chunks[cid] for cid in section['chunk_ids']]
                passages=[{'source_idx':j,'text':c['text']} for j,c in enumerate(members)]
                if kind=='relations':
                    schema={'type':'object','properties':{'relations':{'type':'array','maxItems':recipe['max_relations'],
                      'items':{'type':'object','properties':{k:{'type':'integer' if k=='source_idx' else 'string'} for k in ['subject','predicate','object','source_idx','quote','date','speaker']},
                               'required':['subject','predicate','object','source_idx','quote','date','speaker'],'additionalProperties':False}}},'required':['relations'],'additionalProperties':False}
                    prompt=recipe['graph_prompt']
                else:
                    schema={'type':'object','properties':{'title':{'type':'string'},'summary':{'type':'string'}},'required':['title','summary'],'additionalProperties':False}
                    prompt=recipe['summary_prompt']
                started=time.perf_counter()
                data=self.models.generate(render_prompt(prompt,{'passages':passages}),schema,kind,cache=False,seed=recipe['seed'])
                validate(data,schema)
                if kind=='relations':
                    facts=accepted_facts(data['relations'],members)
                    result.append({**section,'facts':facts,'proposed':len(data['relations']),'rejected':len(data['relations'])-len(facts)})
                else: result.append({**section,**data})
                write_json(checkpoint,{'value':result[-1],'sha256':digest(json.dumps(result[-1],sort_keys=True).encode()),
                                       'duration_ms':(time.perf_counter()-started)*1000,'run_id':self.run.run_id})
                self.progress(kind,i+1,len(document['sections']))
            db.stage(self.job['id'],kind,detail={'completed':len(result),'total':len(document['sections']),'reused_sections':reused})
            return result
        if recipe['graph_enabled']:
            relations=self.artifact('relations',[self.key('chunk')],self.model_key('graph')|{'max_relations':recipe['max_relations']},lambda:enrich('relations'))
        else:
            relations=[];self.skip('relations','Grafo desativado nesta configuração.')
        if recipe['summary_enabled']:
            summaries=self.artifact('summary',[self.key('chunk')],self.model_key('summary'),lambda:enrich('summary'))
        else:
            summaries=[];self.skip('summary','Resumos desativados nesta configuração.')
        embed_parameters={'model':recipe['embedding_model'],'digest':self.models.digests[recipe['embedding_model']]}
        def vectors(texts,name):
            result=[]
            for start in range(0,len(texts),16):
                self.progress(name,start,len(texts))
                result.extend(self.models.embed(texts[start:start+16],name))
            self.progress(name,len(texts),len(texts))
            return result
        embedded=self.artifact('embedding',[self.key('chunk')],embed_parameters,lambda:vectors([c['text'] for c in document['chunks']],'embedding'))
        if summaries:
            summary_vectors=self.artifact('summary_embedding',[self.key('summary')],embed_parameters,lambda:vectors([s['title']+'\n'+s['summary'] for s in summaries],'summary_embedding'))
        else:
            summary_vectors=[];self.skip('summary_embedding','Não há resumos para vetorizar.')
        search_key=digest(json.dumps([self.key('embedding'),self.artifacts.get('summary_embedding',{}).get('key'), 'source-text-excluded-v1'],sort_keys=True).encode())[:24]
        index_name='wb-'+source['id']+'-'+search_key
        def write_search():
            self.storage.http.put('/'+index_name,json={'settings':{'number_of_shards':1,'number_of_replicas':0,'index.knn':True},'mappings':{
                '_source':{'excludes':['text','vector']},'properties':{'text':{'type':'text','analyzer':'portuguese'},
                'kind':{'type':'keyword'},'corpus_id':{'type':'keyword'},'chunk_ids':{'type':'keyword'},'page':{'type':'integer'},
                'vector':{'type':'knn_vector','dimension':len(embedded[0])}}}}).raise_for_status() if self.storage.http.head('/'+index_name).status_code!=200 else None
            records=[{**c,'kind':'chunk','vector':v} for c,v in zip(document['chunks'],embedded,strict=True)]
            records.extend({'id':s['id'],'kind':'summary','text':s['title']+'\n'+s['summary'],'chunk_ids':s['chunk_ids'],'corpus_id':source['id'],'vector':v} for s,v in zip(summaries,summary_vectors,strict=True))
            for start in range(0,len(records),32):
                self.progress('search_index',start,len(records));self.storage.put_records(index_name,records[start:start+32])
            self.progress('search_index',len(records),len(records))
            return {'index_name':index_name,'records':len(records),'dimensions':len(embedded[0])}
        def search_ready(value):
            response=self.storage.http.get('/'+value['index_name']+'/_count')
            return response.status_code==200 and response.json()['count']==value['records']
        search=self.artifact('search_index',[self.key('embedding'),self.artifacts.get('summary_embedding',{}).get('key')],{'name':index_name,'source':'text and vectors excluded'},write_search,search_ready)
        facts=[fact for section in relations for fact in section['facts']]
        graph_key=digest(json.dumps([self.key('chunk'),self.artifacts.get('relations',{}).get('key')],sort_keys=True).encode())[:24]
        graph_name='wb-graph-'+source['id']+'-'+graph_key
        def graph_ready(value):
            with self.storage.graph.session() as session:
                count=session.run('MATCH (c:Chunk {version:$v}) RETURN count(c) AS n',v=value['graph_name']).single()['n']
                fact_count=session.run('MATCH (f:Fact {version:$v}) RETURN count(f) AS n',v=value['graph_name']).single()['n']
            return count==len(chunks) and fact_count==value['facts']
        def write_graph():
            self.storage.index_graph(graph_name,document['chunks'],facts)
            return {'graph_name':graph_name,'facts':len({json.dumps(f,sort_keys=True) for f in facts})}
        graph=self.artifact('graph_index',[self.key('chunk'),self.artifacts.get('relations',{}).get('key')],{'version':graph_name},write_graph,graph_ready)
        directory=db.DATA/'indexes'/digest((index_name+graph_name).encode())[:24]
        write_json(directory/'document.json',document)
        write_json(directory/'relations.json',relations)
        write_json(directory/'summaries.json',summaries)
        manifest={'corpus_id':source['id'],'fingerprint':directory.name,'index_name':index_name,'graph_name':graph_name,
                  'directory':artifact_path(directory),'pages':len(document['pages']),'selected_pages':[p['page'] for p in document['pages']],
                  'chunks':len(chunks),'sections':len(summaries),'facts':graph['facts'],'source_hash':source['sha256'],
                  'embedding':embed_parameters,'run_id':self.run.run_id,'artifacts':self.artifacts,
                  'rejected_facts':sum(s['rejected'] for s in relations)}
        write_json(directory/'manifest.json',manifest)
        return manifest
