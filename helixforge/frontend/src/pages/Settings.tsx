import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Empty, ErrorNote, Field, PageHeader, Panel, Spinner } from '@/components/ui'

interface FieldDef { key: string; label: string; type: 'password' | 'text' | 'number'; hint: string; secret?: boolean }
const FIELDS: FieldDef[] = [
  { key: 'ncbi_api_key', label: 'NCBI API Key', type: 'password', hint: 'Optional. Raises PubMed rate limits. Stored server-side, never echoed back.', secret: true },
  { key: 'ncbi_email', label: 'NCBI Email', type: 'text', hint: 'Recommended by NCBI E-utilities usage policy.' },
  { key: 'reinvent4_python', label: 'REINVENT4 Python', type: 'text', hint: 'Path to the Python interpreter of a REINVENT4 install.' },
  { key: 'reinvent4_bin', label: 'REINVENT4 Bin', type: 'text', hint: 'Path to the REINVENT4 entrypoint (alternative to the Python path).' },
  { key: 'vina_bin', label: 'AutoDock Vina Bin', type: 'text', hint: 'Path/name of the vina executable (default: "vina").' },
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

  async function load() {
    setLoading(true)
    try { const r = await api.getSettings(); setValues(r.values || {}) } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
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

  return (
    <div>
      <PageHeader
        icon={<Icon name="Settings" size={22} />}
        title="Settings"
        subtitle="Configure tool credentials and operational parameters at runtime. Secret values are stored server-side and never returned in full or written to logs."
        actions={<button className="btn-secondary" onClick={load} disabled={loading}><Icon name="RefreshCw" size={14} /> Reload</button>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
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
