import json
import re

from .common import ROOT, digest, read_json, write_json
from .documents import parse_document
from .models import Models
from .storage import Storage
from .telemetry import Run

ENRICHMENT_SCHEMA = {"type":"object","properties":{
    "title":{"type":"string"}, "summary":{"type":"string"},
    "relations":{"type":"array","maxItems":6,"items":{"type":"object","properties":{
        "subject":{"type":"string"},"predicate":{"type":"string"},"object":{"type":"string"},
        "source_idx":{"type":"integer"},"quote":{"type":"string"},
        "date":{"type":"string"},"speaker":{"type":"string"}},
        "required":["subject","predicate","object","source_idx","quote","date","speaker"],"additionalProperties":False}}},
    "required":["title","summary","relations"],"additionalProperties":False}


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def accepted_facts(relations, chunks):
    facts=[]
    for relation in relations:
        idx=relation.get('source_idx')
        if not isinstance(idx,int) or not 0 <= idx < len(chunks):
            continue
        quote=normalize(relation.get('quote',''))
        if len(quote)<12 or quote not in normalize(chunks[idx]['text']):
            continue
        if not all(relation.get(k,'').strip() for k in ('subject','predicate','object')):
            continue
        facts.append({**relation,"quote":quote,"chunk_id":chunks[idx]['id']})
    return facts


def build_index(corpus_id, refresh=False):
    run=Run(kind='indexing')
    storage=None
    try:
        source=next(s for s in read_json(ROOT/'data/corpus-manifest.json') if s['id']==corpus_id)
        models=Models(run)
        fingerprint=digest(json.dumps([source['sha256'],run.settings,models.digests,'parser-v1'],sort_keys=True).encode())[:16]
        directory=ROOT/'data/indexes'/corpus_id/fingerprint
        directory.mkdir(parents=True,exist_ok=True)
        index_name=f"poc-{corpus_id}-{fingerprint}"
        active_path=ROOT/'data/indexes'/f'{corpus_id}.json'
        storage=Storage(run.settings)
        if (directory/'manifest.json').exists() and not refresh:
            manifest=read_json(directory/'manifest.json')
            if storage.index_is_complete(manifest):
                write_json(active_path,manifest)
                with run.span('index_reuse','ready_index',cache_hit=True):
                    pass
                run.finish(corpus_id=corpus_id,index_version=fingerprint,reused=True)
                return manifest
        document_path=directory/'document.json'
        if document_path.exists():
            document=read_json(document_path)
        else:
            document=parse_document(source,run)
            write_json(document_path,document)
        missing=[page['page'] for page in document['pages'] if page['needs_ocr']]
        if missing:
            raise ValueError(f"OCR required on pages {missing}; index has not been published")
        chunks={c['id']:c for c in document['chunks']}
        enriched=[]
        for position,section in enumerate(document['sections']):
            section_path=directory/(section['id']+'.json')
            if section_path.exists():
                enriched.append(read_json(section_path))
                with run.span('enrichment','section_checkpoint',cache_hit=True):
                    pass
                continue
            members=[chunks[cid] for cid in section['chunk_ids']]
            prompt='Resuma este conjunto de trechos em até 100 palavras e dê um título curto. Extraia até 6 relações ou eventos importantes. Use nomes explícitos. Cada relação deve incluir source_idx e uma citação literal curta da fonte indicada. Preencha date e speaker apenas quando explícitos, caso contrário use string vazia. Preserve atribuição e modalidade de alegações.\n'+json.dumps([{'source_idx':i,'text':c['text']} for i,c in enumerate(members)],ensure_ascii=False)
            data=models.generate(prompt,ENRICHMENT_SCHEMA,'enrichment',cache=True)
            facts=accepted_facts(data['relations'],members)
            result={**section,'title':data['title'],'summary':data['summary'],'facts':facts,
                    'rejected_facts':len(data['relations'])-len(facts)}
            write_json(section_path,result)
            enriched.append(result)
            print(f"{corpus_id}: enriched {position+1}/{len(document['sections'])}",flush=True)
        records=[]
        metadata={cid:[] for cid in chunks}
        facts=[f for section in enriched for f in section['facts']]
        for fact in facts:
            metadata[fact['chunk_id']].append(f"{fact['subject']} {fact['predicate']} {fact['object']}")
        for chunk in document['chunks']:
            records.append({**chunk,'kind':'chunk','metadata':' '.join(metadata[chunk['id']])})
        for section in enriched:
            records.append({'id':section['id'],'kind':'summary','text':section['title']+'\n'+section['summary'],
                            'chunk_ids':section['chunk_ids'],'corpus_id':corpus_id})
        for start in range(0,len(records),16):
            batch=records[start:start+16]
            vectors=models.embed([r['text'] for r in batch])
            for record,vector in zip(batch,vectors,strict=True):
                record['vector']=vector
            with run.span('search_index','write_batch',records=len(batch)):
                storage.create_index(index_name,len(vectors[0]))
                storage.put_records(index_name,batch)
            print(f"{corpus_id}: indexed {min(start+16,len(records))}/{len(records)}",flush=True)
        with run.span('graph_index','write_graph',facts=len(facts)):
            storage.index_graph(index_name,document['chunks'],facts)
        count=storage.http.get('/'+index_name+'/_count').raise_for_status().json()['count']
        if count!=len(records):
            raise ValueError('Search index count mismatch')
        manifest={'corpus_id':corpus_id,'fingerprint':fingerprint,'index_name':index_name,
                  'directory':str(directory.relative_to(ROOT)),'pages':len(document['pages']),
                  'chunks':len(chunks),'sections':len(enriched),'facts':len(facts),
                  'rejected_facts':sum(s['rejected_facts'] for s in enriched),
                  'model_digests':models.digests,'source_hash':source['sha256'],'run_id':run.run_id,
                  'section_method':'contiguous character-budget groups of page-preserving chunks'}
        if not storage.index_is_complete(manifest):
            raise ValueError('Search or graph index is incomplete; manifest has not been published')
        write_json(directory/'manifest.json',manifest)
        write_json(active_path,manifest)
        run.finish(corpus_id=corpus_id,index_version=fingerprint,manifest=manifest)
        return manifest
    except BaseException:
        run.finish(status='failed',corpus_id=corpus_id)
        raise
    finally:
        if storage:
            storage.close()
