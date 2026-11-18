from .common import ROOT, read_json
from .models import Models
from .storage import Storage


def fuse(rankings, limit):
    scores, records = {}, {}
    for ranking in rankings:
        seen=set()
        for rank, record in enumerate(ranking,1):
            key=record['id']
            if key in seen:
                continue
            seen.add(key)
            scores[key]=scores.get(key,0)+1/(60+rank)
            records[key]=record
    ordered=sorted(scores,key=lambda key:(-scores[key],key))[:limit]
    return [{**records[key],'fusion_score':scores[key]} for key in ordered]


class Retriever:
    def __init__(self, corpus_id, run):
        self.run=run
        self.manifest=read_json(ROOT/'data/indexes'/f'{corpus_id}.json')
        self.document=read_json(ROOT/self.manifest['directory']/'document.json')
        self.chunks={c['id']:c for c in self.document['chunks']}
        self.storage=Storage(run.settings)
        self.models=None

    def search(self, query, variant='B', limit=4):
        if variant not in 'ABCDEF' or len(variant)!=1:
            raise ValueError('Unknown retrieval variant')
        limit=max(1,min(limit,12))
        index=self.manifest['index_name']
        with self.run.span('retrieval','search',variant=variant,query=query):
            lexical=self.storage.search(index,query,limit=12)
            rankings=[lexical]
            if variant!='A':
                if self.models is None:
                    self.models=Models(self.run)
                vector=self.models.embed([query],'query_embedding')[0]
                rankings.append(self.storage.search(index,query,vector=vector,limit=12))
            if variant in 'CEF':
                summaries=self.storage.search(index,query,kind='summary',limit=3)
                children=[]
                for summary in summaries:
                    for cid in summary['chunk_ids']:
                        children.append(self.chunks[cid])
                rankings.append(children)
            initial=fuse(rankings,12)
            if variant in 'DEF':
                with self.run.span('graph_retrieval','expand',seed_count=min(4,len(initial))):
                    ids=self.storage.expand_graph(index,[c['id'] for c in initial[:4]],query,limit=12)
                    rankings.append([self.chunks[cid] for cid in ids if cid in self.chunks])
            selected=fuse(rankings,limit)
            return {'query':query,'variant':variant,'hits':[
                {'id':c['id'],'page':c['page'],'preview':c['text'][:220],
                 'score':c['fusion_score']} for c in selected]}

    def read(self, chunk_ids):
        if len(chunk_ids)>12:
            raise ValueError('At most 12 chunks per read')
        if any(cid not in self.chunks for cid in chunk_ids):
            raise ValueError('Chunk outside selected corpus or index version')
        return {'chunks':[self.chunks[cid] for cid in chunk_ids]}

    def sections(self, offset=0, limit=20):
        if offset<0 or not 1<=limit<=50:
            raise ValueError('Invalid pagination')
        sections=self.document['sections']
        return {'sections':sections[offset:offset+limit], 'total':len(sections),
                'next_offset':offset+limit if offset+limit<len(sections) else None}

    def follow(self, chunk_ids, query=''):
        self.read(chunk_ids)
        ids=self.storage.expand_graph(self.manifest['index_name'],chunk_ids,query)
        return self.read(ids)
