import { useEffect, useMemo, useState } from 'react'
import { rpc } from './engine'
import { sayOf, type Said } from './plainError'
import { pickImage } from './pickImage'

/** One of the game's pictures a native skin can replace (engine `simple.pictures`): a wallpaper (painted on the places ticked) or an icon a USS class draws. */
export interface Pic { kind: 'wallpaper' | 'icon'; game_kind: string; bundle: string; path_id: string; name: string; w?: number; h?: number; group?: string; where_default?: string[] }
export interface PicCatalog { rows: Pic[]; counts: { wallpapers: number; icons: number; left_out: number }; places: Record<string, string>; look_at: Record<string, { name: string; label: string }> }
interface Swap { bundle: string; path_id: string; name: string; kind: string; source: string; where?: string[] }

const SHOWN = 40
const cache = new Map<string, string>()
function useBinary(method: string, params: Record<string, unknown>, key: string): string {
  const [src, setSrc] = useState(cache.get(key) ?? '')
  useEffect(() => {
    if (!key) { setSrc(''); return }
    if (cache.has(key)) { setSrc(cache.get(key)!); return }
    setSrc(''); let live = true
    rpc<{ content_type: string; base64: string }>(method, params).then((r) => { const u = `data:${r.content_type};base64,${r.base64}`; cache.set(key, u); if (live) setSrc(u) }).catch(() => {})
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return src
}
const GameThumb = ({ p }: { p: { bundle: string; path_id: string } }) => <img className="thumb" alt="" src={useBinary('images.thumb', { bundle: p.bundle, path_id: p.path_id }, `g|${p.bundle}|${p.path_id}`) || undefined} />
const FileThumb = ({ path }: { path: string }) => <img className="thumb" alt="" src={useBinary('images.preview_file', { path }, path ? 'f|' + path : '') || undefined} />

/** Where Look at it can show this picture: a wallpaper on a place a measured layout covers; otherwise null, and the screen says why. */
export function lookFor(pic: Pic, where: string[], cat: PicCatalog): { name: string; label: string } | null {
  if (pic.kind !== 'wallpaper') return null
  const place = where.find((w) => cat.look_at[w])
  return place ? cat.look_at[place] : null
}

/** Pictures in three steps (S6, Simple mode): choose a picture of the game, pick your own file, tick where it shows (wallpapers), then see it in Look at it. Only pictures a
 *  native skin can replace are offered; every change can be put back. Writes through the same `images.commit` as the Advanced Images view. */
export default function Pictures({ project, say, onChanged, onLook }: { project: string; say: (s: string) => void; onChanged: () => void; onLook: (start: { name: string; label: string } | null) => void }) {
  const [cat, setCat] = useState<PicCatalog | null>(null)
  const [kind, setKind] = useState<'wallpaper' | 'icon'>('wallpaper')
  const [q, setQ] = useState('')
  const [chosen, setChosen] = useState<Pic | null>(null)
  const [file, setFile] = useState('')
  const [where, setWhere] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<Said | null>(null)
  const [swaps, setSwaps] = useState<Swap[]>([])
  const [done, setDone] = useState<{ pic: Pic; where: string[] } | null>(null)

  useEffect(() => {
    rpc<PicCatalog>('simple.pictures').then(setCat).catch((e) => setProblem(sayOf(e)))
    rpc<{ image_swaps?: Swap[] }>('project.get', { name: project }).then((p) => setSwaps(p.image_swaps ?? [])).catch(() => {})
  }, [project])

  const shown = useMemo(() => (cat?.rows ?? []).filter((r) => r.kind === kind && (!q.trim() || r.name.toLowerCase().includes(q.trim().toLowerCase()))), [cat, kind, q])

  const choose = (p: Pic) => { setChosen(p); setFile(''); setWhere(p.where_default ?? []); setDone(null); setProblem(null) }
  const pick = async () => { try { const f = await pickImage(); if (f) setFile(f) } catch (e) { setProblem(sayOf(e)) } }
  const canUse = !!chosen && !!file && !busy && (chosen.kind !== 'wallpaper' || where.length > 0)

  async function use() {
    if (!chosen || !canUse) return
    setBusy(true); setProblem(null)
    try {
      const r = await rpc<{ project: { image_swaps?: Swap[] } }>('images.commit', { project, bundle: chosen.bundle, path_id: chosen.path_id, kind: chosen.game_kind, name: chosen.name, path: file, ...(chosen.kind === 'wallpaper' ? { where } : {}) })
      setSwaps(r.project.image_swaps ?? []); setDone({ pic: chosen, where }); onChanged(); say(`picture replaced: ${chosen.name}`)
    } catch (e) { setProblem(sayOf(e)); say('ERROR ' + sayOf(e).details) } finally { setBusy(false) }
  }
  async function putBack(s: Swap) {
    try {
      const r = await rpc<{ project: { image_swaps?: Swap[] } }>('images.remove', { project, bundle: s.bundle, path_id: s.path_id })
      setSwaps(r.project.image_swaps ?? []); onChanged(); say(`picture put back: ${s.name}`)
      if (done && done.pic.bundle === s.bundle && done.pic.path_id === s.path_id) setDone(null)
    } catch (e) { setProblem(sayOf(e)) }
  }

  const look = done && cat ? lookFor(done.pic, done.where, cat) : null
  return (
    <div className="pictures" data-testid="pictures">
      <div className="head">PICTURES</div>
      {swaps.length > 0 && <div className="pad">
        <div className="small dim">Pictures you replaced</div>
        <ul className="pic-list">{swaps.map((s) => <li key={s.bundle + s.path_id}><GameThumb p={s} /> → <b>{s.name || s.path_id}</b>{s.where?.length ? <small className="dim"> on {s.where.map((w) => (cat?.places[w] ?? w).split(' (')[0]).join(', ')}</small> : null}
          <button onClick={() => putBack(s)}>Put it back</button></li>)}</ul></div>}
      <ol className="pic-steps">
        <li><b>Choose a picture of the game</b>
          <div className="row" role="group" aria-label="Kind of picture">
            <button className={kind === 'wallpaper' ? 'on' : ''} onClick={() => setKind('wallpaper')}>Wallpapers{cat ? ` (${cat.counts.wallpapers})` : ''}</button>
            <button className={kind === 'icon' ? 'on' : ''} onClick={() => setKind('icon')}>Icons{cat ? ` (${cat.counts.icons})` : ''}</button>
          </div>
          <input className="search" placeholder="Filter by name ..." aria-label="Filter pictures" value={q} onChange={(e) => setQ(e.target.value)} />
          {!cat && !problem && <div className="dim small">Reading the game's pictures ...</div>}
          {cat && kind === 'icon' && cat.counts.left_out > 0 && <div className="dim small">{cat.counts.left_out} more pictures are placed by the game's code, so a skin can't replace them; they are not listed.</div>}
          <ul className="pic-cat">{shown.slice(0, SHOWN).map((p) => <li key={p.bundle + p.path_id + p.name} className={chosen === p ? 'sel' : ''}>
            <button onClick={() => choose(p)} aria-label={`Choose ${p.name}`}><GameThumb p={p} /><span>{p.name}</span><small className="dim">{p.w && p.h ? ` ${p.w}x${p.h}` : ''}</small></button></li>)}</ul>
          {shown.length > SHOWN && <div className="dim small">Showing the first {SHOWN} of {shown.length}; type part of a name to narrow it.</div>}
        </li>
        <li><b>Pick your picture</b>
          {!chosen ? <div className="dim small">Choose a picture of the game first.</div>
            : <div className="row"><GameThumb p={chosen} /> → {file ? <FileThumb path={file} /> : <span className="dim small">none yet</span>}
              <button onClick={pick}>{file ? 'Pick another file' : 'Pick a file'}</button> <small className="dim">PNG, JPG or WebP{chosen.kind === 'icon' ? ', or SVG' : ''}</small></div>}
        </li>
        <li><b>Where it shows</b>
          {!chosen ? <div className="dim small">Choose a picture of the game first.</div>
            : chosen.kind === 'icon' ? <div className="dim small">An icon shows wherever the game uses it; nothing to tick.</div>
              : cat && <fieldset className="pic-where"><legend className="dim small">The game chooses its wallpapers while it runs, so the skin paints yours on the places you tick.</legend>
                {Object.entries(cat.places).map(([k, label]) => <label key={k}><input type="checkbox" checked={where.includes(k)} onChange={(e) => setWhere(e.target.checked ? [...where, k] : where.filter((x) => x !== k))} /> {label}</label>)}
                {where.length === 0 && <div className="warn small">Tick at least one place.</div>}</fieldset>}
        </li>
      </ol>
      {problem && <div className="notice" role="alert"><div>{problem.plain}</div><details><summary>details</summary><div className="mono small">{problem.details}</div></details></div>}
      <div className="pad"><button className="primary" disabled={!canUse} onClick={use}>{busy ? 'Saving ...' : 'Use my picture'}</button></div>
      {done && <div className="pad pic-done" data-testid="pic-done">
        <div>Your picture is in the skin. It shows in the game after <b>Put it in the game</b>.</div>
        {look ? <button onClick={() => onLook(look)}>See it in Look at it ({look.label})</button>
          : done.pic.kind === 'icon'
            ? <><div className="dim small">Look at it draws it on any layout that uses this icon; the Preferences card and the Tactics and Medical centre tiles use some icons.</div><button onClick={() => onLook(null)}>Open Look at it</button></>
            : <div className="dim small">The places you ticked are on screens Look at it can't draw yet; you will see it in the game. Tick "Main screens" to see it on the Squad screen here.</div>}
      </div>}
    </div>
  )
}
