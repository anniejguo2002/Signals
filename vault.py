"""Read allowlisted Vault metadata only; passwords never enter this application."""
from urllib.parse import urlsplit
import httpx
from .tinyfish import BASE_URL, ResearchError, response_error


def matches_host(host, domain):
    value = domain.strip().lower().rstrip('.')
    if '://' in value:
        value = urlsplit(value).hostname or ''
    return bool(value and '.' in value and '*' not in value and (host == value or host.endswith('.' + value)))


async def matching_items(key, url, transport=None):
    host = urlsplit(url).hostname.lower().rstrip('.')
    try:
        async with httpx.AsyncClient(headers={'X-API-Key': key}, timeout=20, transport=transport) as client:
            response = await client.get(BASE_URL + '/vault/items')
        if response.status_code != 200:
            raise ResearchError('Vault is unavailable. Reconnect your password manager in TinyFish Settings → Vault. ' + response_error(response.status_code))
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get('items'), list):
            raise ValueError('Unexpected vault response')
        items = []
        for item in data['items']:
            if not isinstance(item, dict) or item.get('enabled') is False:
                continue
            domains = item.get('domains') or item.get('websites') or []
            item_id = item.get('itemId') or item.get('item_id')
            if isinstance(item_id, str) and item_id.startswith('cred:') and isinstance(domains, list) and any(isinstance(d, str) and matches_host(host, d) for d in domains):
                items.append({'id': item_id, 'label': str(item.get('label') or 'Portal credential')[:160], 'domain': host, 'has_totp': bool(item.get('hasTotp', item.get('has_totp', False)))})
        return items
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise ResearchError('Could not read Vault metadata. Check TinyFish Settings → Vault and try again.') from exc
