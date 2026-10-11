import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import dotenv_values
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import ResearchRequest, public_url
from .research import Researcher, now
from .store import Store
from .tinyfish import TinyFish, ResearchError
from .vault import matching_items
from .toolkit import Toolkit
from .digest import Digests

ROOT = Path(__file__).resolve().parent.parent


def config():
    return {**dotenv_values(ROOT / '.env'), **os.environ}


def api_key():
    return (config().get('TINYFISH_API_KEY') or '').strip()


def make_app(database_path=None):
    settings = config()
    path = database_path or settings.get('DATABASE_PATH', 'data/research.sqlite3')
    store = Store(str(ROOT / path) if not Path(path).is_absolute() else path)
    tasks = set()
    digests = Digests(store, config, tasks)

    @asynccontextmanager
    async def lifespan(app):
        for report in store.all():
            if report['status'] in ('queued', 'running'):
                report['status'] = 'failed'
                report['finished_at'] = now()
                report['errors'].append({'company': report['url'], 'message': 'Server restarted during this run. Its saved findings remain available; check linked TinyFish runs before restarting.'})
                store.save(report)
        weekly_worker = asyncio.create_task(digests.loop())
        yield
        weekly_worker.cancel()
        await asyncio.gather(weekly_worker, return_exceptions=True)
        for task in list(tasks):
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(title='Signal · Competitor Intelligence', lifespan=lifespan)
    app.state.store = store
    app.include_router(digests.router)

    @app.get('/api/health')
    async def health():
        return {'status': 'ok', 'configured': bool(api_key()), 'provider': 'TinyFish', 'active_runs': len(tasks)}

    @app.post('/api/research', status_code=202)
    async def start(request: ResearchRequest):
        key = api_key()
        if not key:
            raise HTTPException(503, 'Add TINYFISH_API_KEY to the project .env file, save it, then try again. No server restart is needed.')
        if tasks:
            raise HTTPException(409, 'A research report is already running. Open it in Recent research or wait for it to finish.')
        if request.use_vault:
            try:
                allowed = {item['id'] for item in await matching_items(key, request.url)}
            except ResearchError as exc:
                raise HTTPException(502, str(exc)) from exc
            if not set(request.credential_item_ids).issubset(allowed):
                raise HTTPException(403, 'Selected credentials are unavailable or do not match this portal. Refresh the Vault selection.')
            # Inventory lookup awaits network IO; recheck the single-job gate afterwards.
            if tasks:
                raise HTTPException(409, 'Another research report started while Vault was checked. Try again after it finishes.')
        report = {
            'id': str(uuid.uuid4()), 'url': request.url, 'competitor_limit': request.competitor_limit,
            'status': 'queued', 'phase': 'discovery', 'created_at': now(), 'finished_at': None,
            'completed_steps': 0, 'total_steps': request.competitor_limit + 1,
            'companies': [], 'candidates': [], 'events': [], 'errors': [], 'runs': [],
            'provenance': 'live_tinyfish',
            'access_mode': 'vault' if request.use_vault else 'public',
        }
        store.save(report)
        timeout = max(60, min(1800, int(config().get('RESEARCH_TIMEOUT_SECONDS') or 480)))
        researcher = Researcher(store, TinyFish(key, timeout), Toolkit(key), ROOT / 'data/previews')
        task = asyncio.create_task(researcher.execute(report, credential_item_ids=request.credential_item_ids))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        return report

    @app.get('/api/vault/items')
    async def vault_items(url: str):
        if not api_key():
            raise HTTPException(503, 'Configure TINYFISH_API_KEY before using Vault.')
        try:
            normalized = public_url(url)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        try:
            return {'items': await matching_items(api_key(), normalized)}
        except ResearchError as exc:
            raise HTTPException(502, str(exc)) from exc

    @app.get('/api/research')
    async def history():
        return [{k: report[k] for k in ('id', 'url', 'status', 'created_at', 'finished_at', 'provenance')} | {
            'name': report['companies'][0]['name'] if report['companies'] else None,
            'company_count': len(report['companies']),
        } for report in store.all()]

    @app.get('/api/research/{report_id}')
    async def get_report(report_id: str):
        report = store.get(report_id)
        if not report:
            raise HTTPException(404, 'Research report not found.')
        return report

    @app.get('/api/research/{report_id}/preview')
    async def preview(report_id: str):
        report = await get_report(report_id)
        path = ROOT / 'data/previews' / (report['id'] + '.png')
        if not path.exists():
            raise HTTPException(404, 'No browser preview is available for this report.')
        return FileResponse(path, media_type='image/png')

    @app.get('/api/research/{report_id}/export')
    async def export_report(report_id: str):
        from fastapi.responses import JSONResponse
        report = await get_report(report_id)
        return JSONResponse(report, headers={'Content-Disposition': f'attachment; filename="signal-{report["id"]}.json"'})

    dist = ROOT / 'frontend/dist'
    if dist.exists():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

        @app.get('/favicon.svg', include_in_schema=False)
        async def favicon():
            return FileResponse(dist / 'favicon.svg')

        @app.get('/', include_in_schema=False)
        async def frontend():
            return FileResponse(dist / 'index.html')

    return app


app = make_app()
