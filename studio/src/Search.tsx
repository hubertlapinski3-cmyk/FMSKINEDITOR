import { useEffect, useState } from 'react'
import { rpc } from './engine'

interface Hit { path: string; line: number; col: number; text: string }

/** Project-wide find over the project's text files. */
export default function Search({ project, onOpen }: { project: string | null; onOpen: (path: string, line: number) => void }) {
  const [q, setQ] = useState('')
  const [regex, setRegex] = useState(false)
  const [kase, setKase] = useState(false)
  const [res, setRes] = useState<{ hits: Hit[]; truncated: boolean }>({ hits: [], truncated: false })
  const [err, setErr] = useState('')
  useEffect(() => {
    if (!project || !q) { setRes({ hits: [], truncated: false }); setErr(''); return }
    const t = setTimeout(() => rpc('project.search', { project, q, regex, case: kase }).then((r) => { setRes(r); setErr('') }).catch((e) => setErr(String(e.message || e))), 250)
    return () => clearTimeout(t)
  }, [project, q, regex, kase])
  const groups = res.hits.reduce<Record<string, Hit[]>>((g, h) => { (g[h.path] ||= []).push(h); return g }, {})
  return (
    <div className="searchview">
      <div className="head">SEARCH</div>
      <input className="search" placeholder={project ? 'Find in project ...' : 'Open a project first'} disabled={!project} value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
      <div className="opts"><label><input type="checkbox" checked={kase} onChange={(e) => setKase(e.target.checked)} /> Aa</label><label><input type="checkbox" checked={regex} onChange={(e) => setRegex(e.target.checked)} /> .*</label><span className="dim">{res.hits.length}{res.truncated ? '+' : ''} result(s)</span></div>
      {err && <div className="note bad">{err}</div>}
      {Object.entries(groups).map(([path, hs]) => <div key={path}><div className="file">{path}</div>{hs.map((h, i) => <div key={i} className="hit" onClick={() => onOpen(h.path, h.line)}><b>{h.line}</b> {h.text}</div>)}</div>)}
    </div>
  )
}
