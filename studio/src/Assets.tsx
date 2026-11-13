import { useCallback, useEffect, useMemo, useReducer, useState } from 'react'
import { rpc, RpcError } from './engine'
import { commit, initial, isDirty, keyOf, reduce, thumbKey, type Slot, type Stage, type Stored } from './staging'

interface Conflict { severity: 'error' | 'warning' | 'info'; code: string; message: string }
interface Row extends Slot { w: number; h: number; group: string }

const cache = new Map<string, string>()
/** A data: URL for a binary engine method (thumbnails of game images, stored replacements, previews of staged files). */
function useImage(method: string, params: Record<string, unknown>, key: string) {
  const [src, setSrc] = useState<string>(cache.get(key) ?? '')
  useEffect(() => {
    if (cache.has(key)) { setSrc(cache.get(key)!); return }
    setSrc('')                                           // never show the previous picture while the new one loads
    let live = true
    rpc<{ content_type: string; base64: string }>(method, params).then((r) => { const u = `data:${r.content_type};base64,${r.base64}`; cache.set(key, u); if (live) setSrc(u) }).catch(() => {})
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return src
}
// no src until the picture has loaded: an empty src makes the webview request the whole page again
const Game = ({ bundle, id }: { bundle: string; id: string }) => <img className="thumb" src={useImage('images.thumb', { bundle, path_id: id }, `g|${bundle}|${id}`) || undefined} alt="" />
const Yours = ({ project, file, v }: { project: string; file: string; v: number }) => <img className="thumb" src={useImage('images.source', { project, file }, thumbKey(project, file, v)) || undefined} alt="" />
const Staged = ({ path }: { path: string }) => <img className="thumb staged" src={useImage('images.preview_file', { path }, 'p|' + path) || undefined} alt="" />

const pickImage = async (): Promise<string | undefined> => {
  if (!('__TAURI_INTERNALS__' in window)) return prompt('Path of the replacement image (png, jpg, webp or svg):')?.trim() || undefined
  const { open } = await import('@tauri-apps/plugin-dialog')
  const r = await open({ multiple: false, directory: false, title: 'Pick the replacement image', filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'webp', 'svg'] }] })
  return typeof r === 'string' ? r : undefined
}

/** Visual mapping of the project's image swaps. Edits are staged (file, fit, places) and written together by "Override"; "Revert" drops them. */
export default function Assets({ project, onChanged, say }: { project: string; onChanged: () => void; say: (s: string) => void }) {
  const [model, setModel] = useState<any>(null)
  const [st, dispatch] = useReducer(reduce, undefined, initial)
  const [conf, setConf] = useState<Conflict[]>([])
  const [places, setPlaces] = useState<Record<string, string>>({})
  const [catalog, setCatalog] = useState<Row[] | null>(null)
  const [adding, setAdding] = useState(false)
  const [q, setQ] = useState('')
  const [kind, setKind] = useState('all')
  const [err, setErr] = useState('')
  const fail = useCallback((e: unknown) => { const m = e instanceof RpcError ? e.message : String(e); setErr(m); say('ERROR ' + m) }, [say])

  const refreshConflicts = useCallback(() => rpc<{ conflicts: Conflict[] }>('assets.conflicts', { project }).then((r) => setConf(r.conflicts)).catch(() => {}), [project])
  useEffect(() => {
    dispatch({ type: 'reset' }); setErr('')
    rpc<any>('project.get', { name: project }).then(setModel).catch(fail)
    refreshConflicts()
    rpc<{ places: Record<string, string> }>('native.info').then((r) => setPlaces(r.places)).catch(() => {})
  }, [project, fail, refreshConflicts])
  useEffect(() => { if (adding && !catalog) rpc<Row[]>('images.catalog').then(setCatalog).catch(fail) }, [adding, catalog, fail])

  const stored: Stored[] = model?.image_swaps ?? []
  const storedOf = (k: string) => stored.find((e) => keyOf(e) === k)
  // the list: every stored slot, then slots staged from the catalog that are not stored yet
  const slots: Slot[] = useMemo(() => [...stored, ...Object.values(st.staged).map((s) => s.slot).filter((s) => !stored.some((e) => keyOf(e) === keyOf(s)))], [stored, st.staged])
  const target = model?.options?.output
  const dirtyCount = Object.entries(st.staged).filter(([k, s]) => isDirty(s, storedOf(k))).length

  const pick = async (slot: Slot) => { try { const path = await pickImage(); if (path) dispatch({ type: 'stage', slot, patch: { path } }) } catch (e) { fail(e) } }
  const override = async (slot: Slot) => {
    const k = keyOf(slot)
    try {
      const r = await commit((m, p) => rpc(m, p), project, st, k, storedOf(k))
      if (!r.result) return
      setModel(r.result.project); dispatch({ type: 'committed', key: k }); setErr(''); onChanged(); refreshConflicts()
      say(`override saved: ${slot.name || slot.path_id}`)
    } catch (e) { fail(e) }                                 // the staging stays, so nothing is lost
  }
  const remove = async (e: Stored) => {
    try {
      const r = await rpc<any>('images.remove', { project, bundle: e.bundle, path_id: e.path_id })
      setModel(r.project); dispatch({ type: 'revert', key: keyOf(e) }); onChanged(); refreshConflicts(); say(`image swap removed: ${e.name || e.path_id}`)
    } catch (x) { fail(x) }
  }

  // fonts: a font file assigned to a game font-family token; the native export writes the file and a url() rule
  const [fontTokens, setFontTokens] = useState<{ name: string; value?: string }[]>([])
  const [fontToken, setFontToken] = useState('')
  useEffect(() => { rpc<{ tokens: { name: string; value?: string }[] }>('font.tokens').then((r) => { setFontTokens(r.tokens); setFontToken((t) => t || r.tokens[0]?.name || '') }).catch(() => {}) }, [])
  const pickFont = async () => {
    try {
      let path: string | undefined
      if ('__TAURI_INTERNALS__' in window) { const { open } = await import('@tauri-apps/plugin-dialog'); const r = await open({ multiple: false, directory: false, title: 'Pick a font file', filters: [{ name: 'Fonts', extensions: ['ttf', 'otf'] }] }); path = typeof r === 'string' ? r : undefined }
      else path = prompt('Path of the .ttf or .otf file:')?.trim()
      if (!path || !fontToken) return
      const r = await rpc<any>('font.set', { project, token: fontToken, path }); setModel(r.project); onChanged(); say(`font set for ${fontToken}`)
    } catch (e) { fail(e) }
  }
  const removeFont = async (token: string) => { try { const r = await rpc<any>('font.remove', { project, token }); setModel(r.project); onChanged() } catch (e) { fail(e) } }
  const fonts: { token: string; source: string }[] = model?.font_swaps ?? []

  const shown = useMemo(() => (catalog ?? []).filter((r) => (kind === 'all' || r.kind === kind) && (!q.trim() || (r.name ?? '').toLowerCase().includes(q.trim().toLowerCase()))).slice(0, 40), [catalog, q, kind])

  if (!model) return <div className="assets"><div className="head">IMAGES</div>{err ? <div className="warn pad">{err}</div> : <div className="dim pad">Loading ...</div>}</div>
  return (
    <div className="assets">
      <div className="head">IMAGES ({stored.length}){dirtyCount > 0 && <span className="dirty"> ● {dirtyCount} unsaved</span>} <button onClick={() => setAdding(!adding)}>{adding ? 'done' : '+ add'}</button></div>
      {err && <div className="warn pad">{err}</div>}
      {conf.length > 0 && <div className="conf">{conf.map((c, i) => <div key={i} className={'c-' + c.severity} title={c.code}><b>{c.severity}</b> {c.message}</div>)}</div>}
      {slots.length === 0 && !adding && <div className="dim pad">No images replaced yet. Use + add to pick one from the game.</div>}
      {slots.map((slot) => {
        const k = keyOf(slot), s: Stage | undefined = st.staged[k], saved = storedOf(k)
        const dirty = isDirty(s, saved)
        const fitNow = s?.fit ?? saved?.fit ?? 'cover', whereNow = s?.where ?? saved?.where ?? []
        return (
          <div className={'swap' + (dirty ? ' is-dirty' : '')} key={k} data-testid={'slot-' + k}>
            <div className="pair">
              <Game bundle={slot.bundle} id={slot.path_id} /><span>→</span>
              {s?.path ? <Staged path={s.path} /> : saved ? <Yours project={project} file={saved.source} v={st.versions[k] ?? 0} /> : <div className="thumb empty">pick a file</div>}
            </div>
            <div className="meta"><b>{slot.name || slot.path_id}</b> <small>{slot.kind}</small>
              {dirty ? <span className="badge dirty" title="Not written to the project yet">● unsaved</span> : saved ? <span className="badge saved" title="Stored in the project">✓ saved</span> : null}
              {s?.path && <small className="dim"> staged: {s.path.split(/[\\/]/).pop()}</small>}
            </div>
            <div className="ctl">
              {slot.kind !== 'svg' && <select value={fitNow} onChange={(ev) => dispatch({ type: 'stage', slot, patch: { fit: ev.target.value } })} title="How your picture is fitted to the game's"><option>cover</option><option>contain</option><option>stretch</option></select>}
              <button onClick={() => pick(slot)}>{saved || s?.path ? 'pick other file' : 'pick file'}</button>
            </div>
            {slot.kind === 'texture' && target === 'native' && <div className="where">
              {Object.entries(places).map(([pk, label]) => <label key={pk} title={label}><input type="checkbox" checked={whereNow.includes(pk)} onChange={(ev) => dispatch({ type: 'stage', slot, patch: { where: ev.target.checked ? [...whereNow, pk] : whereNow.filter((x) => x !== pk) } })} /> {label.split(' (')[0]}</label>)}
              {!saved?.where && !s?.where && <small className="dim">default places (tick to choose)</small>}
            </div>}
            <div className="ctl">
              <button className="primary" disabled={!dirty} onClick={() => override(slot)} title="Write file, fit and places to the project in one go">Override</button>
              <button disabled={!s} onClick={() => dispatch({ type: 'revert', key: k })} title="Discard the staged changes">Revert</button>
              {saved && <button onClick={() => remove(saved)} title="Remove this replacement from the project">remove</button>}
            </div>
          </div>)
      })}
      <div className="head">FONTS ({fonts.length})</div>
      <div className="pad dim small">Native target: the font file is copied into the skin and the token is set to it with url(). The bundle route needs FontAssets (see docs/PHASE6-FONTS-SPIKE.md).</div>
      {fonts.map((f) => <div key={f.token} className="swap"><b>{f.token}</b> <small>{f.source}</small> <span className="badge saved">✓ saved</span> <button onClick={() => removeFont(f.token)}>remove</button></div>)}
      <div className="pad ctl"><select value={fontToken} onChange={(e) => setFontToken(e.target.value)}>{fontTokens.map((t) => <option key={t.name} value={t.name}>{t.name}</option>)}</select> <button disabled={!fontToken} onClick={pickFont}>pick font file</button></div>
      {adding && <div className="catalog">
        <div className="row"><input className="search" placeholder="Filter by name ..." value={q} onChange={(e) => setQ(e.target.value)} />
          <select value={kind} onChange={(e) => setKind(e.target.value)}><option value="all">all</option><option value="texture">textures</option><option value="icon">icons</option><option value="svg">svg</option></select></div>
        {!catalog && <div className="dim pad">Reading the game's images ...</div>}
        {shown.map((r) => <div className="item" key={r.bundle + r.path_id + r.kind + r.name}>
          <Game bundle={r.bundle} id={r.path_id} /><div className="meta"><b>{r.name}</b><small> {r.kind} {r.w}x{r.h}{r.group ? ' · ' + r.group : ''}</small></div>
          <button onClick={async () => { await pick(r); setAdding(false) }}>stage ...</button></div>)}
        {catalog && shown.length === 40 && <div className="dim pad">Showing the first 40; narrow the filter.</div>}
      </div>}
    </div>
  )
}
