import asyncio
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.models import ResearchRequest
from backend.vault import matching_items, matches_host
from backend.tinyfish import TinyFish
from backend.main import make_app
from backend.research import Researcher
from backend.store import Store
from backend.tests.test_app import company, report


@pytest.mark.parametrize('options', [
    {'use_vault': True},
    {'use_vault': True, 'credential_item_ids': ['cred:test']},
    {'use_vault': True, 'authorize_portal': True},
    {'credential_item_ids': ['cred:test']},
    {'authorize_portal': True},
    {'use_vault': True, 'authorize_portal': True, 'credential_item_ids': ['invalid']},
])
def test_gate_rejects_unscoped_or_unapproved_access(options):
    with pytest.raises(ValidationError):
        ResearchRequest(url='https://example.com', **options)


def test_vault_requires_https():
    with pytest.raises(ValidationError):
        ResearchRequest(url='http://example.com', use_vault=True, authorize_portal=True, credential_item_ids=['cred:test'])


def test_matching_and_allowlist_never_return_secrets():
    assert matches_host('portal.example.com', 'example.com')
    assert not matches_host('evil-example.com', 'example.com')
    assert not matches_host('example.com.evil.net', 'example.com')
    items = [{'itemId': 'cred:good', 'label': 'Portal', 'domains': ['example.com'], 'password': 'SECRET', 'fieldMetadata': [{'value': 'SECRET'}]}, {'itemId': 'cred:other', 'domains': ['other.com']}, {'itemId': 'cred:disabled', 'domains': ['example.com'], 'enabled': False}]
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={'items': items}))
    result = asyncio.run(matching_items('test', 'https://portal.example.com/', transport))
    assert result == [{'id': 'cred:good', 'label': 'Portal', 'domain': 'portal.example.com', 'has_totp': False}]
    assert 'SECRET' not in json.dumps(result)


def test_adapter_sends_only_selected_credentials():
    payloads = []
    async def handler(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, text='data: {"type":"COMPLETE","status":"COMPLETED","result":{"ok":true}}\n\n')
    async def run():
        async def receive(event): pass
        client = TinyFish('key', transport=httpx.MockTransport(handler))
        await client.run('https://example.com', 'goal', receive, credential_item_ids=['cred:selected'])
        await client.run('https://competitor.com', 'goal', receive)
    asyncio.run(run())
    assert payloads[0]['use_vault'] is True and payloads[0]['credential_item_ids'] == ['cred:selected']
    assert payloads[1]['use_vault'] is False and 'credential_item_ids' not in payloads[1]
    assert all(p['use_profile'] is False for p in payloads)


def test_api_revalidates_credential_scope(tmp_path, monkeypatch):
    monkeypatch.setattr('backend.main.api_key', lambda: 'test')
    async def inventory(*args): return [{'id': 'cred:allowed'}]
    monkeypatch.setattr('backend.main.matching_items', inventory)
    with TestClient(make_app(str(tmp_path / 'db'))) as client:
        response = client.post('/api/research', json={'url': 'https://example.com', 'use_vault': True, 'authorize_portal': True, 'credential_item_ids': ['cred:wrong']})
        assert response.status_code == 403
        assert client.get('/api/research').json() == []


def test_research_limits_vault_to_target_and_excludes_private_context(tmp_path, monkeypatch):
    async def allow(*args): pass
    monkeypatch.setattr('backend.research.check_public_dns', allow)
    calls = []
    class Client:
        async def run(self, url, goal, callback, **kwargs):
            calls.append((goal, kwargs))
            if len(calls) == 1:
                target = company()
                target['positioning'] = {'text': 'PRIVATE_TARGET_CONTEXT', 'sources': ['https://example.com/portal']}
                return {'company': target, 'competitors': [{'name': 'Alternative', 'website': 'https://alternative.org', 'reason': {'text': 'Public comparison', 'sources': ['https://example.com/compare']}}]}, 'target-run'
            return {**company('Alternative'), 'website': 'https://alternative.org/'}, 'competitor-run'
    data = report()
    asyncio.run(Researcher(Store(str(tmp_path / 'db')), Client()).execute(data, credential_item_ids=['cred:selected']))
    assert data['status'] == 'completed'
    assert calls[0][1] == {'credential_item_ids': ['cred:selected']}
    assert 'Do not log in' not in calls[0][0]
    assert calls[1][1] == {} and 'PRIVATE_TARGET_CONTEXT' not in calls[1][0]
    assert 'cred:selected' not in json.dumps(data)
