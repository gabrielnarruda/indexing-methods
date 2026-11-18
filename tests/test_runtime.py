import httpx
import asyncio
import pytest

from poc.common import ROOT, config, read_json
from poc.models import Models
from poc.storage import Storage
from poc.telemetry import Run


def fake_model(tmp_path, monkeypatch, handler):
    import poc.models as models
    import poc.telemetry as telemetry
    monkeypatch.setattr(models, 'ROOT', tmp_path)
    monkeypatch.setattr(telemetry, 'ROOT', tmp_path)
    monkeypatch.setattr(models.time, 'sleep', lambda _: None)
    run = Run(kind='model-contract', settings=config())
    model = Models.__new__(Models)
    model.run, model.settings = run, run.settings
    model.url = 'http://model.test'
    model.digests = {'test': 'fixed-digest'}
    model.client = httpx.Client(transport=httpx.MockTransport(handler))
    return model, run


def test_model_timeout_retries_and_accounts_unknown_usage(tmp_path, monkeypatch):
    attempts = []

    def handler(request):
        attempts.append(request)
        if len(attempts) == 1:
            raise httpx.ReadTimeout('simulated timeout', request=request)
        return httpx.Response(200, json={'prompt_eval_count': 10, 'eval_count': 3})

    model, run = fake_model(tmp_path, monkeypatch, handler)
    model.request('/api/chat', {'model': 'test'}, 'generation', cache=False)
    metrics = run.finish()
    assert len(attempts) == 2
    assert metrics['model_calls'] == 2
    assert metrics['errors'] == 1
    assert metrics['usage_unknown_calls'] == 1
    assert metrics['input_tokens'] == 10


def test_truncated_output_is_rejected_and_usage_preserved(tmp_path, monkeypatch):
    model, run = fake_model(tmp_path, monkeypatch, lambda request: httpx.Response(
        200, json={'done_reason': 'length', 'prompt_eval_count': 10, 'eval_count': 20}))
    with pytest.raises(ValueError, match='token budget'):
        model.request('/api/chat', {'model': 'test'}, 'generation', cache=False)
    metrics = run.finish()
    assert metrics['output_tokens'] == 20
    assert metrics['errors'] == 1


def test_cache_avoids_second_model_call(tmp_path, monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={'prompt_eval_count': 7, 'eval_count': 0})

    model, run = fake_model(tmp_path, monkeypatch, handler)
    first = model.request('/api/embed', {'model': 'test', 'input': ['text']}, 'embedding')
    second = model.request('/api/embed', {'model': 'test', 'input': ['text']}, 'embedding')
    metrics = run.finish()
    assert first == second
    assert len(requests) == 1
    assert metrics['model_calls'] == 1 and metrics['cache_hits'] == 1


def test_model_initialization_failure_finishes_run(tmp_path, monkeypatch):
    import poc.extraction as extraction
    import poc.telemetry as telemetry
    monkeypatch.setattr(telemetry, 'ROOT', tmp_path)

    class UnavailableModel:
        def __init__(self, run):
            raise httpx.ConnectError('simulated unavailable local model server')

    monkeypatch.setattr(extraction, 'Models', UnavailableModel)
    with pytest.raises(httpx.ConnectError):
        asyncio.run(extraction.extract_form('adpf54'))
    directory=next((tmp_path/'runs').iterdir())
    assert read_json(directory/'run.json')['status']=='failed'
    metrics=read_json(directory/'metrics.json')
    assert metrics['errors']==1 and metrics['model_calls']==0


@pytest.mark.parametrize('selection', [[], ['missing-field']])
def test_invalid_field_selection_fails_before_model(tmp_path, monkeypatch, selection):
    import poc.extraction as extraction
    import poc.telemetry as telemetry
    monkeypatch.setattr(telemetry, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='Field selection'):
        asyncio.run(extraction.extract_form('adpf54',field_ids=selection))
    directory=next((tmp_path/'runs').iterdir())
    assert read_json(directory/'run.json')['status']=='failed'
    assert read_json(directory/'metrics.json')['model_calls']==0


@pytest.mark.integration
@pytest.mark.parametrize('corpus', ['adpf54', 'dom-casmurro'])
def test_published_index_and_graph_are_complete(corpus):
    path = ROOT/'data/indexes'/f'{corpus}.json'
    if not path.exists():
        pytest.skip('Published corpus required')
    storage = Storage(config())
    try:
        manifest = read_json(path)
        assert storage.index_is_complete(manifest)
        assert not storage.index_is_complete({**manifest, 'facts': manifest['facts']+1})
    finally:
        storage.close()
