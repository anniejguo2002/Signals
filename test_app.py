"""Synthetic transport fixtures are test-only; the application has no mock mode."""
import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.main import make_app
from backend.models import Company, Finding, ResearchRequest, decode_result
from backend.research import Researcher, check_public_dns, now
from backend.store import Store
from backend.tinyfish import ResearchError, TinyFish, sse_events


def company(name='Test Company'):
    return {'name': name, 'website': 'https://example.com/', 'products': {'text': 'Test-only product fixture.', 'sources': ['https://example.com/products']}}


def report():
    return {'id': 'test-report', 'url': 'https://example.com/', 'competitor_limit': 3, 'status': 'queued', 'phase': 'discovery', 'created_at': now(), 'finished_at': None, 'completed_steps': 0, 'total_steps': 4, 'companies': [], 'candidates': [], 'events': [], 'errors': [], 'runs': [], 'provenance': 'test_fixture'}


@pytest.mark.parametrize('url', ['http://127.0.0.1/', 'https://10.0.0.1', 'https://localhost', 'file:///etc/passwd', 'javascript:alert(1)', 'https://user:pass@example.com', 'https://example.com:9999', 'http://[::1]', 'https://foo.local', 'https://foo.internal'])
def test_reject_private_and_unsafe_urls(url):
    with pytest.raises(ValidationError):
        ResearchRequest(url=url)


def test_normalization_and_bounds():
    assert ResearchRequest(url='plausible.io').url == 'https://plausible.io/'
    for count in (0, 4):
        with pytest.raises(ValidationError):
            ResearchRequest(url='plausible.io', competitor_limit=count)


def test_facts_without_evidence_are_removed():
    assert Finding(text='A made-up price', sources=[]).text is None
    with pytest.raises(ValidationError):
        Company(name='Empty company', website='https://example.com')
    with pytest.raises(ValidationError):
        Finding(text='Unsafe source', sources=['javascript:alert(1)'])


def test_documented_result_wrappers():
    value = company()
    assert decode_result({'result': json.dumps(value)}) == value
    assert decode_result('```json\n' + json.dumps(value) + '\n```') == value
    with pytest.raises(ValueError):
        decode_result('not JSON')


def test_sse_multiline_comments_and_eof():
    async def run():
        async def lines():
            for line in [': heartbeat', 'event: update', 'data: {"type":', 'data: "STARTED"}', '', 'data: {"type":"COMPLETE"}']:
                yield line
        return [e async for e in sse_events(lines())]
    assert asyncio.run(run()) == [{'type': 'STARTED'}, {'type': 'COMPLETE'}]


def test_live_adapter_auth_payload_and_success():
    requests = []
    async def handler(request):
        requests.append(request)
        return httpx.Response(200, text='data: {"type":"STARTED","run_id":"run-test"}\n\ndata: ' + json.dumps({'type': 'COMPLETE', 'status': 'COMPLETED', 'result': company()}) + '\n\n')
    async def run():
        events = []
        async def receive(e):
            events.append(e)
        result, run_id = await TinyFish('test-secret', transport=httpx.MockTransport(handler)).run('https://example.com', 'Test goal', receive)
        assert result == company() and run_id == 'run-test'
        assert events[0]['type'] == 'STARTED'
    asyncio.run(run())
    assert requests[0].headers['X-API-Key'] == 'test-secret'
    assert str(requests[0].url) == 'https://agent.tinyfish.ai/v1/automation/run-sse'
    assert 'output_schema' not in json.loads(requests[0].content)


@pytest.mark.parametrize('status', [401, 402, 403, 429, 500])
def test_api_failures_are_actionable_and_never_leak_provider_body(status):
    async def run():
        async def receive(e):
            pass
        client = TinyFish('secret', transport=httpx.MockTransport(lambda request: httpx.Response(status, text='secret raw body')))
        with pytest.raises(ResearchError) as error:
            await client.run('https://example.com', 'goal', receive)
        assert 'secret' not in str(error.value)
    asyncio.run(run())


def test_disconnect_recovers_same_run_without_starting_twice(monkeypatch):
    calls = []
    async def no_wait(_):
        pass
    monkeypatch.setattr('backend.tinyfish.asyncio.sleep', no_wait)
    async def handler(request):
        calls.append(request)
        if request.method == 'POST':
            return httpx.Response(200, text='data: {"type":"STARTED","run_id":"recovered-run"}\n\n')
        return httpx.Response(200, json={'status': 'COMPLETED', 'result': company()})
    async def run():
        async def receive(e):
            pass
        result, run_id = await TinyFish('test', transport=httpx.MockTransport(handler)).run('https://example.com', 'goal', receive)
        assert run_id == 'recovered-run' and result == company()
    asyncio.run(run())
    assert [request.method for request in calls] == ['POST', 'GET']


def test_partial_research_preserves_good_data_and_deduplicates(tmp_path, monkeypatch):
    async def allow(_):
        pass
    monkeypatch.setattr('backend.research.check_public_dns', allow)
    class Client:
        async def run(self, url, goal, callback):
            if url == 'https://example.com/':
                candidate = {'name': 'Alternative', 'website': 'https://alternative.org', 'reason': {'text': 'Test-only reason', 'sources': ['https://example.com/compare']}}
                return {'company': company(), 'competitors': [candidate, candidate]}, 'target-run'
            raise ResearchError('Site blocked')
    store = Store(str(tmp_path / 'test.db'))
    data = report()
    asyncio.run(Researcher(store, Client()).execute(data))
    saved = store.get(data['id'])
    assert saved['status'] == 'partial'
    assert len(saved['companies']) == 1 and len(saved['candidates']) == 1
    assert saved['candidates'][0]['status'] == 'failed'
    assert saved['errors'][0]['message'] == 'Site blocked'


def test_missing_key_history_export_and_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr('backend.main.api_key', lambda: '')
    app = make_app(str(tmp_path / 'test.db'))
    with TestClient(app) as client:
        assert client.get('/api/health').json()['configured'] is False
        response = client.post('/api/research', json={'url': 'https://example.com'})
        assert response.status_code == 503 and 'TINYFISH_API_KEY' in response.json()['detail']
        assert client.get('/api/research').json() == []
        assert client.get('/api/research/missing').status_code == 404
        saved = report()
        app.state.store.save(saved)
        assert client.get('/api/research').json()[0]['id'] == saved['id']
        response = client.get('/api/research/test-report/export')
        assert 'attachment' in response.headers['content-disposition']
        assert response.json()['provenance'] == 'test_fixture'


def test_restart_marks_abandoned_runs_failed(tmp_path):
    app = make_app(str(tmp_path / 'test.db'))
    app.state.store.save(report())
    with TestClient(app) as client:
        saved = client.get('/api/research/test-report').json()
        assert saved['status'] == 'failed'
        assert 'restarted' in saved['errors'][0]['message']


def test_dns_private_resolution_is_rejected(monkeypatch):
    async def run():
        async def fake_dns(*args, **kwargs):
            return [(2, 1, 6, '', ('127.0.0.1', 0))]
        monkeypatch.setattr(asyncio.get_running_loop(), 'getaddrinfo', fake_dns)
        with pytest.raises(ResearchError, match='private'):
            await check_public_dns('https://public-looking.com')
    asyncio.run(run())


def test_full_pipeline_caps_candidates_and_concurrency(tmp_path, monkeypatch):
    async def allow(_):
        pass
    monkeypatch.setattr('backend.research.check_public_dns', allow)
    class Client:
        active = 0
        peak = 0
        async def run(self, url, goal, callback):
            if url == 'https://example.com/':
                return {'company': company(), 'competitors': [
                    {'name': f'Alternative {i}', 'website': f'https://alternative{i}.org', 'reason': {'text': 'Test comparison', 'sources': ['https://example.com/compare']}}
                    for i in range(5)
                ]}, 'target'
            self.active += 1
            self.peak = max(self.active, self.peak)
            await asyncio.sleep(0.005)
            self.active -= 1
            return {**company(url), 'website': url}, url
    store = Store(str(tmp_path / 'test.db'))
    data, client = report(), Client()
    asyncio.run(Researcher(store, client).execute(data))
    assert data['status'] == 'completed'
    assert len(data['candidates']) == 3 and len(data['companies']) == 4
    assert data['completed_steps'] == data['total_steps'] == 4
    assert client.peak == 2


def test_timeout_attempts_provider_cancellation():
    requests = []
    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"type":"STARTED","run_id":"slow-run"}\n\n'
            await asyncio.sleep(10)
    async def handler(request):
        requests.append(str(request.url))
        if str(request.url).endswith('/cancel'):
            return httpx.Response(200, json={'status': 'CANCELLED'})
        return httpx.Response(200, stream=SlowStream())
    async def run():
        async def receive(event):
            pass
        with pytest.raises(ResearchError, match='exceeded'):
            await TinyFish('test', timeout=0.01, transport=httpx.MockTransport(handler)).run('https://example.com', 'goal', receive)
    asyncio.run(run())
    assert requests[-1].endswith('/runs/slow-run/cancel')
