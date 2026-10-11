"""TinyFish's official HTTP API, with real SSE progress and polling recovery."""
import asyncio
import json
from urllib.parse import quote

import httpx

BASE_URL = 'https://agent.tinyfish.ai/v1'


class ResearchError(Exception):
    pass


def response_error(status: int) -> str:
    return {
        401: 'TinyFish rejected the API key. Check TINYFISH_API_KEY in .env.',
        402: 'TinyFish needs wallet funds before research can run. Check your TinyFish dashboard.',
        403: 'TinyFish denied this request. Check your account permissions and balance.',
        429: 'TinyFish is rate limiting requests. Wait a moment, then try again.',
    }.get(status, f'TinyFish returned HTTP {status}. Please try again later.')


async def sse_events(lines):
    data = []
    async for line in lines:
        if line == '':
            if data:
                yield json.loads('\n'.join(data))
                data = []
        elif line.startswith('data:'):
            data.append(line[5:].lstrip())
    if data:
        yield json.loads('\n'.join(data))


class TinyFish:
    def __init__(self, key: str, timeout: int = 480, transport=None):
        self.key = key
        self.timeout = timeout
        self.transport = transport

    async def run(self, url, goal, on_event, *, credential_item_ids=None):
        run_id = None
        terminal = False
        async with httpx.AsyncClient(
            headers={'X-API-Key': self.key},
            timeout=httpx.Timeout(65, connect=20), transport=self.transport,
        ) as client:
            try:
                async with asyncio.timeout(self.timeout):
                    try:
                        async with client.stream('POST', BASE_URL + '/automation/run-sse', json={
                            'url': url, 'goal': goal,
                            'agent_config': {'max_duration_seconds': self.timeout - 20},
                            'use_vault': bool(credential_item_ids),
                            'use_profile': False,
                            **({'credential_item_ids': credential_item_ids} if credential_item_ids else {}),
                        }) as response:
                            if response.status_code != 200:
                                raise ResearchError(response_error(response.status_code))
                            async for event in sse_events(response.aiter_lines()):
                                if event.get('run_id'):
                                    run_id = str(event['run_id'])
                                if event.get('type') == 'COMPLETE':
                                    terminal = True
                                    await on_event({'type': 'RUN_FINISHED', 'run_id': run_id})
                                    return self.result(event, run_id)
                                if event.get('type') in ('STARTED', 'PROGRESS'):
                                    await on_event(event)
                    except (httpx.TransportError, json.JSONDecodeError):
                        if not run_id:
                            raise ResearchError('TinyFish disconnected before returning a run ID. Check the TinyFish dashboard before retrying; the request may have started.')
                    if not run_id:
                        raise ResearchError('TinyFish ended the stream without a result or run ID.')
                    await on_event({'type': 'PROGRESS', 'purpose': 'Stream interrupted. Recovering the existing TinyFish run…', 'run_id': run_id})
                    while True:
                        await asyncio.sleep(3)
                        try:
                            response = await client.get(BASE_URL + '/runs/' + quote(run_id, safe=''))
                            if response.status_code in (429, 500, 502, 503, 504):
                                continue
                            if response.status_code != 200:
                                raise ResearchError(response_error(response.status_code))
                            event = response.json()
                        except httpx.TransportError:
                            continue
                        if event.get('status') in ('COMPLETED', 'FAILED', 'CANCELLED'):
                            terminal = True
                            await on_event({'type': 'RUN_FINISHED', 'run_id': run_id})
                            return self.result(event, run_id)
            except TimeoutError as exc:
                raise ResearchError(f'TinyFish research exceeded {self.timeout} seconds. Try fewer competitors or another public website.') from exc
            finally:
                if run_id and not terminal:
                    try:
                        await asyncio.shield(client.post(BASE_URL + '/runs/' + quote(run_id, safe='') + '/cancel', timeout=10))
                    except (httpx.HTTPError, asyncio.CancelledError):
                        pass

    @staticmethod
    def result(event, run_id):
        if event.get('status') != 'COMPLETED':
            error = event.get('error') or {}
            code = error.get('code', event.get('status', 'FAILED')) if isinstance(error, dict) else 'FAILED'
            raise ResearchError(f'TinyFish run {code}. The site may be blocked, unavailable, or the account may need funds. Review the linked run for details.')
        result = event.get('result', event.get('resultJson'))
        if result is None:
            raise ResearchError('TinyFish completed without research data. No findings have been invented.')
        return result, run_id
