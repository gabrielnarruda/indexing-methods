import json
from itertools import islice

import pytest
from jsonschema import validate

from poc.documents import split_text
from poc.extraction import answer_schema, set_path, verify_answer
from poc.indexing import accepted_facts
from poc.retrieval import fuse
from poc.telemetry import Run, summarize
from poc.common import config, read_json, ROOT
from poc.evaluation import contains_value, score_value


def test_chunking_preserves_every_character_and_offsets():
    text=('O documento tem informação verificável.\n'*90)+'ÚLTIMO'
    chunks=list(split_text(text,100,20))
    covered=set()
    for start,end,value in chunks:
        assert value==text[start:end]
        covered.update(range(start,end))
    assert covered==set(range(len(text)))
    assert chunks[-1][2].endswith('ÚLTIMO')


@pytest.mark.parametrize('size,overlap',[(10,10),(5,9),(10,-1)])
def test_invalid_overlap_terminates_with_error(size,overlap):
    with pytest.raises(ValueError):
        list(split_text('example',size,overlap))


def test_high_overlap_keeps_advancing_after_word_boundary():
    text='aaaa bbbb cccc'
    chunks=list(islice(split_text(text,10,9),len(text)+1))
    assert [start for start,_,_ in chunks]==[0,1,2,3,4]
    assert chunks[-1][1]==len(text)


def test_quote_must_exist_in_same_supplied_chunk():
    chunks=[{'id':'legal-1','text':'O relator é Marco Aurélio.'}]
    answer={'status':'filled','value':'Marco Aurélio','evidence':[{'chunk_id':'book-1','quote':'O relator é Marco Aurélio.'}]}
    assert verify_answer(answer,chunks,{'type':'string'})
    answer['evidence'][0]['chunk_id']='legal-1'
    assert verify_answer(answer,chunks,{'type':'string'})==[]
    answer['evidence'][0]['quote']='O relator é outro ministro.'
    assert verify_answer(answer,chunks,{'type':'string'})


def test_value_requires_citation_and_schema_type():
    assert verify_answer({'status':'filled','value':'54','evidence':[]},[],{'type':'integer'})
    assert verify_answer({'status':'not_found','value':'invention','evidence':[]},[],{'type':'string'})


def test_graph_filters_unanchored_assertions():
    chunk={'id':'c1','text':'Escobar era amigo de Bentinho.'}
    fact={'subject':'Escobar','predicate':'amigo','object':'Bentinho','source_idx':0,'quote':chunk['text']}
    assert accepted_facts([fact],[chunk])[0]['chunk_id']=='c1'
    assert accepted_facts([{**fact,'source_idx':8}],[chunk])==[]
    assert accepted_facts([{**fact,'quote':'Escobar era pai de Bentinho.'}],[chunk])==[]


def test_rrf_deduplicates_across_channels():
    rows=fuse([[{'id':'a'},{'id':'b'}],[{'id':'b'},{'id':'c'}]],3)
    assert [row['id'] for row in rows]==['b','a','c']
    assert fuse([[{'id':'a'},{'id':'a'}]],1)[0]['fusion_score']==1/61


def test_scoring_does_not_match_procedente_inside_improcedente():
    assert not contains_value('improcedente','procedente')
    assert contains_value('julgada procedente','procedente')
    assert not score_value(['124','124'],{'expected':['124','126']})['value_correct']


def test_path_assignment_keeps_siblings():
    result={}
    set_path(result,'/processo/numero',54)
    set_path(result,'/processo/relator','Marco')
    assert result=={'processo':{'numero':54,'relator':'Marco'}}


def test_forms_and_reference_cases_align():
    cases=read_json(ROOT/'evaluation/cases.json')['cases']
    assert len(cases)==40
    for corpus in ('adpf54','dom-casmurro'):
        form=read_json(ROOT/'forms'/f'{corpus}.json')
        fields={field['id']:field for field in form['fields']}
        for case in cases:
            if case['corpus_id']!=corpus:
                continue
            field=fields[case['field_id']]
            sample={'status':'not_found','value':None,'evidence':[],'reason':'absent','next_query':''}
            validate(sample,answer_schema(field['value_schema']))
            if case['expected'] is not None:
                validate(case['expected'],field['value_schema'])


def test_cost_counts_model_operations_once_including_failure(tmp_path,monkeypatch):
    import poc.telemetry as telemetry
    monkeypatch.setattr(telemetry,'ROOT',tmp_path)
    settings={**config(),'machine_hour_rate':None}
    run=Run(kind='test',settings=settings)
    with run.span('field','outer'):
        with run.span('generation','call',billable=True,input_tokens=10,output_tokens=5,api_cost=2):
            pass
        with run.span('generation','cache',cache_hit=True,billable=False):
            pass
        with pytest.raises(RuntimeError):
            with run.span('generation','retry',billable=True,input_tokens=None,api_cost=1):
                raise RuntimeError('failed after charging')
    result=run.finish()
    assert result['api_cost']==3
    assert result['model_calls']==2
    assert result['input_tokens']==10
    assert result['cache_hits']==1
    assert result['machine_cost_estimate'] is None
    assert result['usage_unknown_calls']==1
    assert result['errors']==1
