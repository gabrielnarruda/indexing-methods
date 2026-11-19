"""Evaluate immutable references without exposing them to the reader model."""
from poc.evaluation import score_value

EVALUATOR_VERSION='deterministic-v2'

def evaluate(fields,cases,document):
    lookup={c['field_id']:c for c in cases}
    pages={c['id']:c['page'] for c in document['chunks']}
    scores=[]
    for field in fields:
        case=lookup.get(field['id'])
        if not case:
            scores.append({'field_id':field['id'],'annotated':False,'correct':None,'actual':field['value'],'status':field['status']})
            continue
        score=score_value(field['value'],case)
        correct=score['value_correct'] and (field['status']=='filled' if case['expected'] is not None else field['status']=='not_found')
        retrieved={pages[cid] for step in field['rounds'] for cid in step['retrieved_ids'] if cid in pages}
        ref=set(case.get('reference_pages',[]))
        scores.append({'field_id':field['id'],'annotated':True,**score,'correct':bool(correct),
                       'actual':field['value'],'expected':case['expected'],'status':field['status'],
                       'split':case.get('split'),'reference_pages':list(ref),'reference_page_hit':bool(ref&retrieved) if ref else None,
                       'reference_status':case.get('reference_status','provisional'),'has_citations':bool(field['evidence']),
                       'rounds':len(field['rounds'])})
    annotated=[s for s in scores if s['annotated']]
    return {'fields':scores,'field_count':len(scores),'annotated_count':len(annotated),
            'accuracy':sum(s['correct'] for s in annotated)/len(annotated) if annotated else None,
            'coverage':sum(f['status']=='filled' for f in fields)/len(fields) if fields else None,
            'reference_status':'provisório; exige revisão humana','evaluator_version':EVALUATOR_VERSION,
            'scope_note':'Acerto automático contra o gabarito; citação literal e suporte semântico são critérios diferentes.'}
