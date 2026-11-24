// SKIN-RR2 Part C: P0 Style Editor for AlwaysAppliedStyleSheet ("Injected styles").
// Lists custom classes & CSS variables targeting AlwaysAppliedStyleSheet, edits USS with
// live `uss.diagnostics`, inspects per-class reach via `layouts.class_usage`, previews
// cascade via `render.layout`, exports through both native & bundle routes, and imports
// rules/variables from an inspected skin tagged with Source + personal-use notice.

import { useCallback, useEffect, useState } from 'react'
import { rpc, RpcError } from './engine'
import type { RNode, RResult } from './Render'

interface SourceTag {
  skin?: string
  version?: string
}

interface InjectedClass {
  name: string
  rules: number
  selectors: string[]
  source?: SourceTag | null
}

interface InjectedVariable {
  name: string
  value: string
  scope: string
  source?: SourceTag | null
}

interface InjectedState {
  project: string
  sheet: string
  file: string
  header_note?: string
  uss_text: string
  classes: InjectedClass[]
  variables: InjectedVariable[]
  rules: {
    index: number
    selector: string
    classes: string[]
    props: Record<string, string>
    op?: string | null
    source?: SourceTag | null
    source_tag?: string
    reach?: number | null
    zero_reach_warning?: string | null
    uss_text: string
  }[]
}

interface UssDiag {
  line: number
  col: number
  end_col: number
  severity: string
  code: string
  message: string
  suggest?: string
}

interface ClassReach {
  class: string
  layouts: { bundle: string; name: string; path_id: string; elements: number; uses: number }[]
  rules: { sheet: string; selector: string; props: Record<string, string> }[]
}

interface SkinDefsResult {
  skin_dir: string
  sheet: string
  source: { name: string; version: string; label: string }
  personal_use_notice: string
  variables_total: number
  rules_total: number
  variables: { name: string; value: string; is_new: boolean; uss_text: string }[]
  rules: { selector: string; classes: string[]; props: Record<string, string>; is_new: boolean; uss_text: string }[]
}

function sourceText(src?: SourceTag | null): string | null {
  if (!src?.skin) return null
  return src.version ? `${src.skin} v${src.version}` : src.skin
}

function collectMatchedRules(nodes: RNode[]): { element: string; sheet: string; selector: string; specificity: number; origin?: { file: string; selector: string } }[] {
  const out: { element: string; sheet: string; selector: string; specificity: number; origin?: { file: string; selector: string } }[] = []
  const stack = [...(nodes || [])]
  while (stack.length && out.length < 80) {
    const n = stack.shift()!
    const elLabel = n.type + (n.name ? '#' + n.name : '') + (n.classes || []).map((c) => '.' + c).join('')
    for (const m of n.matched || []) {
      if (m.sheet === 'AlwaysAppliedStyleSheet' || m.origin) {
        out.push({ element: elLabel, sheet: m.sheet, selector: m.selector, specificity: m.specificity, origin: m.origin })
      }
    }
    for (const c of n.children || []) stack.push(c)
  }
  return out
}

export default function InjectedStyles({
  project,
  say,
  onChanged,
  onExportNative,
  onBuildBundles,
}: {
  project: string | null
  say: (s: string) => void
  onChanged?: () => void
  onExportNative?: () => void
  onBuildBundles?: () => void
}) {
  const [data, setData] = useState<InjectedState | null>(null)
  const [text, setText] = useState('')
  const [savedText, setSavedText] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [diags, setDiags] = useState<UssDiag[]>([])
  const [selectedClass, setSelectedClass] = useState<string | null>(null)
  const [reach, setReach] = useState<ClassReach | null>(null)
  const [reachBusy, setReachBusy] = useState(false)

  const [layoutQuery, setLayoutQuery] = useState('LoansTile_4x2')
  const [cascade, setCascade] = useState<RResult | null>(null)
  const [cascadeBusy, setCascadeBusy] = useState(false)

  const [importOpen, setImportOpen] = useState(false)
  const [skinFolder, setSkinFolder] = useState('')
  const [skinFilter, setSkinFilter] = useState('')
  const [skinDefs, setSkinDefs] = useState<SkinDefsResult | null>(null)
  const [skinBusy, setSkinBusy] = useState(false)
  const [importNotice, setImportNotice] = useState('')

  const load = useCallback(async () => {
    if (!project) { setData(null); setText(''); setSavedText(''); return }
    setErr('')
    try {
      const r = await rpc<InjectedState>('styles.injected_get', { project })
      setData(r)
      setText(r.uss_text)
      setSavedText(r.uss_text)
      if (r.uss_text) {
        const d = await rpc<{ diagnostics: UssDiag[] }>('uss.diagnostics', { text: r.uss_text, sheet: 'AlwaysAppliedStyleSheet' }).catch(() => ({ diagnostics: [] }))
        setDiags(d.diagnostics || [])
      } else {
        setDiags([])
      }
      if (r.classes.length && !selectedClass) {
        setSelectedClass(r.classes[0].name)
      }
    } catch (e) {
      setErr(e instanceof RpcError ? e.message : String(e))
    }
  }, [project, selectedClass])

  useEffect(() => { load() }, [project]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!selectedClass) { setReach(null); return }
    let live = true
    setReachBusy(true)
    rpc<ClassReach>('layouts.class_usage', { class: selectedClass })
      .then((r) => { if (live) setReach(r) })
      .catch(() => { if (live) setReach(null) })
      .finally(() => { if (live) setReachBusy(false) })
    return () => { live = false }
  }, [selectedClass])

  useEffect(() => {
    if (!project) return
    const t = setTimeout(() => {
      rpc<{ diagnostics: UssDiag[] }>('uss.diagnostics', { text, sheet: 'AlwaysAppliedStyleSheet' })
        .then((d) => setDiags(d.diagnostics || []))
        .catch(() => {})
    }, 350)
    return () => clearTimeout(t)
  }, [project, text])

  const saveUss = async () => {
    if (!project || busy) return
    setBusy(true); setErr('')
    try {
      const r = await rpc<{ diagnostics: UssDiag[]; problems: { message: string }[]; injected: InjectedState }>('styles.injected_save', { project, text })
      setDiags(r.diagnostics || [])
      setData(r.injected)
      setSavedText(text)
      if (r.problems?.length) {
        setErr(r.problems.map((p) => p.message).join('; '))
      } else {
        say('saved AlwaysAppliedStyleSheet.uss')
      }
      onChanged?.()
    } catch (e) {
      setErr(e instanceof RpcError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const runCascadePreview = async (target?: { bundle?: string; path_id?: string; name?: string }) => {
    if (cascadeBusy) return
    const layName = target?.name || layoutQuery.trim()
    if (!layName && !(target?.bundle && target?.path_id)) return
    setCascadeBusy(true); setErr('')
    try {
      const params: Record<string, unknown> = { project: project || undefined, skin: true, depth: 3 }
      if (target?.bundle && target?.path_id) {
        params.bundle = target.bundle
        params.path_id = target.path_id
      } else {
        params.name = layName
      }
      const r = await rpc<RResult>('render.layout', params)
      setCascade(r)
      if (layName) setLayoutQuery(layName)
      say(`cascade previewed ${r.layout}`)
    } catch (e) {
      setErr(e instanceof RpcError ? e.message : String(e))
    } finally {
      setCascadeBusy(false)
    }
  }

  const scanSkin = async () => {
    const f = skinFolder.trim()
    if (!f || skinBusy) return
    setSkinBusy(true); setErr('')
    try {
      const r = await rpc<SkinDefsResult>('skin.style_definitions', { folder: f, q: skinFilter.trim(), limit: 100 })
      setSkinDefs(r)
    } catch (e) {
      setErr(e instanceof RpcError ? e.message : String(e))
    } finally {
      setSkinBusy(false)
    }
  }

  const importFromSkin = async (kind: 'class' | 'variable', name: string, selector?: string) => {
    if (!project || !skinDefs || skinBusy) return
    setSkinBusy(true); setErr('')
    try {
      const r = await rpc<{ source: { name: string; version: string; label: string }; notice: string; injected: InjectedState }>('styles.import_from_skin', {
        project,
        folder: skinDefs.skin_dir,
        kind,
        name,
        selector,
      })
      setData(r.injected)
      setText(r.injected.uss_text)
      setSavedText(r.injected.uss_text)
      setImportNotice(r.notice)
      if (kind === 'class') setSelectedClass(name)
      say(`imported ${kind} ${name} from ${r.source.label}`)
      onChanged?.()
    } catch (e) {
      setErr(e instanceof RpcError ? e.message : String(e))
    } finally {
      setSkinBusy(false)
    }
  }

  const appendTemplate = (snippet: string) => {
    setText((prev) => (prev && !prev.endsWith('\n') ? prev + '\n' : prev) + snippet)
  }

  const dirty = text !== savedText
  const matchedAlways = cascade ? collectMatchedRules(cascade.tree || []) : []

  if (!project) {
    return (
      <div className="injectedstyles pad" data-testid="injected-styles">
        <b>Injected styles · AlwaysAppliedStyleSheet</b>
        <p className="dim small">Open or create a project first to edit custom classes and CSS variables injected into AlwaysAppliedStyleSheet.</p>
      </div>
    )
  }

  return (
    <div className="injectedstyles" data-testid="injected-styles">
      <div className="injectedstyles-top">
        <b>Injected styles</b>
        <span className="badge st ok">AlwaysAppliedStyleSheet</span>
        <span className="small dim">Project: <b>{project}</b>{dirty ? ' • unsaved' : ''}</span>
        <span className="grow" />
        <button type="button" onClick={() => appendTemplate(':root {\n    --my-accent: #3B8FE1;\n}\n')}>+ Variable</button>
        <button type="button" onClick={() => appendTemplate('.my-custom-card {\n    background-color: var(--my-accent);\n    border-radius: 6px;\n}\n')}>+ Class rule</button>
        <button type="button" data-testid="injected-open-import" className={importOpen ? 'on' : ''} onClick={() => setImportOpen((v) => !v)}>
          Import from inspected skin
        </button>
        <button type="button" className="primary" data-testid="injected-save" disabled={busy} onClick={saveUss}>
          {busy ? 'Saving ...' : 'Save & check'}
        </button>
        <div className="injectedstyles-export" data-testid="injected-export-bar">
          {onExportNative && (
            <button type="button" data-testid="injected-export-native" onClick={onExportNative} title="Export rules.uss / tokens.uss for FM27 native skin loading">
              Export native
            </button>
          )}
          {onBuildBundles && (
            <button type="button" data-testid="injected-build-bundles" onClick={onBuildBundles} title="Build modified ui-styles_assets_default.bundle with AlwaysAppliedStyleSheet">
              Build bundles
            </button>
          )}
        </div>
      </div>

      {err && <div className="warn pad small" role="alert" data-testid="injected-error">{err}</div>}
      {importNotice && <div className="note pad small" data-testid="injected-import-toast">{importNotice}</div>}

      <div className="injectedstyles-body">
        <aside className="injectedstyles-side">
          <div className="head">CUSTOM CLASSES ({data?.classes.length ?? 0})</div>
          <ul data-testid="injected-classes-list">
            {(data?.classes || []).map((c) => {
              const s = sourceText(c.source)
              return (
                <li key={c.name} data-testid="injected-class-row"
                  className={selectedClass === c.name ? 'sel' : ''}
                  title={`.${c.name} · ${c.rules} rule(s)${s ? ' · Source: ' + s : ''}`}
                  onClick={() => setSelectedClass(c.name)}>
                  <div className="injectedstyles-row-main">
                    <span className="mono">.{c.name}</span>
                    <small className="dim">{c.rules}</small>
                  </div>
                  {s && <span className="skininspect-source" data-testid="injected-source-badge">Source: {s}</span>}
                </li>
              )
            })}
            {!data?.classes.length && <li className="dim small">No custom classes yet.</li>}
          </ul>

          <div className="head">VARIABLES ({data?.variables.length ?? 0})</div>
          <ul data-testid="injected-vars-list">
            {(data?.variables || []).map((v, i) => {
              const s = sourceText(v.source)
              return (
                <li key={`${v.name}:${v.scope}:${i}`} data-testid="injected-var-row"
                  title={`${v.name}: ${v.value} (${v.scope})${s ? ' · Source: ' + s : ''}`}>
                  <div className="injectedstyles-row-main">
                    <span className="mono">{v.name}</span>
                    <small className="mono dim">{v.value}</small>
                  </div>
                  <div className="small dim">
                    {v.scope}{s && <> · <span className="skininspect-source" data-testid="injected-source-badge">Source: {s}</span></>}
                  </div>
                </li>
              )
            })}
            {!data?.variables.length && <li className="dim small">No variables defined yet.</li>}
          </ul>
        </aside>

        <section className="injectedstyles-editor-col">
          {importOpen && (
            <div className="injectedstyles-import" data-testid="injected-import-panel">
              <div className="warn small pad" data-testid="injected-personal-use-notice">
                Personal use &amp; study only: imported third-party rules and variables are tagged with their Source (skin name and version). Distributing third-party skin content requires the original author&apos;s permission.
              </div>
              <div className="injectedstyles-import-bar">
                <input className="search" data-testid="injected-skin-path" placeholder="Path to inspected skin folder ..."
                  value={skinFolder} onChange={(e) => setSkinFolder(e.target.value)} />
                <input className="search" data-testid="injected-skin-filter" style={{ maxWidth: 200 }} placeholder="Filter class or --var ..."
                  value={skinFilter} onChange={(e) => setSkinFilter(e.target.value)} />
                <button type="button" className="primary" data-testid="injected-skin-scan" disabled={!skinFolder.trim() || skinBusy} onClick={scanSkin}>
                  {skinBusy ? 'Scanning ...' : 'Load styles'}
                </button>
              </div>
              {skinDefs && (
                <div className="injectedstyles-import-lists">
                  <div className="small">
                    <b>Source: {skinDefs.source.label}</b> · {skinDefs.variables_total} variables · {skinDefs.rules_total} rules
                  </div>
                  <div className="injectedstyles-import-grid">
                    <div>
                      <div className="small"><b>Variables</b></div>
                      <div className="injectedstyles-import-scroll">
                        {skinDefs.variables.slice(0, 40).map((v) => (
                          <div key={v.name} className="injectedstyles-imp-row small">
                            <span className="mono" title={`${v.name}: ${v.value}`}>{v.name}: <span className="dim">{v.value}</span></span>
                            <button type="button" className="small" data-testid={`import-var-${v.name}`}
                              disabled={skinBusy} onClick={() => importFromSkin('variable', v.name)}>Import</button>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="small"><b>Classes &amp; rules</b></div>
                      <div className="injectedstyles-import-scroll">
                        {skinDefs.rules.slice(0, 40).map((r, i) => {
                          const cls = r.classes[0] || r.selector
                          return (
                            <div key={`${r.selector}:${i}`} className="injectedstyles-imp-row small">
                              <span className="mono" title={r.uss_text}>{r.selector}</span>
                              <button type="button" className="small" data-testid={`import-class-${cls}`}
                                disabled={skinBusy || !r.classes.length}
                                onClick={() => importFromSkin('class', cls, r.selector)}>Import</button>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="head">USS EDITOR · styles/AlwaysAppliedStyleSheet.uss</div>
          {data?.header_note && (
            <div className="small dim pad" data-testid="injected-header-note">{data.header_note}</div>
          )}
          <textarea className="injectedstyles-textarea mono" data-testid="injected-uss-editor"
            spellCheck={false}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="/* Write CSS variables under :root { --name: value; } and classes for AlwaysAppliedStyleSheet */" />

          <div className="head">DIAGNOSTICS ({diags.length})</div>
          <div className="injectedstyles-diags" data-testid="injected-diagnostics">
            {diags.map((d, i) => (
              <div key={i} className="injectedstyles-diag-row small">
                <span className={'badge st ' + (d.severity === 'error' ? 'bad' : d.severity === 'warning' ? 'warn' : 'dim')}>{d.severity}</span>{' '}
                <span className="mono">L{d.line}:{d.col}</span> [{d.code}] {d.message}
              </div>
            ))}
            {!diags.length && <div className="dim small">No USS diagnostics reported.</div>}
          </div>

          <div className="head">RULES ({data?.rules.length ?? 0})</div>
          <div className="injectedstyles-diags" data-testid="injected-rules-list">
            {(data?.rules || []).map((r) => (
              <div key={r.index} className="injectedstyles-diag-row small" data-testid="injected-rule-row">
                <span className="mono">{r.selector}</span>{' '}
                {r.source_tag && <span className="skininspect-source" data-testid="injected-rule-source">{r.source_tag}</span>}{' '}
                {r.reach !== undefined && r.reach !== null && (
                  <span className="badge st" data-testid="injected-rule-reach">reach: {r.reach}</span>
                )}{' '}
                {r.zero_reach_warning && (
                  <span className="badge st warn" data-testid="injected-zero-reach-warn">{r.zero_reach_warning}</span>
                )}
              </div>
            ))}
          </div>
        </section>

        <section className="injectedstyles-preview-col">
          <div className="head">PER-CLASS REACH {selectedClass ? `( .${selectedClass} )` : ''}</div>
          <div className="injectedstyles-reach" data-testid="injected-reach">
            {reachBusy && <div className="dim small">Checking layout &amp; rule usage ...</div>}
            {!reachBusy && reach && (
              <>
                <div className="small">
                  <b>{reach.layouts.length}</b> UXML layout(s) · <b>{reach.rules.length}</b> game rule(s)
                </div>
                {reach.layouts.slice(0, 15).map((l) => (
                  <div key={`${l.bundle}:${l.path_id}`} className="injectedstyles-reach-row small">
                    <span className="mono" title={`${l.name} (${l.bundle})`}>{l.name}</span>
                    <span className="dim">{l.uses} use(s)</span>
                    <button type="button" className="small" onClick={() => runCascadePreview({ bundle: l.bundle, path_id: l.path_id, name: l.name })}>
                      Preview cascade
                    </button>
                  </div>
                ))}
                {!reach.layouts.length && <div className="dim small">No stock UXML layout carries .{reach.class} (used by custom/skinned UXML or runtime).</div>}
              </>
            )}
            {!reachBusy && !reach && <div className="dim small">Pick a class on the left to inspect its reach.</div>}
          </div>

          <div className="head">CASCADE PREVIEW (render.layout)</div>
          <div className="injectedstyles-cascade-bar">
            <input className="search" data-testid="injected-layout-input" placeholder="Layout name (e.g. LoansTile_4x2) ..."
              value={layoutQuery} onChange={(e) => setLayoutQuery(e.target.value)} />
            <button type="button" className="primary" data-testid="injected-preview-btn" disabled={cascadeBusy} onClick={() => runCascadePreview()}>
              {cascadeBusy ? 'Rendering ...' : 'Preview cascade'}
            </button>
          </div>
          <div className="injectedstyles-cascade" data-testid="injected-cascade-preview">
            {cascade ? (
              <>
                <div className="small">
                  <b>{cascade.layout}</b> · {cascade.summary.elements} elements · {cascade.origins?.rules?.length ?? 0} skin rule hit(s)
                </div>
                {cascade.origins?.rules?.map((o, i) => (
                  <div key={i} className="injectedstyles-origin small">
                    <span className="badge st ok">{o.sheet}</span> <span className="mono">{o.selector}</span> <span className="dim">({o.file}:{o.line ?? '?'})</span>
                  </div>
                ))}
                {matchedAlways.length > 0 && (
                  <div className="injectedstyles-matches">
                    {matchedAlways.slice(0, 20).map((m, i) => (
                      <div key={i} className="small mono dim">
                        {m.element} ← {m.selector} [{m.sheet}, spec {m.specificity}]
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="dim small">Click &quot;Preview cascade&quot; to resolve computed rules and origins from AlwaysAppliedStyleSheet.</div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
