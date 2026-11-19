"""Audit selected real runs without launching models or altering experiments."""
import argparse
from datetime import datetime, timezone
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from poc.common import ROOT, config, read_json, write_json
from poc.indexing import normalize
from poc.storage import Storage
from workbench import database as db
from workbench.service import detail
from workbench.reporting import report


def verify(ids,interrupted=None,retry=None):
    checks=[]
    def check(condition,message):
        if not condition:raise AssertionError(message)
        checks.append(message)
    results=[detail(identity,True) for identity in ids]
    with_storage=Storage(config())
    try:
        for run in results:
            identity=run['id'];metrics=run['metrics'];index=run['result']['index'] if run['result'] else None
            check(run['status']=='complete',f'{identity}: completed without pipeline failure')
            check(index and index['pages']==run['request']['source']['pages'] and run['request']['recipe']['pages']=='',f'{identity}: whole PDF processed')
            check(with_storage.index_is_complete(index),f'{identity}: selected OpenSearch and Neo4j versions complete')
            response=with_storage.http.post('/'+index['index_name']+'/_search',json={'size':1}).raise_for_status().json()
            check(all('text' not in hit['_source'] and 'vector' not in hit['_source'] for hit in response['hits']['hits']),f'{identity}: text and vectors excluded from stored source')
            stages=metrics['stages'];durations=[s['duration_ms'] for s in stages if s.get('duration_ms') is not None]
            check(len(stages)==13 and all(value>=0 for value in durations),f'{identity}: all thirteen stages explicitly represented')
            check(sum(durations)<=metrics['wall_seconds']*1000*1.01,f'{identity}: stage time does not double count nested spans')
            check(all(s['duration_ms'] is None for s in stages if s['status'] in ('skipped','not_executed')),f'{identity}: unexecuted stages are not zero measurements')
            check(metrics['model_calls']==sum(bool(e.get('billable')) for e in run['events']),f'{identity}: billable operations reconciled')
            check(metrics['mcp_calls']==sum(e['stage']=='mcp' for e in run['events']),f'{identity}: MCP count reconciled')
            check(metrics['api_cost']==0 and metrics['total_cost'] is None,f'{identity}: local API zero, unpriced hardware unknown')
            check({f['id'] for f in run['fields']}==set(run['request']['field_ids']),f'{identity}: every requested field has a result')
            directory=ROOT/index['directory'];document=read_json(directory/'document.json');chunks={c['id']:c for c in document['chunks']}
            relations=read_json(directory/'relations.json')
            check(all(f['chunk_id'] in chunks and normalize(f['quote']) in normalize(chunks[f['chunk_id']]['text']) for section in relations for f in section['facts']),f'{identity}: graph quotations belong to this document version')
            check(all(e['chunk_id'] in chunks for f in run['fields'] for e in f['evidence']),f'{identity}: answer citations belong to this index')
            run.pop('events')  # Full append-only events remain in runs/<id>; export concise evidence.
        for corpus in {r['corpus_id'] for r in results}:
            selected=[r for r in results if r['corpus_id']==corpus]
            check(len({r['request']['input_hash'] for r in selected})==1,f'{corpus}: variants use identical frozen inputs')
            check(len({r['result']['index']['index_name'] for r in selected})==1 and len({r['result']['index']['graph_name'] for r in selected})==1,f'{corpus}: query/prompt changes reuse compatible index and graph')
        recovery=None
        if interrupted and retry:
            original=db.get_job(interrupted);repeated=db.get_job(retry)
            check(original['status']=='interrupted', 'Abrupt termination is recorded as interrupted')
            check(repeated['status']=='complete' and repeated['retry_of']==original['id'] and repeated['request']==original['request'],'Retry completes with frozen inputs unchanged')
            reused=[(r['id'],s['detail'].get('reused_sections',0)) for r in results for s in r['stages'] if s['name']=='relations' and s['detail'].get('reused_sections')]
            check(any(number>=57 for _,number in reused),'Completed relation packages from the interrupted run were reused')
            recovery={'status':'passed','original':original['id'],'retry':repeated['id'],
                      'frozen_inputs_preserved':True,'checkpoint_reuse':reused,
                      'note':'The forced terminal shutdown killed its process tree. Recovery detected the dead worker, reused completed packages in another compatible run, and completed the retry without overwriting the original.'}
            write_json(ROOT/'reports/validation/workbench-restart.json',recovery)
        result={'status':'passed','checked_at':datetime.now(timezone.utc).isoformat(),'checks':checks,'runs':results,'recovery':recovery,
                'scope':'Development validation: two complete PDFs, three fields each, top_k and answer-prompt variants. One repetition per setting; provisional references. This is not a held-out quality benchmark or a cold-start latency comparison.'}
        write_json(ROOT/'reports/validation/workbench-real.json',result)
        for run in results:
            name=f"workbench-run-{run['corpus_id']}-{'prompt' if 'Experimento de prompt' in run['request']['recipe']['name'] else 'k'+str(run['request']['recipe']['top_k'])}.html"
            (ROOT/'reports/validation'/name).write_text(report(run),encoding='utf-8')
        return {'status':'passed','checks':len(checks),'runs':len(results)}
    finally:with_storage.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--runs',nargs='+',required=True)
    parser.add_argument('--interrupted');parser.add_argument('--retry')
    arguments=parser.parse_args()
    print(verify(arguments.runs,arguments.interrupted,arguments.retry))
