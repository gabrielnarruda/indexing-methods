"""SQLite is the source of truth for the durable, single-user queue."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import uuid

from poc.common import ROOT, digest

DATA = Path(os.environ.get('INDEXING_WORKBENCH_DATA', ROOT/'data/workbench')).resolve()

def now():
    return datetime.now(timezone.utc).isoformat()

@contextmanager
def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA/'workbench.sqlite3', timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        yield db
        db.commit()
    finally:
        db.close()

def initialize():
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS configurations (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, revision INTEGER NOT NULL,
          parent_id TEXT, hash TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, config_id TEXT NOT NULL,
          corpus_id TEXT NOT NULL, repetition INTEGER NOT NULL, status TEXT NOT NULL,
          request TEXT NOT NULL, created_at TEXT NOT NULL, started_at TEXT, ended_at TEXT,
          pid INTEGER, process_created REAL, cancel_requested INTEGER DEFAULT 0,
          error TEXT, result TEXT, retry_of TEXT,
          FOREIGN KEY(config_id) REFERENCES configurations(id));
        CREATE TABLE IF NOT EXISTS stages (
          job_id TEXT NOT NULL, name TEXT NOT NULL, status TEXT NOT NULL,
          started_at TEXT, ended_at TEXT, duration_ms REAL, history_ms REAL,
          artifact_key TEXT, source_run TEXT, detail TEXT,
          PRIMARY KEY(job_id,name), FOREIGN KEY(job_id) REFERENCES jobs(id));
        CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status,created_at);
        CREATE TABLE IF NOT EXISTS datasets (
          id TEXT PRIMARY KEY, corpus_id TEXT NOT NULL, revision INTEGER NOT NULL,
          body TEXT NOT NULL, created_at TEXT NOT NULL);
        ''')

def configuration(body, parent_id=None):
    from .configuration import Recipe
    body = Recipe.model_validate(body).model_dump()
    with connect() as db:
        parent = db.execute('SELECT revision FROM configurations WHERE id=?', (parent_id,)).fetchone() if parent_id else None
        if parent_id and not parent:
            raise ValueError('Configuração de origem não encontrada.')
        item = {'id':uuid.uuid4().hex, 'name':body['name'], 'revision':parent['revision']+1 if parent else 1,
                'parent_id':parent_id, 'hash':digest(json.dumps(body,sort_keys=True).encode()),
                'body':json.dumps(body,ensure_ascii=False), 'created_at':now()}
        db.execute('INSERT INTO configurations VALUES (:id,:name,:revision,:parent_id,:hash,:body,:created_at)',item)
    item['body'] = body
    return item

def configs():
    with connect() as db:
        rows = [dict(r) for r in db.execute('SELECT * FROM configurations ORDER BY created_at DESC')]
    for row in rows:
        row['body'] = json.loads(row['body'])
    return rows

def get_config(config_id):
    with connect() as db:
        row = db.execute('SELECT * FROM configurations WHERE id=?',(config_id,)).fetchone()
    if not row:
        raise KeyError('Configuração não encontrada')
    result = dict(row)
    result['body'] = json.loads(result['body'])
    return result

def get_job(job_id):
    with connect() as db:
        row = db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        stages = [dict(r) for r in db.execute('SELECT * FROM stages WHERE job_id=? ORDER BY started_at,name',(job_id,))]
    if not row:
        raise KeyError('Execução não encontrada')
    result = dict(row)
    for key in ['request','result']:
        result[key] = json.loads(result[key]) if result[key] else None
    for stage in stages:
        stage['detail'] = json.loads(stage['detail']) if stage['detail'] else {}
    result['stages'] = stages
    return result

def update_job(job_id, **values):
    allowed = {'status','started_at','ended_at','pid','process_created','cancel_requested','error','result'}
    if not values.keys() <= allowed:
        raise ValueError('Invalid job update')
    if 'result' in values:
        values['result'] = json.dumps(values['result'],ensure_ascii=False)
    with connect() as db:
        db.execute('UPDATE jobs SET '+','.join(key+'=?' for key in values)+' WHERE id=?',(*values.values(),job_id))

def stage(job_id, name, **values):
    allowed = {'status','started_at','ended_at','duration_ms','history_ms','artifact_key','source_run','detail'}
    if not values.keys() <= allowed:
        raise ValueError('Invalid stage update')
    if 'detail' in values:
        values['detail'] = json.dumps(values['detail'],ensure_ascii=False)
    with connect() as db:
        db.execute('INSERT OR IGNORE INTO stages(job_id,name,status) VALUES (?,?,?)',(job_id,name,'pending'))
        db.execute('UPDATE stages SET '+','.join(k+'=?' for k in values)+' WHERE job_id=? AND name=?',(*values.values(),job_id,name))

def enqueue(config_id, corpus_id, repetition, request, batch_id=None, retry_of=None):
    item = {'id':'wb-'+uuid.uuid4().hex, 'batch_id':batch_id or uuid.uuid4().hex,
            'config_id':config_id,'corpus_id':corpus_id,'repetition':repetition,
            'status':'queued','request':json.dumps(request,ensure_ascii=False), 'created_at':now(),'retry_of':retry_of}
    with connect() as db:
        db.execute('INSERT INTO jobs(id,batch_id,config_id,corpus_id,repetition,status,request,created_at,retry_of) VALUES (:id,:batch_id,:config_id,:corpus_id,:repetition,:status,:request,:created_at,:retry_of)',item)
    return get_job(item['id'])

def dataset_version(corpus_id, body):
    with connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        revision=connection.execute('SELECT COALESCE(MAX(revision),0)+1 AS version FROM datasets WHERE corpus_id=?',(corpus_id,)).fetchone()['version']
        identity=uuid.uuid4().hex
        connection.execute('INSERT INTO datasets VALUES (?,?,?,?,?)',(identity,corpus_id,revision,json.dumps(body,ensure_ascii=False),now()))
    return {'id':identity,'revision':revision,**body}

def dataset_versions(corpus_id):
    with connect() as connection:
        rows=connection.execute('SELECT * FROM datasets WHERE corpus_id=? ORDER BY revision DESC',(corpus_id,)).fetchall()
    return [{'id':row['id'],'revision':row['revision'],'created_at':row['created_at'],**json.loads(row['body'])} for row in rows]
