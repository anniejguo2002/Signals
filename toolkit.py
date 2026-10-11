"""TinyFish public research tools. Secrets and CDP URLs stay server-side."""
import asyncio
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from .models import public_url
from .tinyfish import ResearchError


class Toolkit:
    def __init__(self, key, transport=None):
        self.key, self.transport = key, transport

    async def request(self, method, product, suffix='', **kwargs):
        try:
            async with httpx.AsyncClient(timeout=90, transport=self.transport) as client:
                response = await client.request(method, f'https://api.{product}.tinyfish.ai{suffix}', headers={'X-API-Key': self.key}, **kwargs)
                if response.is_error:
                    raise ResearchError(f'TinyFish {product.title()} returned HTTP {response.status_code}. Check API access, credits, or retry later.')
                return response.json() if response.content else {}
        except (httpx.HTTPError, ValueError) as exc:
            raise ResearchError(f'TinyFish {product.title()} could not complete this request.') from exc

    async def search(self, url):
        query = urlsplit(url).hostname + ' alternatives competitors'
        data = await self.request('GET', 'search', params={'query': query, 'purpose': 'Identify direct product competitors with supporting public sources.'})
        results = []
        for item in data.get('results', [])[:8]:
            try:
                link = public_url(item['url'])
            except (ValueError, KeyError):
                continue
            results.append({'url': link, 'title': str(item.get('title', ''))[:300], 'snippet': str(item.get('snippet', ''))[:1000]})
        return {'query': query, 'results': results}

    async def fetch(self, url):
        data = await self.request('POST', 'fetch', json={'urls': [url], 'format': 'markdown', 'ttl': 0, 'per_url_timeout_ms': 45000})
        pages = []
        for item in data.get('results', []):
            if isinstance(item.get('text'), str) and item['text'].strip():
                pages.append({'url': public_url(item.get('final_url') or item['url']), 'title': str(item.get('title', ''))[:300], 'text': item['text'][:10000]})
        if not pages:
            raise ResearchError('TinyFish Fetch returned no readable page. Agent will try browser research.')
        return {'pages': pages}

    async def preview(self, url, path):
        from playwright.async_api import async_playwright
        session = await self.request('POST', 'browser', json={'url': url, 'timeout_seconds': 120})
        session_id = session['session_id']
        try:
            async with asyncio.timeout(75):
                async with async_playwright() as p:
                    browser = await p.chromium.connect_over_cdp(session['cdp_url'])
                    page = browser.contexts[0].pages[0]
                    await page.wait_for_url(lambda value: str(value) != 'about:blank', timeout=45000)
                    await page.wait_for_load_state('domcontentloaded', timeout=45000)
                    await page.set_viewport_size({'width': 1280, 'height': 800})
                    title = await page.title()
                    final_url = public_url(page.url)
                    Path(path).parent.mkdir(parents=True, exist_ok=True)
                    await page.screenshot(path=str(path), full_page=False, timeout=15000)
                    return {'title': title[:300], 'url': final_url}
        except Exception as exc:
            raise ResearchError('TinyFish Browser preview was unavailable. Agent research can continue.') from exc
        finally:
            for attempt in range(3):
                try:
                    await self.request('DELETE', 'browser', '/' + session_id)
                    break
                except ResearchError:
                    if attempt < 2:
                        await asyncio.sleep(1)
