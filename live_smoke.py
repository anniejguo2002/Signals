"""Exercise the REAL running app. Never supplies synthetic research results."""
import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--url', default='https://plausible.io')
    parser.add_argument('--competitors', type=int, default=1, choices=(1, 2, 3))
    parser.add_argument('--report-id', help='Resume verification of an already submitted run without additional API calls.')
    parser.add_argument('--require-tools', action='store_true', help='Require successful real Search, Fetch, and Browser calls plus a served PNG preview.')
    parser.add_argument('--output', default='data/live-demo.json')
    args = parser.parse_args()
    async with httpx.AsyncClient(base_url=args.base_url, timeout=20) as client:
        response = await client.get('/api/health')
        response.raise_for_status()
        if not response.json()['configured']:
            raise SystemExit('Set TINYFISH_API_KEY in .env first.')
        if args.report_id:
            report_id = args.report_id
        else:
            response = await client.post('/api/research', json={'url': args.url, 'competitor_limit': args.competitors})
            response.raise_for_status()
            report_id = response.json()['id']
        print('Research report:', report_id, flush=True)
        deadline = time.monotonic() + 1800
        last = None
        while time.monotonic() < deadline:
            response = await client.get(f'/api/research/{report_id}')
            response.raise_for_status()
            report = response.json()
            if report['events']:
                message = report['events'][-1]['message']
                if message != last:
                    print(message, flush=True)
                    last = message
            if report['status'] not in ('running', 'queued'):
                break
            await asyncio.sleep(3)
        else:
            raise SystemExit('Timed out waiting for research; inspect saved report before retrying.')
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, indent=2))
        if report['status'] != 'completed' or len(report['companies']) < 2:
            raise SystemExit(f'Live validation failed or incomplete ({report["status"]}): {report["errors"]}')
        assert report['provenance'] == 'live_tinyfish' and report['runs']
        for company in report['companies']:
            assert company['run_id']
            for key in ('positioning', 'products', 'pricing', 'customers', 'differentiation'):
                finding = company[key]
                assert not finding['text'] or finding['sources'], f'Uncited {key}'
        if args.require_tools:
            tools = {item['name']: item for item in report.get('tools', [])}
            assert all(tools.get(name, {}).get('status') == 'completed' for name in ('Search', 'Fetch', 'Browser')), 'One or more public tools did not complete'
            assert tools['Search']['data']['results'] and tools['Fetch']['data']['pages']
            preview = await client.get(tools['Browser']['data']['image'])
            preview.raise_for_status()
            assert preview.content.startswith(b'\x89PNG\r\n\x1a\n')
            print('PASS: live Search results, fresh Fetch content, and rendered Browser PNG.')
        export = await client.get(f'/api/research/{report_id}/export')
        export.raise_for_status()
        assert export.json() == report
        print(f'PASS: {len(report["companies"])} companies, actual TinyFish runs, source-backed findings, export round-trip. Saved to {args.output}.')


if __name__ == '__main__':
    asyncio.run(main())
