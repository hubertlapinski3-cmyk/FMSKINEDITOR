import { useEffect, useState } from 'react'
import { rpc, RpcError } from './engine'

interface LiveResult { mode: 'live' | 'static'; skin_id: string; exported: string; steps: string[]; reloaded: boolean; reason?: string; reload_note?: string; screenshot?: string; problems?: string[] }
interface Region { id: string; rect: number[]; skin: string; vanilla: string; changed: boolean }
const bin = async (method: string, params: Record<string, unknown>) => { const r = await rpc<{ content_type: string; base64: string }>(method, params); return `data:${r.content_type};base64,${r.base64}` }
const css = (c: string) => (c.length === 9 ? `#${c.slice(1, 7)}${c.slice(7)}` : c)

/** Live preview: native skin <name>-preview, game reload and screenshot through the inspector pipe. Without the pipe it says why and shows the static repaint of a measured screen. */
export default function Preview({ project, say }: { project: string | null; say: (s: string) => void }) {
  const [online, setOnline] = useState<{ online: boolean; reason?: string; game?: string; scene?: string } | null>(null)
  const [res, setRes] = useState<LiveResult | null>(null)
  const [img, setImg] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [stat, setStat] = useState<{ img: string; regions: Region[]; res: number[]; name: string } | null>(null)

  const probe = () => rpc<any>('inspector.status').then(setOnline).catch(() => {})
  useEffect(() => { probe() }, [])

  const staticRepaint = async () => {
    const models = await rpc<{ name: string; resolution: number[] }[]>('preview.models')
    if (!models.length || !project) return
    const m = await rpc<{ regions: Region[]; resolution: number[] }>('preview.evaluate', { name: models[0].name, project })
    setStat({ img: await bin('preview.image', { name: models[0].name }), regions: m.regions.filter((r) => r.changed), res: m.resolution, name: models[0].name })
  }
  const run = async () => {
    if (!project) return
    setBusy(true); setErr(''); setImg(''); setStat(null)
    try {
      const r = await rpc<LiveResult>('preview.live', { project })
      setRes(r); say(`live preview (${r.mode}): ${r.steps.join(' | ')}`)
      if (r.mode === 'live' && r.screenshot) setImg(await bin('preview.live_image', { path: r.screenshot }))
      else await staticRepaint()
      probe()
    } catch (e) { setErr(e instanceof RpcError ? e.message : String(e)) } finally { setBusy(false) }
  }
  return (
    <div className="preview">
      <div className="row">
        <button disabled={!project || busy} onClick={run}>{busy ? 'Working ...' : 'Live preview'}</button>
        <span className="dim">{online === null ? '' : online.online ? `inspector online: game ${online.game}, scene ${online.scene}` : `inspector offline: ${online.reason}`}</span>
      </div>
      <div className="dim">Writes the project as the native skin <b>{project ? project + '-preview' : '...'}</b> (never bundles), clicks Reload Skin in the game and takes a screenshot. First time: pick that skin once in Preferences.</div>
      {err && <div className="warn">{err}</div>}
      {res && <ul className="steps">{res.steps.map((s, i) => <li key={i}>{s}</li>)}</ul>}
      {res?.reload_note && <div className="warn">{res.reload_note}</div>}
      {res?.mode === 'static' && <div className="warn">Static repaint instead: {res.reason}</div>}
      {img && <img className="shot" src={img} alt="game screenshot" />}
      {stat && <div className="static" style={{ position: 'relative', maxWidth: 720 }}>
        <img className="shot" src={stat.img} alt={stat.name} />
        {stat.regions.map((r) => <div key={r.id} title={`${r.id}: ${r.vanilla} -> ${r.skin}`} style={{ position: 'absolute', left: `${(r.rect[0] / stat.res[0]) * 100}%`, top: `${(r.rect[1] / stat.res[1]) * 100}%`, width: `${(r.rect[2] / stat.res[0]) * 100}%`, height: `${(r.rect[3] / stat.res[1]) * 100}%`, background: css(r.skin), opacity: 0.85 }} />)}
        <div className="dim">{stat.name}: {stat.regions.length} changed region(s) painted with the project's colours (measured screen, not the game)</div>
      </div>}
    </div>
  )
}
