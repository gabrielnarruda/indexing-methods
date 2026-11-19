"""One active worker, durable queue, process-identity checks before recovery."""
import os
import subprocess
import sys
import threading
import time

import psutil

from poc.common import ROOT
from . import database as db

def process_alive(job):
    if not job['pid'] or not job['process_created']:
        return False
    try:
        process=psutil.Process(job['pid'])
        return abs(process.create_time()-job['process_created'])<.01 and process.is_running() and process.status()!=psutil.STATUS_ZOMBIE
    except psutil.AccessDenied:
        return None  # Unknown is not evidence that a worker died.
    except psutil.NoSuchProcess:
        return False

class Coordinator:
    def __init__(self):
        self.stop_event=threading.Event()
        self.thread=threading.Thread(target=self.loop,daemon=True,name='workbench-coordinator')
        self.children={}

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set();self.thread.join(timeout=2)
        # Detached workers deliberately survive an API/browser restart.

    def tick(self):
        for key,process in list(self.children.items()):
            if process.poll() is not None:
                self.children.pop(key)
        with db.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            active=[dict(row) for row in connection.execute("SELECT * FROM jobs WHERE status IN ('starting','running')")]
            for job in active:
                if process_alive(job) is not False:
                    return
                if job['status']=='starting' and job['id'] in self.children and self.children[job['id']].poll() is None:
                    return
                # Do not reclaim a just-reserved row during another coordinator's launch window.
                from .metrics import elapsed
                if job['status']=='starting' and elapsed(job['started_at'],db.now())<15000:
                    return
                connection.execute("UPDATE jobs SET status='interrupted',ended_at=?,error=? WHERE id=?",
                    (db.now(),'O processo responsável terminou sem publicar conclusão. Retome criando uma nova run; os artefatos completos serão reaproveitados.',job['id']))
            row=connection.execute("SELECT id FROM jobs WHERE status='queued' AND cancel_requested=0 ORDER BY created_at LIMIT 1").fetchone()
            if not row:return
            job_id=row['id']
            connection.execute("UPDATE jobs SET status='starting',started_at=? WHERE id=?",(db.now(),job_id))
        logdir=db.DATA/'logs';logdir.mkdir(parents=True,exist_ok=True)
        try:
            with (logdir/(job_id+'.log')).open('ab') as log:
                process=subprocess.Popen([sys.executable,'-m','workbench.worker',job_id],cwd=ROOT,
                    env={**os.environ,'INDEXING_WORKBENCH_DATA':str(db.DATA),'PYTHONIOENCODING':'utf-8'},
                    stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,
                    start_new_session=os.name!='nt')
            self.children[job_id]=process
            with db.connect() as connection:
                connection.execute("UPDATE jobs SET pid=?,process_created=? WHERE id=? AND status='starting'",
                                   (process.pid,psutil.Process(process.pid).create_time(),job_id))
        except Exception as exc:
            db.update_job(job_id,status='failed',ended_at=db.now(),error=f'Falha ao iniciar worker: {exc}')

    def loop(self):
        while not self.stop_event.is_set():
            try:self.tick()
            except Exception:
                import logging
                logging.exception('Coordinator tick failed')
            self.stop_event.wait(.5)
