"""Audit complete real runs, their source citations, budgets and exported results."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import zipfile

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def normalize(text):
    return ' '.join(text.split())


def verify(name='full'):
    benchmark = read(ROOT/'runs'/f'benchmark-{name}'/'benchmark.json')
    assert all(job.get('status') == 'complete' for job in benchmark['jobs']), 'Incomplete benchmark'
    assert len(benchmark['jobs']) == 2 * len(benchmark['variants']) * benchmark['repetitions']
    report = read(ROOT/'reports'/name/'measurements.json')
    assert {row['run_id'] for row in report['executions']} == {job['run_id'] for job in benchmark['jobs']}
    documents = {}
    forms = {}
    for corpus, fingerprint in benchmark['frozen_inputs']['indexes'].items():
        index = read(ROOT/'data/indexes'/f'{corpus}.json')
        assert index['fingerprint'] == fingerprint
        document = read(ROOT/index['directory']/'document.json')
        source = ROOT/'data/raw'/document['source']['filename']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == index['source_hash']
        assert len(document['pages']) == index['pages']
        documents[corpus] = {chunk['id']: chunk for chunk in document['chunks']}
        forms[corpus] = {field['id']: field for field in read(ROOT/'forms'/f'{corpus}.json')['fields']}
    with zipfile.ZipFile(ROOT/'reports'/name/'frozen-inputs.zip') as archive:
        for path, expected in benchmark['frozen_inputs'].items():
            if path != 'indexes':
                assert hashlib.sha256(archive.read(path)).hexdigest() == expected, path

    counters = Counter()
    statuses = Counter()
    for job in benchmark['jobs']:
        directory = ROOT/'runs'/job['run_id']
        fields = read(directory/'fields.json')
        result = read(directory/'result.json')
        metrics = read(directory/'metrics.json')
        expected_fields = forms[job['corpus']]
        if benchmark.get('field_ids'):
            expected_fields = {key: value for key, value in expected_fields.items() if key in benchmark['field_ids']}
        assert len(fields) == len(expected_fields)
        assert {field['id'] for field in fields} == set(expected_fields)
        assert len({field['id'] for field in fields}) == len(fields)
        output_name = f"{job['corpus']}-{job['variant']}-r{job['repetition']+1}"
        assert read(ROOT/'reports'/name/'outputs'/f'{output_name}.json') == result
        counters['forms'] += 1
        for field in fields:
            counters['fields'] += 1
            statuses[field['status']] += 1
            schema = expected_fields[field['id']]['value_schema']
            Draft202012Validator({'anyOf': [schema, {'type': 'null'}]}).validate(field['value'])
            current = result
            for key in field['path'].strip('/').split('/'):
                current = current[key]
            assert current == field['value']
            limit = benchmark['config']['max_rounds_per_field'] if job['variant'] == 'F' else 1
            assert len(field['rounds']) <= limit
            if field['status'] != 'filled':
                assert field['value'] is None
                continue
            Draft202012Validator(schema).validate(field['value'])
            assert field['evidence'], f'Missing citation: {field["id"]}'
            assert field['rounds'][-1]['support_check']['supported'] is True
            supplied = {cid for step in field['rounds'] for cid in step['retrieved_ids']}
            for citation in field['evidence']:
                assert citation['chunk_id'] in supplied
                chunk = documents[job['corpus']][citation['chunk_id']]
                assert citation['page'] == chunk['page']
                assert len(normalize(citation['quote'])) >= 10
                assert normalize(citation['quote']) in normalize(chunk['text'])
                counters['filled_citations_checked'] += 1
        events = []
        for path in directory.glob('events-*.jsonl'):
            events.extend(json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line)
        ids = {event['span_id'] for event in events}
        assert len(ids) == len(events), 'Duplicate telemetry span'
        assert all(not event.get('parent_span_id') or event['parent_span_id'] in ids for event in events)
        assert sum(event['stage'] == 'mcp' for event in events) == metrics['mcp_calls']
        assert sum(event['stage'] == 'round' for event in events) == metrics['agent_rounds']
        assert sum(bool(event.get('billable')) for event in events) == metrics['model_calls']
        assert sum(event.get('api_cost', 0) for event in events if event.get('billable')) == metrics['api_cost']
        assert metrics['api_cost'] == 0
        counters['events_checked'] += len(events)
        counters['mcp_calls'] += metrics['mcp_calls']
        counters['agent_rounds'] += metrics['agent_rounds']
        counters['model_calls'] += metrics['model_calls']
    summary = {'status': 'passed', 'benchmark': name, 'checks': dict(counters),
               'field_statuses': dict(statuses),
               'scope': 'schema, provenance, scope, budget, telemetry and export consistency; not semantic accuracy'}
    destination = ROOT/'reports'/name/'end-to-end.json'
    destination.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default='full')
    print(json.dumps(verify(parser.parse_args().name), ensure_ascii=False))
