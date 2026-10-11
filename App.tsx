import React, { useEffect, useRef, useState } from 'react';
import ReportAnalytics from './ReportAnalytics';
import StrategyLab from './StrategyLab';
import WeeklyUpdates from './WeeklyUpdates';
import ResearchTools, { type ToolResult } from './ResearchTools';
import VaultAccess, { PUBLIC_ACCESS, type VaultOptions } from './VaultAccess';
import { Activity, ArrowDownToLine, ArrowRight, ArrowUpRight, BookOpen, Check, CheckCircle2, ChevronRight, Circle, Clock3, Compass, ExternalLink, FileSearch, Globe2, Layers3, LoaderCircle, Plus, Radio, Search, ShieldCheck, Sparkles, Target, TriangleAlert, X } from 'lucide-react';

type Finding = { text: string | null; sources: string[] };
type Company = { name: string; website: string; role: string; run_id: string; positioning: Finding; products: Finding; pricing: Finding; customers: Finding; differentiation: Finding; limitations: string[]; reason?: Finding };
type ResearchEvent = { at: string; message: string; company: string | null; kind: string };
type Report = { tools?: ToolResult[]; access_mode?: 'public' | 'vault'; id: string; url: string; status: string; phase: string; competitor_limit: number; created_at: string; finished_at: string | null; completed_steps: number; total_steps: number; companies: Company[]; candidates: { name: string; website: string; status: string; reason: Finding; error?: string }[]; events: ResearchEvent[]; errors: { company: string; message: string }[]; runs: { id: string; company: string; url: string }[]; provenance: string };
type HistoryItem = Pick<Report, 'id' | 'url' | 'status' | 'created_at' | 'finished_at'> & { name: string | null; company_count: number };
const fields = [{ key: 'positioning', label: 'Positioning', icon: Compass }, { key: 'products', label: 'Products', icon: Layers3 }, { key: 'pricing', label: 'Pricing', icon: Activity }, { key: 'customers', label: 'Target customers', icon: Target }, { key: 'differentiation', label: 'Differentiation', icon: Sparkles }] as const;
const isActive = (status?: string) => status === 'running' || status === 'queued';
const domain = (url: string) => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; } };
const date = (value: string) => new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : response.status === 422 ? 'Enter a valid public company website URL.' : `Request failed (${response.status}). Please try again.`);
  return data;
}
function Logo({ small = false }: { small?: boolean }) { return <span className={`signal-logo ${small ? 'small' : ''}`} aria-hidden="true"><i/><i/><i/></span>; }
function SourceLinks({ sources }: { sources: string[] }) { return <div className="source-links">{sources.map((url, i) => <a href={url} key={url} target="_blank" rel="noopener noreferrer" title={url}><span>{i + 1}</span>{domain(url)}<ArrowUpRight size={11}/></a>)}</div>; }
function FindingCell({ finding }: { finding: Finding }) { return finding.text ? <><p>{finding.text}</p><SourceLinks sources={finding.sources}/></> : <span className="not-found">Not found in available sources</span>; }

export default function App() {
  const [url, setUrl] = useState('');
  const [limit, setLimit] = useState(3);
  const [vault, setVault] = useState<VaultOptions>(PUBLIC_ACCESS);
  const [report, setReport] = useState<Report | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [health, setHealth] = useState<{ configured: boolean } | null>(null);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [tab, setTab] = useState('comparison');
  const [showGuide, setShowGuide] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [tick, setTick] = useState(Date.now());
  const [savedView, setSavedView] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const modalRef = useRef<HTMLElement>(null);
  const selection = useRef(0);
  const refreshHistory = () => api<HistoryItem[]>('/api/research').then(setHistory).catch(() => {});
  useEffect(() => {
    api<{ configured: boolean }>('/api/health').then(setHealth).catch(() => setError('Cannot reach the backend. Start FastAPI on port 8000, then refresh.'));
    refreshHistory();
    const id = new URLSearchParams(location.search).get('report');
    if (id) void loadReport(id);
  }, []);
  useEffect(() => {
    if (!report || !isActive(report.status)) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await api<Report>(`/api/research/${report.id}`);
        if (!disposed) { setReport(next); setReconnecting(false); if (!isActive(next.status)) refreshHistory(); }
      } catch { if (!disposed) setReconnecting(true); }
      if (!disposed) timer = setTimeout(poll, 1500);
    };
    timer = setTimeout(poll, 1000);
    return () => { disposed = true; clearTimeout(timer); };
  }, [report?.id, report?.status]);
  useEffect(() => { if (!isActive(report?.status)) return; const timer = setInterval(() => setTick(Date.now()), 1000); return () => clearInterval(timer); }, [report?.status]);
  useEffect(() => {
    if (!showGuide) return;
    const previous = document.activeElement as HTMLElement | null;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setShowGuide(false);
      if (e.key === 'Tab') {
        const buttons = modalRef.current?.querySelectorAll<HTMLButtonElement>('button');
        if (!buttons?.length) return;
        const first = buttons[0], last = buttons[buttons.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    window.addEventListener('keydown', handler);
    return () => { window.removeEventListener('keydown', handler); previous?.focus(); };
  }, [showGuide]);

  async function loadReport(id: string) {
    const current = ++selection.current;
    try {
      const result = await api<Report>(`/api/research/${id}`);
      if (current !== selection.current) return;
      setVault(PUBLIC_ACCESS); setReport(result); setUrl(result.url); setLimit(result.competitor_limit); setSavedView(!isActive(result.status)); setError(''); setTab('comparison'); setHistoryOpen(false);
      window.history.replaceState(null, '', `?report=${id}`);
    } catch (e) { setError((e as Error).message); }
  }
  async function start(value = url, count = limit, publicOnly = false) {
    if (submitting || isActive(report?.status)) return;
    if (!value.trim()) { inputRef.current?.focus(); return; }
    if (!publicOnly && vault.use_vault && (!vault.credential_item_ids.length || !vault.authorize_portal)) { setError('Select a matching Vault credential and authorize this portal before starting.'); return; }
    setSubmitting(true); setError(''); setSavedView(false); setTab('comparison');
    ++selection.current;
    try {
      const result = await api<Report>('/api/research', { method: 'POST', body: JSON.stringify({ url: value.trim(), competitor_limit: count, ...(publicOnly ? PUBLIC_ACCESS : vault) }) });
      setReport(result); setUrl(value); setLimit(count); setHealth({ configured: true });
      window.history.replaceState(null, '', `?report=${result.id}`); refreshHistory();
    } catch (e) { setError((e as Error).message); }
    finally { setSubmitting(false); }
  }
  function reset() { setVault(PUBLIC_ACCESS); ++selection.current; setReport(null); setSavedView(false); setError(''); setUrl(''); setHistoryOpen(false); window.history.replaceState(null, '', '/'); inputRef.current?.focus(); }
  const active = isActive(report?.status);
  const sources = report ? [...new Set(report.companies.flatMap(c => [...fields.flatMap(f => c[f.key].sources), ...(c.reason?.sources || [])]))] : [];
  const findings = report?.companies.reduce((sum, c) => sum + fields.filter(f => c[f.key].text).length, 0) || 0;
  const elapsed = report ? Math.max(0, Math.floor(((report.finished_at ? new Date(report.finished_at).getTime() : tick) - new Date(report.created_at).getTime()) / 1000)) : 0;
  const successful = history.filter(h => h.company_count > 1 && h.status === 'completed');

  return <div className="app-shell">
    <aside className="sidebar">
      <button className="brand" onClick={reset} aria-label="Signal home"><Logo/><span>signal<span className="brand-dot">.</span></span></button>
      <div className="workspace"><span className="workspace-avatar">W</span><div>My workspace<small>Hackathon edition</small></div><ChevronRight size={15}/></div>
      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="Main navigation">
        <button className={!historyOpen ? 'nav-item selected' : 'nav-item'} onClick={() => setHistoryOpen(false)}><Compass size={18}/> Intelligence <span className="nav-dot"/></button>
        <button className={historyOpen ? 'nav-item selected' : 'nav-item'} onClick={() => { refreshHistory(); setHistoryOpen(true); }}><Clock3 size={18}/> Research history <span className="nav-count">{history.length}</span></button>
      </nav>
      <div className="recent-heading"><span className="nav-label">RECENT RESEARCH</span><button onClick={reset} title="New research" aria-label="New research"><Plus size={16}/></button></div>
      <div className="recent-list">{history.length ? history.slice(0, 5).map(h => <button onClick={() => loadReport(h.id)} className={report?.id === h.id ? 'recent active-recent' : 'recent'} key={h.id}><span className={`history-dot ${h.status}`}/><span>{h.name || domain(h.url)}</span><ChevronRight size={12}/></button>) : <p className="sidebar-empty">Your research will appear here.<br/>Start with a company URL.</p>}</div>
      <div className="sidebar-bottom"><div className="engine-card"><div><Radio size={17}/><span>Powered by TinyFish</span></div><p>Real websites.<br/>Fresh competitive intelligence.</p><a href="https://docs.tinyfish.ai/agent-api/reference" target="_blank" rel="noopener noreferrer">Explore the technology <ArrowUpRight size={13}/></a></div><button className="profile" onClick={() => setShowGuide(true)}><span className="profile-avatar">S</span><span>Signal workspace<small>Built for the curious</small></span><BookOpen size={16}/></button></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div><span className="mobile-logo"><Logo small/></span><span className="breadcrumb">Workspace</span><ChevronRight size={13}/><span>Competitor intelligence</span></div><div className="topbar-actions"><button className="mobile-action" aria-label="Open research history" onClick={() => { refreshHistory(); setHistoryOpen(true); }}><Clock3 size={17}/></button><button className="mobile-action" aria-label="Start new research" onClick={reset}><Plus size={18}/></button><button className="guide-link" aria-label="How it works" onClick={() => setShowGuide(true)}><BookOpen size={15}/><span>How it works</span><ArrowUpRight size={13}/></button></div></header>
      <main>
        <div className="page-heading"><div><div className="eyebrow"><span/> THE COMPETITIVE EDGE</div><h1>Clarity in a crowded market.</h1><p>Know your company. Understand the competition. Find your edge.</p></div><span className="live-badge"><span/> Live web research</span></div>
        {historyOpen ? <section className="history-panel surface"><div className="section-heading"><div><h2>Research history</h2><p>Actual runs, saved with their sources and timestamps.</p></div><button className="secondary-button" onClick={reset}><Plus size={15}/> New research</button></div>{history.length ? history.map(h => <button className="history-row" key={h.id} onClick={() => loadReport(h.id)}><span className="company-monogram">{(h.name || domain(h.url))[0].toUpperCase()}</span><span><strong>{h.name || domain(h.url)}</strong><small>{date(h.created_at)} · {h.company_count} companies researched</small></span><span className={`status-tag ${h.status}`}>{h.status}</span><ArrowRight size={16}/></button>) : <div className="history-empty"><FileSearch size={32}/><h3>A fresh start.</h3><p>Your first research report is one URL away.</p><button className="primary-button" onClick={reset}>Start researching <ArrowRight size={16}/></button></div>}</section> : <>
        <section className="search-card surface">
          <div className="search-card-heading"><div className="mini-icon"><Globe2 size={19}/></div><div><h2>Your next insight starts with a URL.</h2><p>We’ll research the company and map its closest competitors.</p></div><span className="step-label">01 / DISCOVER</span></div>
          <form onSubmit={e => { e.preventDefault(); void start(); }}>
            <label htmlFor="company-url" className="input-label">Company website</label>
            <div className="search-controls"><div className="url-input"><Globe2 size={18}/><input id="company-url" ref={inputRef} value={url} onChange={e => { setUrl(e.target.value); setVault({ ...vault, credential_item_ids: [], authorize_portal: false }); }} placeholder="Enter a company URL, e.g. plausible.io" autoComplete="url" disabled={active || submitting} required aria-describedby="url-hint"/></div><label className="limit-control"><span className="sr-only">Maximum competitors</span><select value={limit} onChange={e => setLimit(Number(e.target.value))} disabled={active || submitting}>{[1, 2, 3].map(n => <option key={n} value={n}>Up to {n} competitor{n !== 1 ? 's' : ''}</option>)}</select></label><button type="submit" className="primary-button research-button" disabled={active || submitting}>{active || submitting ? <LoaderCircle size={17} className="spin"/> : <Sparkles size={17}/>}<span>{active ? 'Researching' : submitting ? 'Starting…' : 'Analyze company'}</span>{!active && !submitting && <ArrowRight size={17}/>}</button></div>
          </form>
          <VaultAccess url={url} value={vault} onChange={setVault} disabled={active || submitting}/>
          <div className="search-foot"><span id="url-hint"><ShieldCheck size={14}/> {vault.use_vault ? 'Authorized portal + public competitors.' : 'Public sources only. Every finding linked.'}</span><span><Clock3 size={13}/> Usually a few minutes</span></div>
          {!active && <div className="sample-line"><span>Take it for a spin</span><button onClick={() => { setUrl('https://plausible.io'); setLimit(1); setVault(PUBLIC_ACCESS); void start('https://plausible.io', 1, true); }}>Research Plausible <ArrowUpRight size={12}/></button><span className="sample-note">A live, focused demo · 1 competitor</span></div>}
        </section>
        {error && <div className="error-banner" role="alert"><TriangleAlert size={19}/><div><strong>Research couldn’t start</strong><p>{error}</p></div><button aria-label="Dismiss error" onClick={() => setError('')}><X size={16}/></button></div>}
        {!health?.configured && health && !error && <div className="setup-note"><span className="setup-dot"/><p><strong>One quick setup step.</strong> Add your TinyFish API key to the server’s <code>.env</code> file to start live research.</p><button onClick={() => setShowGuide(true)}>Setup guide <ArrowRight size={14}/></button></div>}
        {report ? <>
          {active && <ResearchTools tools={report.tools} runs={report.runs.length} active={active}/>}

          <section className="research-status surface" aria-live="polite"><div className="status-heading"><div className={`status-symbol ${active ? 'working' : report.status}`} >{active ? <Radio size={20}/> : report.status === 'completed' ? <CheckCircle2 size={20}/> : <TriangleAlert size={20}/>}</div><div><h2>{active ? (report.phase === 'discovery' ? 'Getting to know the company' : 'Exploring the competitive landscape') : report.status === 'completed' ? 'Your competitive landscape, uncovered.' : report.companies.length ? 'Research finished with some gaps' : 'Research needs another try'}</h2><p>{active ? `Live TinyFish research · ${Math.floor(elapsed / 60)}m ${elapsed % 60}s elapsed` : `${savedView ? 'Saved live research' : 'Researched live'} · ${date(report.created_at)} · ${report.companies.length} companies`}</p></div><span className={`status-tag ${report.status}`}>{active ? 'In progress' : report.status === 'partial' ? 'Partial report' : report.status}</span></div>
          {report.access_mode === 'vault' && <div className="vault-report-note"><ShieldCheck size={15}/><span>Vault-enabled target · May contain gated information. Login outcome and access limitations are recorded in the research notes. Review before sharing or exporting.</span></div>}
          {active && <><div className="progress-track"><span style={{ width: `${Math.max(4, report.completed_steps / report.total_steps * 100)}%` }}/></div><div className="progress-steps"><span className={report.completed_steps >= 1 ? 'done' : 'current'}>{report.completed_steps >= 1 ? <Check size={13}/> : <LoaderCircle size={13} className="spin"/>} Company & discovery</span>{report.candidates.map(c => <span className={c.status === 'completed' ? 'done' : c.status === 'running' ? 'current' : ''} key={c.website}>{c.status === 'completed' ? <Check size={13}/> : c.status === 'running' ? <LoaderCircle size={13} className="spin"/> : c.status === 'failed' ? <TriangleAlert size={13}/> : <Circle size={11}/>} {c.name}</span>)}<span><Circle size={11}/> Comparison</span></div></>}
          {reconnecting && <p className="reconnect" role="status">Connection interrupted. Reconnecting to your saved run…</p>}
          {report.errors.map((e, i) => <div className="report-error" key={i}><TriangleAlert size={15}/><p><strong>{domain(e.company)}</strong> — {e.message}</p></div>)}
          {active && report.events.length > 0 && <div className="latest-event"><span className="pulsing-dot"/>{report.events.at(-1)?.message}</div>}
          </section>
          {report.companies.length > 0 && <>
          <div className="metric-grid"><div className="metric"><span><Layers3 size={16}/>Companies researched</span><strong>{String(report.companies.length).padStart(2, '0')}<small>in your landscape</small></strong></div><div className="metric"><span><Globe2 size={16}/>Source pages</span><strong>{String(sources.length).padStart(2, '0')}<small>linked to findings</small></strong></div><div className="metric"><span><ShieldCheck size={16}/>Sourced findings</span><strong>{String(findings).padStart(2, '0')}<small>ready to explore</small></strong></div></div>
          <section className="results surface"><div className="results-heading"><div><span className="eyebrow muted">THE BIG PICTURE</span><h2>{report.companies[0].name} & the competition</h2></div><a className="secondary-button" href={`/api/research/${report.id}/export`} download><ArrowDownToLine size={15}/><span>Export report</span></a></div><div className="tab-bar" role="tablist" aria-label="Report views">{[{ id: 'comparison', name: 'Comparison', icon: Layers3 }, { id: 'sources', name: 'Sources', icon: Globe2 }, { id: 'activity', name: 'Research log', icon: Activity }].map(t => <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)} className={tab === t.id ? 'tab active-tab' : 'tab'}><t.icon size={15}/>{t.name}{t.id === 'sources' && <span>{sources.length}</span>}</button>)}</div>
          {tab === 'comparison' && <div className="comparison-scroll" role="tabpanel"><table className="comparison-table"><thead><tr><th className="dimension-heading">A closer look<span>Evidence, side by side.</span></th>{report.companies.map((c, i) => <th key={c.website} className={i === 0 ? 'target-column' : ''}><div className="company-th"><span className={`company-monogram tone-${i}`}>{c.name[0].toUpperCase()}</span><span className="company-label">{i === 0 ? 'YOUR COMPANY' : `COMPETITOR ${i}`}</span><h3>{c.name}</h3><a href={c.website} target="_blank" rel="noopener noreferrer">{domain(c.website)} <ArrowUpRight size={12}/></a></div></th>)}</tr></thead><tbody>{fields.map(f => <tr key={f.key}><th><f.icon size={15}/>{f.label}</th>{report.companies.map((c, i) => <td key={c.website} className={i === 0 ? 'target-column' : ''}><FindingCell finding={c[f.key]}/></td>)}</tr>)}<tr><th><FileSearch size={15}/>Research notes</th>{report.companies.map(c => <td key={c.website}>{c.reason && <><div className="cell-caption">WHY IT COMPETES</div><FindingCell finding={c.reason}/></>}{c.limitations.length ? <ul className="limitations">{c.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul> : <span className="not-found">No access limitations reported.</span>}</td>)}</tr></tbody></table></div>}
          {tab === 'sources' && <div className="sources-panel" role="tabpanel"><p className="panel-intro">Pages cited by TinyFish during this run. Open the original source to verify a claim.</p>{sources.map((source, i) => <a className="source-row" key={source} href={source} target="_blank" rel="noopener noreferrer"><span className="source-index">{String(i + 1).padStart(2, '0')}</span><div><strong>{domain(source)}</strong><p>{source}</p></div><ExternalLink size={15}/></a>)}</div>}
          {tab === 'activity' && <ActivityLog report={report}/>}
          <div className="results-footer"><ShieldCheck size={14}/><span>AI-extracted from live websites. Missing details stay missing. Verify critical claims at the source.</span></div></section>
          <ReportAnalytics key={report.id} companies={report.companies} active={active}/>
          <StrategyLab key={report.id} companies={report.companies}/>
          {!active && <WeeklyUpdates key={`weekly-${report.id}`} reportId={report.id} publicReport={report.access_mode!=='vault'}/>}
          </>}
          {!active && <ResearchTools tools={report.tools} runs={report.runs.length} active={active}/>}
          {!report.companies.length && <section className="surface standalone-log"><div className="section-heading"><h2>Live research log</h2><span className="subtle">Straight from the agent</span></div><ActivityLog report={report}/></section>}
        </> : <>
          <div className="section-heading workflow-heading"><div><h2>From URL to understanding.</h2><p>Your research team, without the busywork.</p></div><span className="subtle">ONE URL. A WIDER PERSPECTIVE.</span></div>
          <div className="workflow-grid">{[{ icon: Globe2, number: '01', title: 'Meet the company', text: 'Explore its website to understand the product, positioning, and who it serves.', color: 'peach' }, { icon: Compass, number: '02', title: 'Find the alternatives', text: 'Discover up to three relevant competitors, then visit their sites for the details.', color: 'lavender' }, { icon: Layers3, number: '03', title: 'See the full picture', text: 'Compare products, pricing, and differentiation. Trace every insight to its source.', color: 'mint' }].map(s => <article className="workflow-card surface" key={s.number}><div className="workflow-top"><span className={`workflow-icon ${s.color}`}><s.icon size={22}/></span><span>{s.number}</span></div><h3>{s.title}</h3><p>{s.text}</p></article>)}</div>
          <section className="empty-landscape surface"><div className="landscape-art" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="orbit-line line-one"/><div className="orbit-line line-two"/><div className="art-node node-a"><Layers3 size={17}/></div><div className="art-node node-b"><Target size={17}/></div><div className="art-center"><Search size={25}/></div><div className="art-node node-c"><Globe2 size={17}/></div><span className="art-spark spark-one"/><span className="art-spark spark-two"/></div><div><span className="eyebrow muted">LESS SEARCHING. MORE KNOWING.</span><h2>Your next move starts here.</h2><p>Add a company URL above. We’ll turn the open web<br className="desktop-break"/> into a clear view of your competitive landscape.</p><div className="empty-tags"><span><Check size={13}/> Real-time research</span><span><Check size={13}/> Source-backed findings</span><span><Check size={13}/> No guesswork</span></div></div></section>
          {successful.length > 0 && <div className="saved-demo"><Clock3 size={17}/><p>Short on time? Revisit an actual completed report.</p><button onClick={() => loadReport(successful[0].id)}>Open {successful[0].name || domain(successful[0].url)} <ArrowRight size={14}/></button></div>}
        </>}
        </>}
        <footer className="page-footer"><span><Logo small/> Signal is your starting point for a smarter strategy.</span><span>Built with <strong>TinyFish</strong><span className="footer-dot">·</span>Hackathon 2026</span></footer>
      </main>
    </div>
    {showGuide && <div className="modal-backdrop" onClick={e => { if (e.target === e.currentTarget) setShowGuide(false); }}><section ref={modalRef} className="guide-modal" role="dialog" aria-modal="true" aria-labelledby="guide-title"><button className="modal-close" autoFocus onClick={() => setShowGuide(false)} aria-label="Close guide"><X size={20}/></button><span className="workflow-icon peach"><BookOpen size={23}/></span><h2 id="guide-title">Meet your research assistant.</h2><p>Signal sends a public website to TinyFish’s live web agent. It researches the company, discovers alternatives, and visits each competitor’s website.</p><ol><li><strong>Connect TinyFish.</strong> Put your key in <code>TINYFISH_API_KEY</code> in the project’s <code>.env</code> file. It stays on the Python server.</li><li><strong>Enter a company URL.</strong> Choose one to three competitors. Research can take several minutes and uses TinyFish wallet funds.</li><li><strong>Follow the evidence.</strong> Compare findings, open their sources, and download your report as JSON.</li></ol><div className="guide-callout"><ShieldCheck size={18}/><p>Nothing is prefilled or invented. “Not found” means the agent couldn’t substantiate that detail. Saved reports show when the live research happened.</p></div><button className="primary-button" onClick={() => setShowGuide(false)}>Let’s explore <ArrowRight size={16}/></button></section></div>}
  </div>;
}

function ActivityLog({ report }: { report: Report }) { return <div className="activity-panel" role="tabpanel">{report.events.length === 0 && <p className="panel-intro">Waiting for the research agent to connect…</p>}{report.events.map((e, i) => <div className={`activity-row event-${e.kind}`} key={i}><span className="event-dot"/><time>{new Date(e.at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time><div>{e.company && <strong>{domain(e.company)}</strong>}<p>{e.message}</p></div></div>)}{report.runs.length > 0 && <div className="run-links"><span>TINYFISH RUNS</span>{report.runs.map(run => <a href={run.url} key={run.id} target="_blank" rel="noopener noreferrer">{domain(run.company)}<ExternalLink size={12}/></a>)}</div>}</div>; }

