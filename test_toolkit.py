import asyncio
import httpx
import pytest
from backend.toolkit import Toolkit
from backend.tinyfish import ResearchError
from backend.research import Researcher


def test_search_contract_and_bad_links():
    def handler(request):
        assert request.headers['X-API-Key'] == 'test-key'
        assert request.url.host == 'api.search.tinyfish.ai'
        assert request.url.params['query'] == 'example.com alternatives competitors'
        return httpx.Response(200, json={'results': [{'url': 'javascript:alert(1)'}, {'url':'https://other.com', 'title':'A lead', 'snippet':'Not verified'}]})
    data = asyncio.run(Toolkit('test-key', httpx.MockTransport(handler)).search('https://example.com/private?secret=never-send'))
    assert len(data['results']) == 1
    assert 'secret' not in data['query']


def test_fetch_requires_readable_text_and_disables_cache():
    def handler(request):
        import json
        body = json.loads(request.content)
        assert body['ttl'] == 0
        assert body['format'] == 'markdown'
        return httpx.Response(200, json={'results': [], 'errors':[{'message':'blocked'}]})
    with pytest.raises(ResearchError, match='no readable page'):
        asyncio.run(Toolkit('test', httpx.MockTransport(handler)).fetch('https://example.com'))


def test_provider_errors_do_not_expose_body():
    transport = httpx.MockTransport(lambda request: httpx.Response(403, text='secret-provider-body'))
    with pytest.raises(ResearchError, match='HTTP 403') as error:
        asyncio.run(Toolkit('test', transport).search('https://example.com'))
    assert 'secret-provider-body' not in str(error.value)


def test_portal_skips_all_public_tools():
    class Store:
        def save(self, report): pass
    class ForbiddenTools:
        def __getattr__(self, name): raise AssertionError('Portal must not call public tools')
    report = {}
    result = asyncio.run(Researcher(Store(), None, ForbiddenTools()).prepare(report, 'https://example.com/private', True))
    assert result == ''
    assert len(report['tools']) == 3
    assert all(t['status'] == 'skipped' for t in report['tools'])


def test_preparation_retains_real_outputs_and_continues_after_failure(tmp_path):
    class Store:
        def save(self, report): pass
    class Tools:
        async def search(self, url): return {'results':[{'url':'https://example.org', 'title':'Lead'}]}
        async def fetch(self, url): raise ResearchError('Fetch is unavailable')
        async def preview(self, url, path): return {'url':url,'title':'Rendered title'}
    report = {'id':'test-report','events':[]}
    context = asyncio.run(Researcher(Store(), None, Tools(), tmp_path).prepare(report, 'https://example.com'))
    states = {t['name']:t['status'] for t in report['tools']}
    assert states == {'Search':'completed','Fetch':'failed','Browser':'completed'}
    assert 'Lead' in context and 'Rendered title' in context
    assert 'Fetch is unavailable' not in context
    assert 'untrusted' in context


def test_browser_deletes_session_on_cdp_failure(monkeypatch, tmp_path):
    from playwright import async_api
    class Chromium:
        async def connect_over_cdp(self, url): raise RuntimeError('private-CDP-token')
    class Playwright:
        chromium = Chromium()
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
    monkeypatch.setattr(async_api, 'async_playwright', Playwright)
    calls = []
    def handler(request):
        calls.append(request.method)
        if request.method == 'POST':
            return httpx.Response(201,json={'session_id':'session-1','cdp_url':'wss://example.com/private-token'})
        assert request.url.path == '/session-1'
        return httpx.Response(204)
    with pytest.raises(ResearchError) as error:
        asyncio.run(Toolkit('test',httpx.MockTransport(handler)).preview('https://example.com',tmp_path/'preview.png'))
    assert calls == ['POST','DELETE']
    assert 'private' not in str(error.value)


def test_findings_preserve_more_than_eight_valid_sources():
    from backend.models import Finding
    sources = [f'https://example.com/page-{i}' for i in range(9)]
    assert Finding(text='A supported finding', sources=sources).sources == sources
