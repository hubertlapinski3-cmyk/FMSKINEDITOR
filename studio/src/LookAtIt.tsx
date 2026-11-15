import { useEffect, useRef, useState } from 'react'
import { rpc } from './engine'
import { RenderCanvas, nodeAt, type LayoutRow, type RResult } from './Render'
import Recolour from './Recolour'
import { SHOWCASE } from './showcase'
import { sayOf } from './plainError'

type Mode = 'side' | 'game' | 'mine'

/** "Look at it" (S5), Simple mode: a layout of the game drawn OFFLINE by the Studio, with a before / after switch: the game as it ships, with your skin, or both side by side.
 *  Both sides are renders (an approximation, never the game); no screenshot of the game is requested or shown anywhere in this view: it never calls `preview.*`
 *  (pinned by a test that spies on every call). The approximation notice is the engine's own, shown once above the pictures. */
export default function LookAtIt({ project, say, start }: { project: string | null; say: (s: string) => void; start?: { name: string; label: string } | null }) {
  const [current, setCurrent] = useState<LayoutRow | null>(null)
  const [label, setLabel] = useState(SHOWCASE[0].label)
  const [mode, setMode] = useState<Mode>(project ? 'side' : 'game')
  const [notice, setNotice] = useState('')
  const [q, setQ] = useState('')
  const [found, setFound] = useState<LayoutRow[]>([])
  const [problem, setProblem] = useState('')
  const asked = useRef('')
  const [picked, setPicked] = useState<{ side: 'game' | 'mine'; path: string } | null>(null)      // S3: the part clicked, on which side
  const [results, setResults] = useState<{ game?: RResult; mine?: RResult }>({})

  async function open(name: string, lab: string) {
    asked.current = name
    try {
      const r = await rpc<{ layouts: LayoutRow[] }>('render.layouts', { q: name, limit: 50 })
      const row = r.layouts.find((l) => l.name === name)
      if (asked.current !== name) return
      if (!row) { setProblem(`The game has no layout called ${name} in this build.`); return }
      setProblem(''); setLabel(lab); setCurrent(row); setNotice(''); setPicked(null); setResults({})
    } catch (e) { setProblem(sayOf(e).plain); say('ERROR ' + sayOf(e).details) }
  }
  useEffect(() => { void open(start?.name ?? SHOWCASE[0].name, start?.label ?? SHOWCASE[0].label) }, [start])        // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { setMode(project ? 'side' : 'game') }, [project])
  useEffect(() => {
    if (q.trim().length < 2) { setFound([]); return }
    const t = setTimeout(() => rpc<{ layouts: LayoutRow[] }>('render.layouts', { q: q.trim(), limit: 12 }).then((r) => setFound(r.layouts)).catch(() => {}), 250)
    return () => clearTimeout(t)
  }, [q])

  const key = current ? current.bundle + '|' + current.path_id : ''
  const onResult = (side: 'game' | 'mine') => (r: RResult | null) => { if (r?.notice) setNotice(r.notice); if (r) setResults((x) => ({ ...x, [side]: r })) }
  const pane = (skin: boolean, title: string) => (
    <figure className="look-pane" key={title + key}>
      <figcaption>{title}</figcaption>
      <RenderCanvas layout={current} say={say} project={project} skinOverride={skin} bare zoom0={mode === 'side' ? 0.5 : 0.75} onResult={onResult(skin ? 'mine' : 'game')}
        picked={picked && picked.side === (skin ? 'mine' : 'game') ? picked.path : null} onPick={project ? (p) => setPicked({ side: skin ? 'mine' : 'game', path: p }) : undefined} />
    </figure>
  )

  return (
    <div className="look" data-testid="look">
      <aside className="look-list">
        <div className="head">LOOK AT</div>
        <ul>{SHOWCASE.map((s) => <li key={s.name} className={current?.name === s.name ? 'sel' : ''}><button onClick={() => open(s.name, s.label)}><b>{s.label}</b><small>{s.what}</small></button></li>)}</ul>
        <div className="head">FIND ANOTHER</div>
        <input className="search" placeholder="Part of a layout's name ..." value={q} onChange={(e) => setQ(e.target.value)} aria-label="Find another layout" />
        {found.length > 0 && <ul className="look-found">{found.map((l) => <li key={l.bundle + l.path_id}><button onClick={() => { setCurrent(l); setLabel(l.name); setNotice(''); setFound([]); setQ(''); setPicked(null); setResults({}) }}>{l.name}</button></li>)}</ul>}
      </aside>
      <section className="look-main">
        <div className="look-bar" role="group" aria-label="What to show">
          <button className={mode === 'side' ? 'on' : ''} disabled={!project} onClick={() => setMode('side')}>Side by side</button>
          <button className={mode === 'game' ? 'on' : ''} onClick={() => setMode('game')}>The game as it ships</button>
          <button className={mode === 'mine' ? 'on' : ''} disabled={!project} onClick={() => setMode('mine')}>With my skin</button>
          <b className="look-title">{label}</b>
        </div>
        {!project && <div className="dim small pad">Open or make a skin (Projects) to see it next to the game here.</div>}
        {project && <div className="dim small pad">Click any part of a picture to change its colours.</div>}
        {problem && <div className="warn pad" role="alert">{problem}</div>}
        {notice && <div className="rnotice" role="note">{notice}</div>}
        <div className="look-work">
          <div className={'look-panes ' + mode}>
            {current && (mode === 'game' || mode === 'side') && pane(false, 'The game as it ships')}
            {current && project && (mode === 'mine' || mode === 'side') && pane(true, 'With my skin: ' + project)}
          </div>
          {project && picked && (() => {
            const res = results[picked.side]
            const node = res ? nodeAt(res.tree, picked.path) : null
            return node && res ? <Recolour key={picked.side + picked.path + key} node={node} tree={res.tree} project={project} say={say} onClose={() => setPicked(null)} /> : null
          })()}
        </div>
      </section>
    </div>
  )
}
