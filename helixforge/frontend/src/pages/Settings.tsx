import { useEffect, useState } from 'react'
import { api, getSessionAuthToken, setSessionAuthToken } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Empty, ErrorNote, PageHeader, Panel, Spinner } from '@/components/ui'

interface FieldDef { key: string; label: string; type: 'password' | 'text' | 'number'; hint: string; secret?: boolean }
const FIELDS: FieldDef[] = [
  { key: 'ncbi_api_key', label: 'NCBI API Key', type: 'password', hint: 'Optional. Raises PubMed rate limits. Stored server-side, never echoed back.', secret: true },
  { key: 'ncbi_email', label: 'NCBI Email', type: 'text', hint: 'Recommended by NCBI E-utilities usage policy.' },
  { key: 'chunk_size', label: 'Chunk Size', type: 'number', hint: 'Pagination/batch size for external API calls.' },
  { key: 'timeout_seconds', label: 'Timeout (seconds)', type: 'number', hint: 'HTTP timeout for external API calls.' },
]

export function Settings() {
  const [values, setValues] = useState<Record<string, any>>({})
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')
  const [savedKeys, setSavedKeys] = useState<string[]>([])
  const [authToken, setAuthToken] = useState('')
  const [hasAuthToken, setHasAuthToken] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const r = await api.getSettings()
      setValues(r.values || {})
      setHasAuthToken(Boolean(getSessionAuthToken()))
      setErr('')
    } catch (e: any) { setHasAuthToken(false); setErr(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  async function save() {
    setSaving(true); setErr(''); setSavedKeys([])
    try {
      const payload: Record<string, any> = {}
      for (const f of FIELDS) {
        const v = inputs[f.key]
        if (v == null || v === '') continue
        payload[f.key] = f.type === 'number' ? Number(v) : v
      }
      const r = await api.updateSettings(payload)
      setSavedKeys(r.applied_keys || [])
      setValues(r.values || {})
      setInputs({})
    } catch (e: any) { setErr(e.message) } finally { setSaving(false) }
  }

  function current(key: string): string {
    const v = values[key]
    if (!v) return ''
    if ('preview' in v) return v.set ? v.preview : '(not set)'
    if ('value' in v) return v.value === '' || v.value == null ? '(not set)' : String(v.value)
    return ''
  }

  async function saveSessionToken() {
    const candidate = authToken.trim()
    if (!setSessionAuthToken(candidate)) {
      setHasAuthToken(false)
      setErr('Session storage is unavailable; the administrator token was not saved.')
      return
    }
    setLoading(true); setErr('')
    try {
      const response = await api.getSettings()
      setValues(response.values || {})
      setHasAuthToken(true)
      setAuthToken('')
    } catch (error: unknown) {
      setSessionAuthToken('')
      setHasAuthToken(false)
      setErr(error instanceof Error ? `Token validation failed: ${error.message}` : 'Token validation failed.')
    } finally { setLoading(false) }
  }

  return (
    <div>
      <PageHeader
        icon={<Icon name="Settings" size={22} />}
        title="Settings"
        subtitle="Configure safe operational parameters and the administrator token used by this browser tab. Executable paths are deployment-only settings and cannot be changed here."
        actions={<button className="btn-secondary" onClick={load} disabled={loading}><Icon name="RefreshCw" size={14} /> Reload</button>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      <Panel className="mb-4 max-w-3xl">
        <div className="grid gap-3 sm:grid-cols-[240px_1fr] sm:items-end">
          <div>
            <div className="text-sm font-medium text-slate-200">Administrator session</div>
            <div className="text-[11px] text-slate-500">The bearer token is kept in session storage, sent to protected APIs, and cleared when this browser tab session ends.</div>
          </div>
          <div className="flex items-center gap-2">
            <input
              className="input"
              type="password"
              autoComplete="off"
              aria-label="Administrator bearer token"
              placeholder={hasAuthToken ? 'Token set for this session' : 'Enter administrator token'}
              value={authToken}
              onChange={(event) => setAuthToken(event.target.value)}
            />
            <button className="btn-secondary" onClick={saveSessionToken} disabled={!authToken.trim() || loading}><Icon name="KeyRound" size={14} /> Set & verify</button>
            {hasAuthToken && <button className="btn-ghost" onClick={() => { setSessionAuthToken(''); setHasAuthToken(false) }}>Clear</button>}
          </div>
        </div>
      </Panel>
      {loading ? <Spinner label="Loading settings…" /> : (
        <Panel className="max-w-3xl">
          <div className="space-y-4">
            {FIELDS.map((f) => (
              <div key={f.key} className="grid gap-2 sm:grid-cols-[240px_1fr] sm:items-center">
                <div>
                  <div className="text-sm font-medium text-slate-200">{f.label}</div>
                  <div className="text-[11px] text-slate-500">{f.hint}</div>
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <input
                      className="input"
                      type={f.type === 'password' ? 'password' : f.type === 'number' ? 'number' : 'text'}
                      placeholder={current(f.key) || `Set ${f.label}…`}
                      value={inputs[f.key] ?? ''}
                      onChange={(e) => setInputs((s) => ({ ...s, [f.key]: e.target.value }))}
                    />
                    {savedKeys.includes(f.key) && <Badge tone="green">saved</Badge>}
                  </div>
                  <div className="mt-1 text-[11px] text-slate-500">Current: <span className="font-mono text-slate-400">{f.secret ? (current(f.key) || '(not set)') : (current(f.key) || '(not set)')}</span></div>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-5 flex items-center gap-3 border-t border-line pt-4">
            <button className="btn-primary" onClick={save} disabled={saving}><Icon name="Save" size={15} /> {saving ? 'Saving…' : 'Save changes'}</button>
            {savedKeys.length > 0 && <span className="text-xs text-brand-300">Applied: {savedKeys.join(', ')}</span>}
          </div>
          <div className="mt-4 rounded-lg border border-line bg-bg-soft/50 p-3 text-xs text-slate-400">
            <Icon name="ShieldCheck" size={13} className="mr-1 inline text-brand-400" />
            Secrets are masked in the API response (only the last 4 characters of the API key are ever shown) and are never logged. Environment variables in <span className="mono">.env</span> provide the defaults; these runtime overrides layer on top.
          </div>
        </Panel>
      )}
      {!loading && Object.keys(values).length === 0 && <div className="mt-4"><Empty>Backend settings endpoint returned no values. Ensure the backend is running.</Empty></div>}
    </div>
  )
}
