import { useEffect, useRef, useState } from 'react';
import { ExternalLink, LockKeyhole, RefreshCw, ShieldCheck } from 'lucide-react';

export type VaultOptions = { use_vault: boolean; credential_item_ids: string[]; authorize_portal: boolean };
export const PUBLIC_ACCESS: VaultOptions = { use_vault: false, credential_item_ids: [], authorize_portal: false };
type Item = { id: string; label: string; domain: string; has_totp: boolean };

export default function VaultAccess({ url, value, onChange, disabled }: { url: string; value: VaultOptions; onChange: (value: VaultOptions) => void; disabled: boolean }) {
  const [items, setItems] = useState<Item[]>([]);
  const [loadedFor, setLoadedFor] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const request = useRef(0);
  useEffect(() => { request.current++; setItems([]); setLoadedFor(''); setError(''); setLoading(false); }, [url]);

  async function load() {
    const current = ++request.current;
    setLoading(true); setError(''); setItems([]); setLoadedFor('');
    onChange({ ...value, credential_item_ids: [], authorize_portal: false });
    try {
      const response = await fetch(`/api/vault/items?url=${encodeURIComponent(url.trim())}`);
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not load Vault credentials.');
      if (current === request.current) { setItems(data.items); setLoadedFor(url); }
    } catch (e) { if (current === request.current) setError((e as Error).message); }
    finally { if (current === request.current) setLoading(false); }
  }

  return <div className={`vault-access ${value.use_vault ? 'vault-expanded' : ''}`}>
    <label className="vault-toggle"><input type="checkbox" checked={value.use_vault} disabled={disabled} onChange={e => onChange({ ...PUBLIC_ACCESS, use_vault: e.target.checked })}/><LockKeyhole size={15}/><span>Use TinyFish Vault for this portal</span><small>Optional · gated content</small></label>
    {value.use_vault && <div className="vault-panel">
      <p>Sign in to the target website with a credential from your connected Vault. Competitors are researched publicly in separate sessions.</p>
      <div className="vault-actions"><button type="button" className="secondary-button" disabled={disabled || loading || !url.trim()} onClick={load}><RefreshCw size={13} className={loading ? 'spin' : ''}/>{loading ? 'Checking Vault…' : 'Load matching credentials'}</button><a href="https://docs.tinyfish.ai/vault-setup" target="_blank" rel="noopener noreferrer">Connect your password manager <ExternalLink size={12}/></a></div>
      {error && <p className="vault-error" role="alert">{error}</p>}
      {loadedFor === url && !items.length && <p className="vault-empty" role="status">No matching credentials. Connect your password manager in TinyFish Settings → Vault, add this website to the credential, sync there, then reload this list.</p>}
      {loadedFor === url && items.length > 0 && <><label className="vault-select">Credential for this website<select disabled={disabled} value={value.credential_item_ids[0] || ''} onChange={e => onChange({ ...value, credential_item_ids: e.target.value ? [e.target.value] : [], authorize_portal: false })}><option value="">Choose a credential</option>{items.map(item => <option value={item.id} key={item.id}>{item.label} · {item.domain}{item.has_totp ? ' · TOTP available' : ''}</option>)}</select></label><label className="vault-consent"><input type="checkbox" checked={value.authorize_portal} disabled={disabled || !value.credential_item_ids.length} onChange={e => onChange({ ...value, authorize_portal: e.target.checked })}/><span>I’m authorized to access this portal and allow TinyFish to sign in with the selected credential for this read-only research run. The report may contain gated information and will be saved locally.</span></label></>}
      <div className="vault-note"><ShieldCheck size={14}/><span>Passwords stay in TinyFish’s Vault flow. Hardware-key or push MFA and some SSO flows are unsupported. No bypass of access controls or paid upgrades.</span></div>
    </div>}
  </div>;
}
