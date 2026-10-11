import { useState } from 'react';
import { ArrowUpRight, BarChart3, Check, CircleHelp, Grid2X2, MousePointer2 } from 'lucide-react';

const dimensions = [
  ['positioning', 'Positioning'], ['products', 'Products'], ['pricing', 'Pricing'],
  ['customers', 'Customers'], ['differentiation', 'Difference'],
] as const;
type Dimension = typeof dimensions[number][0];
type Finding = { text: string | null; sources: string[] };
type Profile = Record<Dimension, Finding> & { name: string; website: string; role: string };
const colors = ['#d58c65', '#8d91bd', '#70a68f', '#74a5bb'];
const supported = (finding: Finding) => Boolean(finding.text?.trim() && finding.sources.length);
const uniqueSources = (company: Profile) => [...new Set(dimensions.flatMap(([key]) => supported(company[key]) ? company[key].sources : []))];

export default function ReportAnalytics({ companies, active }: { companies: Profile[]; active: boolean }) {
  const [selected, setSelected] = useState<{ website: string; dimension: Dimension } | null>(null);
  const [showPricing, setShowPricing] = useState(false);
  const total = companies.length * dimensions.length;
  const covered = companies.reduce((sum, company) => sum + dimensions.filter(([key]) => supported(company[key])).length, 0);
  const coverage = total ? Math.round(covered / total * 100) : 0;
  const counts = companies.map(company => uniqueSources(company).length);
  const axisMax = Math.max(4, Math.ceil(Math.max(0, ...counts) / 4) * 4);
  const selectedCompany = companies.find(company => company.website === selected?.website) || companies[0];
  const selectedDimension = selected?.dimension || 'positioning';
  const finding = selectedCompany[selectedDimension];
  const circleLength = 2 * Math.PI * 48;

  return <section className="analytics-section" aria-labelledby="analytics-heading">
    <div className="section-heading analytics-heading"><div><span className="eyebrow muted">PATTERNS IN THE RESEARCH</span><h2 id="analytics-heading">Your landscape, visualized.</h2><p>Explore the evidence behind your comparison.</p></div><span className="analytics-live"><BarChart3 size={14}/>{active ? 'Updates as profiles arrive' : 'Calculated from this report'}</span></div>
    <div className="analytics-top-grid">
      <article className="surface chart-card source-chart">
        <div className="chart-heading"><div><h3>Source depth by company</h3><p>Distinct pages cited across the five research dimensions</p></div><BarChart3 size={18}/></div>
        <div className="source-bars" role="img" aria-label={`Distinct cited pages: ${companies.map((c, i) => `${c.name}: ${counts[i]}`).join('; ')}. More sources does not indicate a stronger product.`}>
          {companies.map((company, i) => <div className="source-bar-row" key={company.website}><div className="bar-company"><span style={{ background: colors[i % colors.length] }}/><span>{company.name}</span>{company.role === 'target' && <small>YOU</small>}</div><div className="source-bar-track"><div className="source-bar-fill" style={{ width: `${counts[i] / axisMax * 100}%`, background: colors[i % colors.length] }}/></div><strong>{counts[i]}<span className="sr-only"> cited pages</span></strong></div>)}
          <div className="bar-axis"><span/><div>{[0, 1, 2, 3, 4].map(tick => <span key={tick}>{axisMax * tick / 4}</span>)}</div><span/></div>
          <p className="axis-title">Distinct source pages</p>
        </div>
        <p className="chart-footnote">Each URL is counted once per company. This measures research depth, not market share or product quality.</p>
      </article>
      <article className="surface chart-card coverage-chart">
        <div className="chart-heading"><div><h3>Research coverage</h3><p>How much of the comparison has evidence?</p></div></div>
        <div className="coverage-body"><div className="coverage-donut"><svg viewBox="0 0 120 120" role="img" aria-label={`${covered} of ${total} research fields have cited findings; ${total - covered} are unavailable.`}><circle className="donut-track" cx="60" cy="60" r="48" fill="none" strokeWidth="10"/><circle cx="60" cy="60" r="48" fill="none" stroke="#7fa894" strokeWidth="10" strokeDasharray={`${circleLength * covered / (total || 1)} ${circleLength}`} transform="rotate(-90 60 60)"/></svg><div><strong>{coverage}%</strong><span>fields sourced</span></div></div><div className="coverage-legend"><div><span className="legend-dot sourced"/><span>Sourced fields</span><strong>{covered}</strong></div><div><span className="legend-dot missing"/><span>Not found</span><strong>{total - covered}</strong></div><p>{companies.length} profiles × 5 dimensions</p></div></div>
        <p className="chart-footnote">Coverage indicates citation presence, not factual accuracy. {active ? 'Profiles still being researched are excluded.' : 'Failed profiles are excluded.'}</p>
      </article>
    </div>
    <article className="surface evidence-chart">
      <div className="chart-heading"><div><h3>Evidence map</h3><p>See where the research is supported, then inspect any finding.</p></div><span className="interaction-hint"><MousePointer2 size={13}/> Select a cell</span></div>
      <div className="evidence-layout"><div className="evidence-matrix-scroll"><table className="evidence-matrix"><caption className="sr-only">Number of distinct cited pages for each company and research dimension. Select a cell to read the finding and its sources.</caption><thead><tr><th scope="col">Company</th>{dimensions.map(([key, label]) => <th scope="col" key={key}>{label}</th>)}</tr></thead><tbody>{companies.map((company, i) => <tr key={company.website}><th scope="row"><span className="matrix-company"><span style={{ background: colors[i % colors.length] }}/>{company.name}</span></th>{dimensions.map(([key, label]) => {
        const count = supported(company[key]) ? new Set(company[key].sources).size : 0;
        const isSelected = selectedCompany.website === company.website && selectedDimension === key;
        return <td key={key}><button className={`evidence-cell density-${Math.min(count, 3)} ${isSelected ? 'cell-selected' : ''}`} onClick={() => setSelected({ website: company.website, dimension: key })} aria-pressed={isSelected} aria-label={`${company.name}, ${label}: ${count ? `${count} cited ${count === 1 ? 'page' : 'pages'}` : 'Not found'}. Show finding.`}>{count || '—'}</button></td>;
      })}</tr>)}</tbody></table><div className="matrix-legend"><span><i className="density-0"/>Not found</span><span><i className="density-1"/>1 page</span><span><i className="density-2"/>2 pages</span><span><i className="density-3"/>3+ pages</span></div></div>
      <div className="evidence-detail" aria-live="polite"><span className="eyebrow muted">SELECTED FINDING</span><h4>{selectedCompany.name}</h4><span className="detail-dimension">{dimensions.find(([key]) => key === selectedDimension)?.[1]}</span>{supported(finding) ? <><p>{finding.text}</p><div className="analytics-sources">{[...new Set(finding.sources)].map((url, i) => <a key={url} href={url} target="_blank" rel="noopener noreferrer"><span>{i + 1}</span>{new URL(url).hostname.replace(/^www\./, '')}<ArrowUpRight size={12}/></a>)}</div></> : <div className="missing-finding"><CircleHelp size={19}/><p>No source-backed finding was available. This is a research gap, not evidence that the company lacks this capability.</p></div>}</div></div>
    </article>
    <article className="surface pricing-visual"><div className="chart-heading"><div><h3>Pricing evidence at a glance</h3><p>Original pricing details, with currency, billing terms, and limits preserved.</p></div><button className="secondary-button" onClick={() => setShowPricing(!showPricing)} aria-expanded={showPricing}>{showPricing ? 'Collapse pricing' : 'Compare pricing'}<Grid2X2 size={14}/></button></div>
      <div className="pricing-evidence-grid">{companies.map((company, i) => <div className="pricing-evidence-card" key={company.website} style={{ borderTopColor: colors[i % colors.length] }}><div className="pricing-company"><span className="company-monogram" style={{ color: colors[i % colors.length] }}>{company.name[0]}</span><h4>{company.name}</h4></div><span className={`pricing-evidence-status ${supported(company.pricing) ? '' : 'unavailable'}`}>{supported(company.pricing) ? <Check size={13}/> : <CircleHelp size={13}/>} {supported(company.pricing) ? 'Pricing information found' : 'Pricing not found'}</span>{showPricing && <><p>{supported(company.pricing) ? company.pricing.text : 'No public pricing could be substantiated during this research run.'}</p><div className="analytics-sources">{company.pricing.sources.map((url, j) => <a href={url} key={url} target="_blank" rel="noopener noreferrer">Source {j + 1}<ArrowUpRight size={12}/></a>)}</div></>}</div>)}</div><p className="chart-footnote">Plans can use different currencies, traffic limits, seats, and billing periods. These summaries are not normalized into a price ranking.</p>
    </article>
  </section>;
}
