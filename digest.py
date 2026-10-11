"""Opt-in weekly public research, persisted scheduling, and SMTP delivery."""
import asyncio
import json
import secrets
import smtplib
import time
import uuid
from email.message import EmailMessage
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator
from .models import Company, decode_result
from .research import BASE_GOAL, check_public_dns, now
from .tinyfish import TinyFish

WEEK = 7 * 86400
FIELDS = ('positioning', 'products', 'pricing', 'customers', 'differentiation')


def mail_ready(settings):
    return bool(settings.get('SMTP_HOST') and settings.get('SMTP_FROM') and str(settings.get('PUBLIC_BASE_URL', '')).startswith('https://'))


def send_mail(settings, recipient, subject, text):
    message = EmailMessage()
    message['From'] = settings['SMTP_FROM']
    message['To'] = recipient
    message['Subject'] = subject
    message.set_content(text)
    with smtplib.SMTP(settings['SMTP_HOST'], int(settings.get('SMTP_PORT') or 587), timeout=25) as smtp:
        smtp.starttls()
        if settings.get('SMTP_USER'):
            smtp.login(settings['SMTP_USER'], settings.get('SMTP_PASSWORD', ''))
        smtp.send_message(message)


def digest_text(previous, current):
    companies = current['companies']
    sources = {url for c in companies for key in FIELDS for url in c[key]['sources']}
    covered = sum(bool(c[key]['text'] and c[key]['sources']) for c in companies for key in FIELDS)
    lines = ['SIGNAL / WEEKLY COMPETITOR BRIEF', f'Researched: {current["created_at"]}', '',
             f'KPIs: {len(companies)} companies refreshed | {len(sources)} cited pages | {covered}/{len(companies)*5} fields sourced',
             'These are research coverage KPIs, not market share or revenue estimates.', '']
    old = {c['website']: c for c in previous['companies']}
    for c in companies:
        lines += [c['name']]
        for key in ('pricing', 'products', 'differentiation'):
            finding = c[key]
            prior = old.get(c['website'], {}).get(key, {})
            changed = prior.get('text') != finding['text']
            summary = finding['text'] or 'Not substantiated this week.'
            summary = summary[:497] + '…' if len(summary) > 500 else summary
            label = 'summary differs — verify source' if changed else 'summary unchanged'
            lines += [f'{key.title()} ({label}): {summary}', *finding['sources'][:2]]
        lines.append('')
    lines += ['A wording change in AI extraction does not establish a product or pricing change. Review linked pages.',
              *[f'Research gap: {e["company"]}: {e["message"]}' for e in current['errors']]]
    return '\n'.join(lines)


class Signup(BaseModel):
    email: str = Field(max_length=254)
    report_id: str
    consent: bool

    @field_validator('email')
    @classmethod
    def valid_email(cls, value):
        import re
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@<>\r\n]+@[^\s@<>\r\n]+\.[^\s@<>\r\n]+', value):
            raise ValueError('Enter a valid email address.')
        return value


class Digests:
    def __init__(self, store, config, tasks):
        self.store, self.config, self.tasks = store, config, tasks
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS subscriptions (id TEXT PRIMARY KEY, email TEXT, report_id TEXT, token TEXT UNIQUE, status TEXT, due REAL, attempts INTEGER DEFAULT 0, last_error TEXT, last_report TEXT, UNIQUE(email, report_id))')
        self.router = APIRouter()
        self.router.add_api_route('/api/weekly/status', self.status, methods=['GET'])
        self.router.add_api_route('/api/weekly/subscribe', self.subscribe, methods=['POST'], status_code=202)
        self.router.add_api_route('/api/weekly/confirm/{token}', self.confirm_page, methods=['GET'], response_class=HTMLResponse)
        self.router.add_api_route('/api/weekly/confirm/{token}', self.confirm, methods=['POST'], response_class=HTMLResponse)
        self.router.add_api_route('/api/weekly/unsubscribe/{token}', self.unsubscribe_page, methods=['GET'], response_class=HTMLResponse)
        self.router.add_api_route('/api/weekly/unsubscribe/{token}', self.unsubscribe, methods=['POST'], response_class=HTMLResponse)

    async def status(self):
        return {'email_configured': mail_ready(self.config()), 'cadence': 'Every 7 days after confirmation; server must be running.'}

    async def subscribe(self, request: Signup):
        report = self.store.get(request.report_id)
        if not request.consent:
            raise HTTPException(422, 'Consent is required for weekly emails.')
        if not report or not report['companies'] or report['status'] not in ('completed', 'partial'):
            raise HTTPException(422, 'Choose a completed research report first.')
        if report.get('access_mode') == 'vault':
            raise HTTPException(422, 'Weekly email currently supports public reports only.')
        with self.store.connect() as db:
            count = db.execute('SELECT COUNT(*) FROM subscriptions WHERE status != ?', ('unsubscribed',)).fetchone()[0]
            existing = db.execute('SELECT id FROM subscriptions WHERE email=? AND report_id=?', (request.email, request.report_id)).fetchone()
            if count >= 100 and not existing:
                raise HTTPException(429, 'Subscription capacity reached. Contact the workspace owner.')
            db.execute('INSERT OR IGNORE INTO subscriptions(id,email,report_id,token,status,due) VALUES(?,?,?,?,?,?)',
                       (str(uuid.uuid4()), request.email, request.report_id, secrets.token_urlsafe(32), 'pending', time.time()))
            db.execute("UPDATE subscriptions SET status='pending', token=?, due=?, attempts=0 WHERE email=? AND report_id=? AND status='unsubscribed'", (secrets.token_urlsafe(32),time.time(),request.email,request.report_id))
        return {'message': 'Signup saved. Confirm the email sent to you before updates begin.' if mail_ready(self.config()) else 'Signup saved, but email delivery is not configured yet. A confirmation email will be sent after the workspace owner enables it. No updates are active yet.'}

    def lookup(self, token):
        with self.store.connect() as db:
            db.row_factory = __import__('sqlite3').Row
            row = db.execute('SELECT * FROM subscriptions WHERE token=?', (token,)).fetchone()
        if not row:
            raise HTTPException(404, 'This email link is invalid.')
        return dict(row)

    async def confirm_page(self, token: str):
        self.lookup(token)
        return '<h1>Confirm weekly competitor updates</h1><p>Receive a public-source research brief every seven days. You can unsubscribe in any email.</p><form method="post"><button>Confirm subscription</button></form>'

    async def confirm(self, token: str):
        self.lookup(token)
        with self.store.connect() as db:
            db.execute("UPDATE subscriptions SET status='active', due=?, attempts=0 WHERE token=? AND status='confirmation_sent'", (time.time()+WEEK, token))
        return '<h1>Confirmation processed</h1><p>If this link was awaiting confirmation, your first weekly brief is scheduled seven days from now.</p>'

    async def unsubscribe_page(self, token: str):
        self.lookup(token)
        return '<h1>Stop weekly updates?</h1><form method="post"><button>Unsubscribe</button></form>'

    async def unsubscribe(self, token: str):
        self.lookup(token)
        with self.store.connect() as db:
            db.execute("UPDATE subscriptions SET status='unsubscribed' WHERE token=?", (token,))
        return '<h1>Unsubscribed</h1><p>No more weekly competitor emails will be scheduled.</p>'

    async def refresh(self, previous, key):
        report = {'id': str(uuid.uuid4()), 'url': previous['url'], 'created_at': now(), 'finished_at': None,
                  'competitor_limit': previous['competitor_limit'], 'status': 'running', 'phase':'competitors', 'companies':[],
                  'errors':[], 'events':[], 'runs':[], 'candidates':[], 'completed_steps':0, 'total_steps':len(previous['companies']),
                  'provenance':'live_tinyfish', 'access_mode':'public'}
        client = TinyFish(key)
        for company in previous['companies']:
            try:
                await check_public_dns(company['website'])
                async def event(item):
                    if item.get('run_id') and not any(r['id']==item['run_id'] for r in report['runs']):
                        report['runs'].append({'id':item['run_id'], 'company':company['name'], 'url':'https://agent.tinyfish.ai/runs/'+item['run_id']})
                raw, run_id = await client.run(company['website'], BASE_GOAL + '\nResearch this exact product, not unrelated parent-company products: ' + json.dumps(company['name']) + '\nReturn the company JSON object directly.', event)
                fresh = Company.model_validate(decode_result(raw)).model_dump()
                fresh.update(role=company['role'], run_id=run_id)
                report['companies'].append(fresh)
            except Exception:
                report['errors'].append({'company':company['name'], 'message':'Fresh research unavailable; prior findings were not substituted.'})
            report['completed_steps'] += 1
        report.update(status='partial' if report['errors'] else 'completed', phase='done', finished_at=now())
        if not report['companies']:
            raise RuntimeError('No fresh profiles available')
        self.store.save(report)
        return report

    async def tick(self):
        settings = self.config()
        if not mail_ready(settings):
            return
        with self.store.connect() as db:
            db.row_factory = __import__('sqlite3').Row
            row = db.execute("SELECT * FROM subscriptions WHERE status IN ('pending','active') AND due<=? AND attempts<3 ORDER BY due LIMIT 1", (time.time(),)).fetchone()
        if not row:
            return
        sub=dict(row)
        try:
            base = settings['PUBLIC_BASE_URL'].rstrip('/')
            unsubscribe = base+'/api/weekly/unsubscribe/'+sub['token']
            if sub['status']=='pending':
                await asyncio.to_thread(send_mail, settings, sub['email'], 'Confirm your Signal weekly competitor brief', 'Confirm weekly updates: '+base+'/api/weekly/confirm/'+sub['token']+'\n\nDid not request this? Ignore this email or unsubscribe: '+unsubscribe)
                with self.store.connect() as db:
                    db.execute("UPDATE subscriptions SET status='confirmation_sent', attempts=0 WHERE id=? AND status='pending'", (sub['id'],))
            else:
                if not settings.get('TINYFISH_API_KEY'):
                    return
                tracked = self.store.get(sub['report_id'])
                previous = self.store.get(sub['last_report']) if sub['last_report'] else tracked
                current = await self.refresh(tracked, settings['TINYFISH_API_KEY'])
                # A visitor may unsubscribe while the provider is running.
                if self.lookup(sub['token'])['status'] != 'active':
                    return
                await asyncio.to_thread(send_mail, settings, sub['email'], 'Your weekly Signal competitor brief', digest_text(previous,current)+'\n\nFull report: '+base+'/?report='+current['id']+'\nUnsubscribe: '+unsubscribe)
                with self.store.connect() as db:
                    db.execute('UPDATE subscriptions SET due=?, attempts=0, last_error=NULL,last_report=? WHERE id=?', (time.time()+WEEK, current['id'], sub['id']))
        except Exception:
            with self.store.connect() as db:
                db.execute('UPDATE subscriptions SET attempts=attempts+1,due=?,last_error=? WHERE id=?', (time.time()+3600,'Delivery or research failed. Check SMTP and TinyFish configuration.',sub['id']))

    async def loop(self):
        while True:
            await asyncio.sleep(60)
            # Share the foreground job gate while weekly work runs.
            if not self.tasks:
                task = asyncio.create_task(self.tick())
                if not task.done():
                    self.tasks.add(task)
                    try:
                        await task
                    finally:
                        self.tasks.discard(task)
