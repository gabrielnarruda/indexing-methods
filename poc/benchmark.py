import asyncio
import random
import json
import platform

from .common import ROOT, config, digest, read_json, write_json
from .evaluation import evaluate_run
from .extraction import extract_form


def benchmark(repetitions=3,variants='ABCDEF',name='full',field_ids=None):
    directory=ROOT/'runs'/f'benchmark-{name}'
    directory.mkdir(parents=True,exist_ok=True)
    manifest_path=directory/'benchmark.json'
    inputs=[*sorted((ROOT/'poc').glob('*.py')),*sorted((ROOT/'forms').glob('*.json')),
            ROOT/'evaluation/cases.json',ROOT/'config.json',ROOT/'requirements.lock.txt']
    frozen={str(path.relative_to(ROOT)).replace('\\','/'):digest(path.read_bytes())
            for path in inputs if path.name!='report.py'}
    frozen['indexes']={c:read_json(ROOT/'data/indexes'/f'{c}.json')['fingerprint']
                       for c in ('adpf54','dom-casmurro')}
    fingerprint=digest(json.dumps(frozen,sort_keys=True).encode())
    if manifest_path.exists():
        manifest=read_json(manifest_path)
        if manifest['repetitions']!=repetitions or manifest['variants']!=variants or manifest.get('field_ids')!=field_ids:
            raise ValueError('Existing benchmark has different parameters; choose another name')
        if manifest.get('input_fingerprint')!=fingerprint:
            raise ValueError('Benchmark inputs changed; use a new name to avoid mixing experiments')
    else:
        jobs=[{'corpus':c,'variant':v,'repetition':r} for r in range(repetitions) for c in ['adpf54','dom-casmurro'] for v in variants]
        random.Random(42).shuffle(jobs)
        manifest={'name':name,'repetitions':repetitions,'variants':variants,'field_ids':field_ids,
                  'order_seed':42,'jobs':jobs,'input_fingerprint':fingerprint,'frozen_inputs':frozen,
                  'config':config(),'runtime':{'python':platform.python_version(),'platform':platform.platform()},
                  'generation_cache':False,'query_embedding_cache':True,'temperature':0,
                  'development_fields':['adpf54/identificacao','adpf54/relator'],
                  'evaluation_scope':'exploratory; reference split is not an independently blind evaluation'}
        write_json(manifest_path,manifest)
    for number,job in enumerate(manifest['jobs']):
        if job.get('status')=='complete':
            continue
        print(f"Benchmark {number+1}/{len(manifest['jobs'])}: {job['corpus']} {job['variant']} repeat {job['repetition']}",flush=True)
        job['status']='running'
        write_json(manifest_path,manifest)
        try:
            run_id=asyncio.run(extract_form(job['corpus'],job['variant'],job['repetition'],field_ids))
            evaluation=evaluate_run(run_id)
            job.update(status='complete',run_id=run_id,accuracy=evaluation['accuracy'])
        except Exception as exc:
            job.update(status='failed',error=str(exc)[:1000])
            write_json(manifest_path,manifest)
            raise
        write_json(manifest_path,manifest)
    return manifest
