"""Transparent deterministic scoring against provisional source-linked references."""
import re
import unicodedata

from .common import ROOT, read_json, write_json


def canonical(value):
    text=unicodedata.normalize('NFKD',str(value)).casefold()
    text=''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+',' ',text).strip()


def contains_value(actual,expected):
    return bool(re.search(r'(?<!\w)'+re.escape(canonical(expected))+r'(?!\w)',canonical(actual)))


def score_value(value,case):
    expected=case['expected']
    if expected is None:
        return {'value_correct':value is None,'list_precision':None,'list_recall':None}
    if isinstance(expected,list):
        actual=value if isinstance(value,list) else []
        matched_expected=sum(any(contains_value(item,target) for item in actual) for target in expected)
        matched_actual=sum(any(contains_value(item,target) for target in expected) for item in actual)
        precision=matched_actual/len(actual) if actual else 0
        recall=matched_expected/len(expected) if expected else int(not actual)
        return {'value_correct':precision==1 and recall==1 and len(actual)==len(expected) and len(actual)==len(set(map(canonical,actual))),
                'list_precision':precision,'list_recall':recall}
    if isinstance(expected,(bool,int,float)):
        correct=type(value)==type(expected) and value==expected
    else:
        correct=value is not None and any(contains_value(value,target) for target in [expected,*case.get('aliases',[])])
    return {'value_correct':bool(correct),'list_precision':None,'list_recall':None}


def evaluate_run(run_id):
    directory=ROOT/'runs'/run_id
    experiment=read_json(directory/'experiment.json')
    cases={c['field_id']:c for c in read_json(ROOT/'evaluation/cases.json')['cases'] if c['corpus_id']==experiment['corpus_id']}
    fields=read_json(directory/'fields.json')
    index=experiment['index']
    document=read_json(ROOT/index['directory']/'document.json')
    pages={chunk['id']:chunk['page'] for chunk in document['chunks']}
    scores=[]
    for field in fields:
        case=cases[field['id']]
        score=score_value(field['value'],case)
        retrieved={pages[cid] for step in field['rounds'] for cid in step['retrieved_ids'] if cid in pages}
        reference_pages=set(case['reference_pages'])
        checks=[error for step in field['rounds'] for error in step.get('validation_errors',[])]
        resolved=field['status']=='filled'
        correct=score['value_correct'] and (resolved if case['expected'] is not None else field['status']=='not_found')
        scores.append({'field_id':field['id'],'split':case['split'],**score,'correct':correct,
            'status':field['status'],'expected':case['expected'],'actual':field['value'],
            'reference_page_hit':bool(retrieved & reference_pages) if reference_pages else None,
            'has_citations':bool(field['evidence']),'validation_errors':len(checks),
            'rounds':len(field['rounds']),'is_negative':case['expected'] is None})
    output={'run_id':run_id,**experiment,'scoring':'deterministic aliases and literal citation checks; semantic support requires review',
            'reference_status':'assistant annotated, provisional, not human reviewed','fields':scores,
            'accuracy':sum(s['correct'] for s in scores)/len(scores) if scores else None,
            'field_count':len(scores)}
    write_json(directory/'evaluation.json',output)
    return output
