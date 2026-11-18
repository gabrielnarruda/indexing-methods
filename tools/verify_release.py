"""Check post-benchmark maintenance against the preserved experimental snapshot."""
import ast
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from poc.documents import split_text


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def functions(source):
    return {node.name:ast.dump(node,include_attributes=False) for node in ast.parse(source).body
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}


def main(smoke_run=None):
    manifest=read(ROOT/'runs/benchmark-full/benchmark.json')
    changed=[]
    for relative,expected in manifest['frozen_inputs'].items():
        if relative=='indexes':
            continue
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=expected:
            changed.append(relative)
    assert set(changed)=={'poc/documents.py','poc/extraction.py'}, changed
    with zipfile.ZipFile(ROOT/'reports/full/frozen-inputs.zip') as archive:
        for relative,allowed in [('poc/documents.py','split_text'),('poc/extraction.py','extract_form')]:
            before=functions(archive.read(relative).decode('utf-8'))
            after=functions((ROOT/relative).read_text(encoding='utf-8'))
            assert set(before)==set(after)
            assert all(before[key]==after[key] for key in before if key!=allowed)
    counts={}
    for corpus in ('adpf54','dom-casmurro'):
        index=read(ROOT/'data/indexes'/f'{corpus}.json')
        document=read(ROOT/index['directory']/'document.json')
        settings=manifest['config']
        actual=[(page['page'],start,end,text) for page in document['pages']
                for start,end,text in split_text(page['text'],settings['chunk_characters'],settings['overlap_characters'])]
        expected=[(chunk['page'],chunk['start'],chunk['end'],chunk['text']) for chunk in document['chunks']]
        assert actual==expected
        counts[corpus]=len(actual)
    result={'status':'passed','benchmark':'full','changed_source_files':changed,
            'identical_chunks_under_benchmark_configuration':counts,
            'unchanged_functions':'All except split_text and extract_form initialization',
            'experimental_source':'../full/frozen-inputs.zip',
            'maintenance_changes':['Guarantee progress with high overlap',
                                   'Reject empty or unknown field selections',
                                   'Record initialization failures and timing'],
            'scope':'Regression of source layout and unchanged extraction/retrieval logic; benchmark outputs remain from the archived version'}
    if smoke_run:
        directory=ROOT/'runs'/smoke_run
        metadata=read(directory/'run.json')
        fields=read(directory/'fields.json')
        metrics=read(directory/'metrics.json')
        assert metadata['status']=='complete' and fields
        assert all(field['status']=='filled' for field in fields)
        assert metrics['stages']['initialization']['calls']==1
        result['release_smoke']={'run_id':smoke_run,'status':metadata['status'],
                                 'result':read(directory/'result.json'),'metrics':metrics}
    (ROOT/'reports/validation/release.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--smoke-run')
    main(parser.parse_args().smoke_run)
