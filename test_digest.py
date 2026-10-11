import asyncio
import time
from fastapi.testclient import TestClient
from backend.main import make_app
from backend.digest import Digests, digest_text
from backend.store import Store


def report():
    field={'text':'A cited summary','sources':['https://example.com/']}
    company={'name':'Example','website':'https://example.com/','role':'target', **{k:dict(field) for k in ('positioning','products','pricing','customers','differentiation')}}
    return {'id':'r1','status':'completed','companies':[company],'url':'https://example.com/','competitor_limit':1,'created_at':'2026-10-11','errors':[]}


def test_signup_persisted_and_consent_and_vault(tmp_path):
    app=make_app(str(tmp_path/'test.sqlite'))
    app.state.store.save(report())
    with TestClient(app) as c:
        assert c.post('/api/weekly/subscribe',json={'email':'me@example.com','report_id':'r1','consent':False}).status_code==422
        assert c.post('/api/weekly/subscribe',json={'email':'bad\nemail','report_id':'r1','consent':True}).status_code==422
        for _ in range(2):
            assert c.post('/api/weekly/subscribe',json={'email':'me@example.com','report_id':'r1','consent':True}).status_code==202
        with app.state.store.connect() as db:
            assert db.execute('SELECT COUNT(*) FROM subscriptions').fetchone()[0]==1
            assert db.execute('SELECT status FROM subscriptions').fetchone()[0]=='pending'
        private=report();private['access_mode']='vault';app.state.store.save(private)
        assert c.post('/api/weekly/subscribe',json={'email':'other@example.com','report_id':'r1','consent':True}).status_code==422


def test_confirmation_delivery_weekly_and_unsubscribe(tmp_path,monkeypatch):
    store=Store(str(tmp_path/'test.sqlite'));store.save(report())
    settings={'SMTP_HOST':'smtp.example.com','SMTP_FROM':'signal@example.com','PUBLIC_BASE_URL':'https://signal.example.com','TINYFISH_API_KEY':'test'}
    service=Digests(store,lambda:settings,set())
    from backend.digest import Signup
    asyncio.run(service.subscribe(Signup(email='me@example.com',report_id='r1',consent=True)))
    sent=[]
    monkeypatch.setattr('backend.digest.send_mail',lambda *args:sent.append(args))
    asyncio.run(service.tick())
    with store.connect() as db: token,status=db.execute('SELECT token,status FROM subscriptions').fetchone()
    assert status=='confirmation_sent' and len(sent)==1
    assert 'Confirm weekly updates:' in sent[0][3]
    asyncio.run(service.confirm(token))
    assert service.lookup(token)['due']>time.time()+6*86400
    with store.connect() as db: db.execute('UPDATE subscriptions SET due=0')
    async def refresh(*args):
        fresh=report();fresh['id']='r2';store.save(fresh);return fresh
    monkeypatch.setattr(service,'refresh',refresh)
    asyncio.run(service.tick())
    assert len(sent)==2 and 'Unsubscribe:' in sent[1][3]
    assert service.lookup(token)['last_report']=='r2'
    asyncio.run(service.unsubscribe(token))
    with store.connect() as db:db.execute('UPDATE subscriptions SET due=0')
    asyncio.run(service.tick())
    assert len(sent)==2


def test_missing_email_config_sends_nothing(tmp_path,monkeypatch):
    store=Store(str(tmp_path/'test.sqlite'));store.save(report())
    service=Digests(store,lambda:{},set())
    from backend.digest import Signup
    result=asyncio.run(service.subscribe(Signup(email='me@example.com',report_id='r1',consent=True)))
    assert 'not configured' in result['message']
    monkeypatch.setattr('backend.digest.send_mail',lambda *args:(_ for _ in ()).throw(AssertionError('Must not send')))
    asyncio.run(service.tick())


def test_summary_difference_not_claimed_as_verified_change():
    import copy
    previous=report();current=copy.deepcopy(previous)
    current['companies'][0]['pricing']['text']='Different summary'
    text=digest_text(previous,current)
    assert 'summary differs — verify source' in text
    assert 'not market share or revenue' in text
    assert 'https://example.com/' in text
