"""Append-only spans with separate wall-clock and billable-operation accounting."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import uuid

from .common import ROOT, config, read_json, write_json

PARENT = ContextVar("parent_span", default=None)


class Run:
    def __init__(self, run_id=None, kind="execution", settings=None):
        self.run_id = run_id or f"{kind}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
        self.directory = ROOT / "runs" / self.run_id
        self.directory.mkdir(parents=True, exist_ok=True)
        manifest_path = self.directory / 'run.json'
        self.settings = settings or (read_json(manifest_path)['config'] if run_id and manifest_path.exists() else config())
        self.events_path = self.directory / f"events-{os.getpid()}.jsonl"
        self.start = time.perf_counter()
        self.kind = kind
        if not manifest_path.exists():
            write_json(self.directory / "run.json", {
                "run_id": self.run_id, "kind": kind, "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(), "config": self.settings})

    @contextmanager
    def span(self, stage, operation, **details):
        check = getattr(self, 'check_cancelled', None)
        if check:
            check()
        event = {"run_id": self.run_id, "span_id": uuid.uuid4().hex,
                 "parent_span_id": PARENT.get(), "stage": stage, "operation": operation,
                 "started_at": datetime.now(timezone.utc).isoformat(), "status": "ok", **details}
        token = PARENT.set(event["span_id"])
        start = time.perf_counter()
        try:
            yield event
        except BaseException as exc:
            event.update(status="error", error_type=type(exc).__name__, error=str(exc)[:600])
            raise
        finally:
            event["duration_ms"] = (time.perf_counter() - start) * 1000
            event["ended_at"] = datetime.now(timezone.utc).isoformat()
            PARENT.reset(token)
            with self.events_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")

    def finish(self, status="complete", **details):
        manifest = read_json(self.directory / "run.json")
        manifest.update(status=status, wall_seconds=time.perf_counter()-self.start, **details)
        write_json(self.directory / "run.json", manifest)
        summary = summarize(self.directory)
        write_json(self.directory / "metrics.json", summary)
        return summary


def summarize(directory):
    directory = Path(directory)
    manifest = read_json(directory / "run.json")
    events = []
    for path in directory.glob("events-*.jsonl"):
        events.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    stages = {}
    for event in events:
        stage = stages.setdefault(event["stage"], {"calls": 0, "inclusive_ms": 0, "errors": 0})
        stage["calls"] += 1
        stage["inclusive_ms"] += event["duration_ms"]
        stage["errors"] += event["status"] == "error"
    usage = [event for event in events if event.get("billable")]
    rate = manifest["config"].get("machine_hour_rate")
    return {"run_id": manifest["run_id"], "status": manifest["status"],
            "wall_seconds": manifest.get("wall_seconds"), "stages": stages,
            "model_calls": len(usage), "cache_hits": sum(bool(e.get("cache_hit")) for e in events),
            "input_tokens": sum(e.get("input_tokens") or 0 for e in usage),
            "output_tokens": sum(e.get("output_tokens") or 0 for e in usage),
            "usage_unknown_calls": sum(e.get("input_tokens") is None for e in usage),
            "mcp_calls": sum(e["stage"] == "mcp" for e in events),
            "agent_rounds": sum(e["stage"] == "round" for e in events),
            "api_cost": sum(e.get("api_cost", 0) for e in usage),
            "currency": manifest["config"]["currency"],
            "machine_cost_estimate": None if rate is None else rate * manifest.get("wall_seconds", 0) / 3600,
            "machine_hour_rate": rate, "errors": sum(e["status"] == "error" for e in events)}
