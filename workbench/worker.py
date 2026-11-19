"""A detached local process owns one run; closing the browser does not stop it."""
import argparse
import asyncio
import os
import subprocess
import zipfile

import psutil

from poc.common import ROOT, config, digest, read_json, write_json
from poc.extraction import extract_form
from poc.telemetry import Run
from . import database as db
from .configuration import Recipe, runtime_settings
from .evaluation import evaluate
from .metrics import measure
from .pipeline import Cancelled, Pipeline

def implementation_snapshot():
    files={str(p.relative_to(ROOT)).replace('\\','/'):p.read_bytes()
           for folder in ['poc','workbench'] for p in sorted((ROOT/folder).glob('*.py'))}
    fingerprint=digest(b''.join(name.encode()+b'\0'+content for name,content in sorted(files.items())))
    return files,fingerprint

def execute(job_id):
    job=db.get_job(job_id)
    if job['status']!='starting':
        raise ValueError('Run is not reserved by the coordinator')
    db.update_job(job_id,status='running',pid=os.getpid(),process_created=psutil.Process().create_time(),started_at=db.now())
    recipe=Recipe.model_validate(job['request']['recipe'])
    settings=runtime_settings(recipe,config())
    run=Run(run_id=job_id,kind='workbench',settings=settings)
    pipeline=None
    status='failed'
    try:
        files,fingerprint=implementation_snapshot()
        with zipfile.ZipFile(run.directory/'implementation.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,content in files.items():archive.writestr(name,content)
        manifest=read_json(run.directory/'run.json')
        manifest['provenance']={'configuration':job['config_id'],'input_hash':job['request']['input_hash'],
                                'model_digests':job['request'].get('model_digests',{}),
                                'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                                'implementation_hash':fingerprint,'implementation_archive':'implementation.zip'}
        write_json(run.directory/'run.json',manifest)
        pipeline=Pipeline(job,run)
        index=pipeline.build()
        settings['index_manifest']=index
        manifest=read_json(run.directory/'run.json')
        manifest['config']=settings
        write_json(run.directory/'run.json',manifest)
        write_json(run.directory/'index.json',index)
        if job['request'].get('mode','end_to_end')=='index_only':
            result={'index':index,'evaluation':None}
        else:
            for name in ['retrieval','generation','verification']:
                db.stage(job_id,name,status='running',started_at=db.now())
            asyncio.run(extract_form(job['corpus_id'],recipe.variant,job['repetition'],
                                    job['request']['field_ids'],run=run,index_manifest=index,
                                    form=job['request']['form'],finish_run=False))
            pipeline.check()
            fields=read_json(run.directory/'fields.json')
            db.stage(job_id,'evaluation',status='running',started_at=db.now())
            with run.span('evaluation','score_frozen_references'):
                evaluation=evaluate(fields,job['request']['cases'],read_json(ROOT/index['directory']/'document.json'))
            write_json(run.directory/'evaluation.json',evaluation)
            result={'index':index,'evaluation':evaluation}
            status='partial' if any(f['status']=='error' for f in fields) else 'complete'
        if job['request'].get('mode')=='index_only':
            status='complete'
        db.update_job(job_id,result=result)
    except Cancelled as exc:
        status='cancelled';db.update_job(job_id,error=str(exc))
    except BaseException as exc:
        import traceback
        traceback.print_exc()
        db.update_job(job_id,error=f'{type(exc).__name__}: {str(exc)[:1500]}')
    finally:
        if pipeline:
            pipeline.close()
        manifest=read_json(run.directory/'run.json')
        if manifest.get('provenance',{}).get('implementation_archive'):
            final_hash=implementation_snapshot()[1]
            manifest['provenance'].update(implementation_end_hash=final_hash,
                                          implementation_changed_during_run=final_hash!=manifest['provenance']['implementation_hash'])
            write_json(run.directory/'run.json',manifest)
        run.finish(status=status,corpus_id=job['corpus_id'],configuration_id=job['config_id'])
        db.update_job(job_id,status=status,ended_at=db.now())
        metrics=measure(db.get_job(job_id))
        for stage in metrics['stages']:
            if stage['name'] in ('retrieval','generation','verification','evaluation'):
                db.stage(job_id,stage['name'],status=stage['status'],duration_ms=stage['duration_ms'],
                         started_at=stage.get('started_at'),ended_at=stage.get('ended_at'))
        write_json(run.directory/'workbench-metrics.json',metrics)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('job_id')
    execute(parser.parse_args().job_id)
