import { Component, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import Editor from '@monaco-editor/react'
import { connect, rpc, subscribe, RpcError, type EngineState, type FileItem, type Job, type ProblemItem } from './engine'
import { lint, registerQuickFixes, registerTokenCompletion } from './monaco'
import Palette from './Palette'
import Assets from './Assets'
import Updates from './Updates'
import Preview from './Preview'
import Layouts from './Layouts'
import Tiles from './Tiles'
import Tables from './Tables'
import Checklist from './Checklist'
import Search from './Search'
import Gutter, { useStoredSize } from './Gutter'
import { RenderBrowser, RenderCanvas, type LayoutRow } from './Render'

interface Tab { path: string; text: string; saved: string; readonly?: boolean }
interface Plan { target: string; operations: { op: string; count: number; summary: string; detail: any[] }[]; dropped: { item: string; reason: string }[]; warnings: string[] }
type Mode = 'simple' | 'expert'
type PanelTab = 'problems' | 'output' | 'build' | 'preview'
type View = 'explorer' | 'search' | 'palette' | 'assets' | 'layouts' | 'tiles' | 'tables' | 'updates' | 'checklist' | 'game' | 'render'
const SESSION = 'studio.session'

/** A view that throws while rendering shows its error instead of taking the whole window down (a blank black screen). */
export class Guard extends Component<{ name: string; children: ReactNode }, { err: Error | null }> {
  state = { err: null as Error | null }
  static getDerivedStateFromError(err: Error) { return { err } }
  componentDidCatch(err: Error) { console.error('view crashed:', this.props.name, err) }
  render() {
    if (!this.state.err) return this.props.children
    return <div className="guard"><b>{this.props.name} could not be shown.</b><div className="mono small">{String(this.state.err.message || this.state.err)}</div><button onClick={() => this.setState({ err: null })}>Try again</button></div>
  }
}

const langOf = (p: string) => (p.endsWith('.json') ? 'json' : p.endsWith('.uss') ? 'css' : 'plaintext')
const SIMPLE_FILES = (f: FileItem) => f.path === 'styles/tokens.uss' || f.path.startsWith('images/')

export default function App() {
  const [boot, setBoot] = useState<'connecting' | 'ready' | string>('connecting')
  const [state, setState] = useState<EngineState | null>(null)
  const [projects, setProjects] = useState<string[]>([])
  const [project, setProject] = useState<string | null>(null)
  const [isFolder, setIsFolder] = useState(true)
  const [target, setTarget] = useState<string>('')
  const [files, setFiles] = useState<FileItem[]>([])
  const [tabs, setTabs] = useState<Tab[]>([])
  const [active, setActive] = useState<string | null>(null)
  const [problems, setProblems] = useState<ProblemItem[]>([])
  const [panel, setPanel] = useState<PanelTab>('problems')
  const [log, setLog] = useState<string[]>([])
  const [jobs, setJobs] = useState<Record<string, Job>>({})
  const [mode, setMode] = useState<Mode>((localStorage.getItem('studio.mode') as Mode) || 'expert')
  const [view, setView] = useState<View>('explorer')
  const editorRef = useRef<any>(null)
  const restored = useRef(false)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [planErr, setPlanErr] = useState('')
  const [sheets, setSheets] = useState<{ name: string; bundle: string; rules: number }[]>([])
  const [sheetQ, setSheetQ] = useState('')
  const [rl, setRl] = useState<LayoutRow | null>(null)                             // the layout picked in the render view
  const [sideW, setSideW] = useStoredSize('studio.sideW', 250, 160, 640)           // resizable panels, remembered between runs
  const [panelH, setPanelH] = useStoredSize('studio.panelH', 210, 80, 560)

  const say = useCallback((s: string) => setLog((l) => [...l.slice(-300), new Date().toLocaleTimeString() + '  ' + s]), [])
  const fail = useCallback((e: unknown) => { say('ERROR ' + (e instanceof RpcError ? `${e.message} (code ${e.code})` : String(e))); setPanel('output') }, [say])

  const refreshState = useCallback(async () => {
    try { const s = await rpc<EngineState>('app.state'); const list = await rpc<string[]>('project.list'); setProjects(list); setState(s) } catch (e) { fail(e) }   // both set together: the session restore waits for both
  }, [fail])

  useEffect(() => {
    let off = () => {}
    connect().then(async () => { setBoot('ready'); await refreshState(); off = subscribe((t, d) => {
      const id = d.id as string
      setJobs((j) => ({ ...j, [id]: { ...(j[id] || {}), ...d } as Job }))
      if (t === 'job.done' || t === 'job.failed') say(`${t}: ${d.title || id}${d.error ? ' - ' + d.error : ''}`)
    }) }).catch((e) => setBoot(String(e.message || e)))
    const iv = setInterval(() => { rpc<EngineState>('app.state').then(setState).catch(() => {}) }, 15000)
    return () => { off(); clearInterval(iv) }
  }, [refreshState, say])

  const openProject = useCallback(async (name: string, keepTabs?: string[], keepActive?: string | null) => {
    if (!keepTabs && tabs.some((t) => t.text !== t.saved) && !confirm('Discard unsaved changes in the open files?')) return
    try {
      const f = await rpc<{ folder: boolean; files: FileItem[] }>('project.files', { project: name })
      setProject(name); setIsFolder(f.folder); setFiles(f.files); setTabs([]); setActive(null); setProblems([])
      if (keepTabs) {
        const opened: Tab[] = []
        for (const p of keepTabs) { if (!f.files.some((x) => x.path === p && x.kind === 'text')) continue; try { const r = await rpc<{ text: string }>('project.read_file', { project: name, path: p }); opened.push({ path: p, text: r.text, saved: r.text }) } catch { /* file gone */ } }
        setTabs(opened); setActive(keepActive && opened.some((x) => x.path === keepActive) ? keepActive : opened[0]?.path ?? null)
      }
      if (f.folder) setProblems((await rpc<{ problems: ProblemItem[] }>('project.problems', { project: name })).problems)
      const m = await rpc<any>('project.get', { name }); setTarget(m.options?.output || 'bundles')
      say(`opened ${name}${f.folder ? '' : ' (legacy single-file project)'}`)
    } catch (e) { fail(e) }
  }, [tabs, say, fail])

  const openFile = useCallback(async (path: string, line?: number) => {
    if (!project) return
    if (!tabs.some((t) => t.path === path)) {
      try { const r = await rpc<{ text: string }>('project.read_file', { project, path }); setTabs((t) => [...t, { path, text: r.text, saved: r.text }]) } catch (e) { return fail(e) }
    }
    setActive(path)
    if (line) setTimeout(() => { editorRef.current?.revealLineInCenter(line); editorRef.current?.setPosition({ lineNumber: line, column: 1 }); editorRef.current?.focus() }, 80)
  }, [project, tabs, fail])

  const openSheet = useCallback(async (name: string, bundle: string) => {
    const path = `game/${bundle.replace(/^ui-styles_assets_|\.bundle$/g, '')}/${name}.uss`
    if (!tabs.some((t) => t.path === path)) {
      try { const r = await rpc<{ text: string }>('game.sheet', { name, bundle }); setTabs((ts) => [...ts, { path, text: r.text, saved: r.text, readonly: true }]) } catch (e) { return fail(e) }
    }
    setActive(path)
  }, [tabs, fail])

  const loadPlan = useCallback(async () => {
    if (!project) return
    setPlanErr('')
    try { setPlan(await rpc<Plan>('build.plan', { project })) } catch (e) { setPlan(null); setPlanErr(e instanceof RpcError ? e.message : String(e)) }
  }, [project])
  useEffect(() => { if (panel === 'build' && project) loadPlan() }, [panel, project, problems.length, loadPlan])
  useEffect(() => { if (view === 'game' && !sheets.length) rpc<typeof sheets>('game.sheets').then(setSheets).catch(() => {}) }, [view, sheets.length])

  const save = useCallback(async () => {
    const t = tabs.find((x) => x.path === active)
    if (!t || !project || t.readonly) return
    try {
      const r = await rpc<{ problems: ProblemItem[] }>('project.write_file', { project, path: t.path, text: t.text })
      setTabs((ts) => ts.map((x) => (x.path === t.path ? { ...x, saved: t.text } : x)))
      setProblems(r.problems); say(`saved ${t.path}: ${r.problems.length} problem(s)`)
      setFiles((await rpc<{ files: FileItem[] }>('project.files', { project })).files)
    } catch (e) { fail(e) }
  }, [tabs, active, project, say, fail])

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); save() } }
    window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h)
  }, [save])

  const closeTab = (path: string) => {
    const t = tabs.find((x) => x.path === path)
    if (t && t.text !== t.saved && !confirm(`Close ${path} without saving?`)) return
    const rest = tabs.filter((x) => x.path !== path); setTabs(rest)
    if (active === path) setActive(rest.length ? rest[rest.length - 1].path : null)
  }

  const newProject = async () => {
    const name = prompt('Name of the new project (letters, digits, dot, dash, underscore):')?.trim()
    if (!name) return
    try { await rpc('project.create_folder', { name, target: 'native' }); await refreshState(); await openProject(name) } catch (e) { fail(e) }
  }
  const importNative = async () => {
    let path: string | undefined
    if ('__TAURI_INTERNALS__' in window) {                       // the desktop window: the real Windows folder picker
      try { const { open } = await import('@tauri-apps/plugin-dialog'); const r = await open({ directory: true, multiple: false, title: 'Pick the skin folder (the one that holds skin.json). It is only read.' }); path = typeof r === 'string' ? r : undefined } catch (e) { fail(e); return }
    } else path = prompt('Folder of a native skin to import (the one with skin.json). It is only read.')?.trim()
    if (!path) return
    const name = prompt('Name for the new project:', path.split(/[\\/]/).filter(Boolean).pop() || 'imported')?.trim()
    if (!name) return
    try { const r = await rpc<any>('project.import_native', { path, name }); say(`imported ${r.name}: ${r.sheets} sheets, ${r.images} images, ${r.fonts} fonts (${r.files} files)`); (r.notes || []).forEach((n: string) => say('note: ' + n)); await refreshState(); await openProject(name) } catch (e) { fail(e) }
  }
  const newSheet = async () => {
    if (!project) return
    const sheet = prompt('Game stylesheet the new rule file belongs to (its name, e.g. SIStyles or AlwaysAppliedStyleSheet; see G for the list). The file will be styles/<name>.uss:', 'SIStyles')?.trim()
    if (!sheet) return
    try {
      const r = await rpc<{ path: string; files: FileItem[] }>('project.new_sheet', { project, sheet })
      setFiles(r.files); say(`created ${r.path}`); await openFile(r.path)
    } catch (e) { fail(e) }
  }
  const closeProject = () => {
    if (tabs.some((t) => t.text !== t.saved) && !confirm('Discard unsaved changes in the open files?')) return
    setProject(null); setFiles([]); setTabs([]); setActive(null); setProblems([]); setPlan(null)
    try { localStorage.removeItem(SESSION) } catch { /* no storage */ }
  }
  const deleteProject = async (name: string) => {
    if (!confirm(`Delete project "${name}"?\n\nIt is moved to the trash folder inside the workspace, not erased.`)) return
    try {
      const r = await rpc<{ trash: string }>('project.delete', { project: name })
      say(`deleted ${name} (moved to ${r.trash})`)
      if (name === project) { setProject(null); setFiles([]); setTabs([]); setActive(null); setProblems([]); setPlan(null); try { localStorage.removeItem(SESSION) } catch { /* no storage */ } }
      await refreshState()
    } catch (e) { fail(e) }
  }
  const migrate = async () => {
    if (!project || !confirm(`Convert ${project} into a project folder? The old file is kept as ${project}.skin.json.migrated and the conversion is verified first.`)) return
    try { await rpc('project.migrate', { project }); say(`${project} converted to a folder`); await refreshState(); await openProject(project) } catch (e) { fail(e) }
  }
  const exportNative = async () => {
    if (!project) return
    try { const r = await rpc<any>('native.export', { project }); say(`native skin written to ${r.folder}: ${r.tokens} tokens, ${r.rules} rules, ${r.images} images, ${r.problems.length} problem(s)`); for (const s of r.skipped) say('skipped: ' + s); setPanel('output') } catch (e) { fail(e) }
  }
  const buildBundles = async () => {
    if (!project) return
    try { const r = await rpc<{ job: string }>('build.bundles', { name: project }); say(`bundle build queued (${r.job})`); setPanel('output') } catch (e) { fail(e) }
  }
  const installBundles = async () => {
    if (!project) return
    if (!confirm(`Install the latest build of "${project}" into the game?\n\nThe game must be closed. The files it replaces are backed up first, the copy is verified and rolled back on a mismatch. Native skins are not affected.`)) return
    try { const r = await rpc<any>('install.bundles', { name: project }); say('installed: ' + JSON.stringify(r).slice(0, 400)); setPanel('output') } catch (e) { fail(e) }
  }
  const restoreStock = async () => {
    if (!confirm('Put the stock game files back for every bundle this editor changed?\n\nThe game must be closed. Hashes are verified afterwards.')) return
    try { const r = await rpc<any>('backup.restore', { backup: 'vanilla' }); say('restored: ' + JSON.stringify(r).slice(0, 400)); setPanel('output') } catch (e) { fail(e) }
  }
  const setModeP = (m: Mode) => { setMode(m); localStorage.setItem('studio.mode', m) }

  useEffect(() => {
    if (boot !== 'ready' || restored.current || !state) return
    restored.current = true
    try { const s = JSON.parse(localStorage.getItem(SESSION) || 'null'); if (s?.project && projects.includes(s.project)) openProject(s.project, s.tabs || [], s.active) } catch { /* no session */ }
  }, [boot, state, projects, openProject])
  useEffect(() => {
    if (!restored.current || !project) return
    localStorage.setItem(SESSION, JSON.stringify({ project, tabs: tabs.map((t) => t.path), active }))
  }, [project, tabs, active])

  const reloadClean = useCallback(async () => {
    if (!project) return
    setFiles((await rpc<{ files: FileItem[] }>('project.files', { project })).files)
    setProblems((await rpc<{ problems: ProblemItem[] }>('project.problems', { project })).problems)
    const fresh = await Promise.all(tabs.filter((t) => t.text === t.saved).map(async (t) => { try { return [t.path, (await rpc<{ text: string }>('project.read_file', { project, path: t.path })).text] as const } catch { return [t.path, t.text] as const } }))
    setTabs((ts) => ts.map((t) => { const f = fresh.find((x) => x[0] === t.path); return f && t.text === t.saved ? { ...t, text: f[1], saved: f[1] } : t }))
  }, [project, tabs])

  const dirty = (p: string) => { const t = tabs.find((x) => x.path === p); return !!t && t.text !== t.saved }
  const tab = tabs.find((t) => t.path === active)
  const shown = useMemo(() => (mode === 'simple' ? files.filter(SIMPLE_FILES) : files), [files, mode])
  const running = Object.values(jobs).filter((j) => j.state === 'running' || j.state === 'queued')

  if (boot !== 'ready') return <div className="boot"><h1>FM Skin Studio</h1><p>{boot === 'connecting' ? 'Starting the engine ...' : boot}</p></div>

  return (
    <div className="app" style={{ gridTemplateColumns: `44px ${sideW}px 1fr`, gridTemplateRows: `1fr ${panelH}px 24px` }}>
      <Gutter axis="x" value={sideW} min={160} max={640} def={250} onChange={setSideW} label="Side panel width" style={{ left: 44 + sideW - 3, top: 0, bottom: 24 }} />
      <Gutter axis="y" invert value={panelH} min={80} max={560} def={210} onChange={setPanelH} label="Bottom panel height" style={{ left: 44 + sideW, right: 0, bottom: 24 + panelH - 3 }} />
      <nav className="activity">
        <button className={view === 'explorer' ? 'on' : ''} title="Explorer" onClick={() => setView('explorer')}>E</button>
        <button className={view === 'search' ? 'on' : ''} title="Search in project" onClick={() => setView('search')}>S</button>
        <button className={view === 'palette' ? 'on' : ''} title="Palette (token colours)" onClick={() => setView('palette')} disabled={!project}>P</button>
        <button className={view === 'assets' ? 'on' : ''} title="Images: replace the game's pictures, icons and SVGs" onClick={() => setView('assets')} disabled={!project}>I</button>
        <button className={view === 'layouts' ? 'on' : ''} title="UXML layouts: element trees, class edits" onClick={() => setView('layouts')}>L</button>
        <button className={view === 'tiles' ? 'on' : ''} title="Tile layout: grid compositions per screen and breakpoint, move cells" onClick={() => setView('tiles')}>T</button>
        <button className={view === 'tables' ? 'on' : ''} title="Table views: columns, widths, order" onClick={() => setView('tables')}>V</button>
        <button className={view === 'render' ? 'on' : ''} title="Render: draw a game layout offline, with the rules that matched (an approximation)" onClick={() => setView('render')}>R</button>
        <button className={view === 'checklist' ? 'on' : ''} title="In-game checklist and the prepared packages" onClick={() => setView('checklist')}>?</button>
        <button className={view === 'updates' ? 'on' : ''} title="Game updates: version profiles and the diff between two builds" onClick={() => setView('updates')}>U</button>
        <button className={view === 'game' ? 'on' : ''} title="Game: vanilla stylesheets (read-only)" onClick={() => setView('game')}>G</button>
        <span className="grow" />
        <button title={mode === 'expert' ? 'Expert mode (click for Simple)' : 'Simple mode (click for Expert)'} onClick={() => setModeP(mode === 'expert' ? 'simple' : 'expert')}>{mode === 'expert' ? 'X' : 'S'}</button>
      </nav>
      <aside className="explorer">
        {view === 'search' && <Search project={project} onOpen={openFile} />}
        {view === 'game' && <div className="gameview"><div className="head">GAME STYLESHEETS ({sheets.length})</div>
          <input className="search" placeholder="Filter ..." value={sheetQ} onChange={(e) => setSheetQ(e.target.value)} />
          <ul>{sheets.filter((s) => s.name.toLowerCase().includes(sheetQ.toLowerCase())).map((s) => <li key={s.bundle + '|' + s.name} onClick={() => openSheet(s.name, s.bundle)} title={s.bundle}>{s.name}<small> {s.rules}</small></li>)}</ul></div>}
        {project && <div hidden={view !== 'assets'}><Guard name="Images"><Assets key={project} project={project} onChanged={reloadClean} say={say} /></Guard></div>}   {/* stays mounted so unsaved staging survives a view switch */}
        {view === 'layouts' && <Guard name="Layouts"><Layouts key={project ?? ''} project={project} target={target} onChanged={reloadClean} say={say} /></Guard>}
        {view === 'tiles' && <Guard name="Tile layout"><Tiles key={project ?? ''} project={project} target={target} onChanged={reloadClean} say={say} /></Guard>}
        {view === 'tables' && <Guard name="Table views"><Tables key={project ?? ''} project={project} target={target} onChanged={reloadClean} say={say} /></Guard>}
        {view === 'render' && <Guard name="Render browser"><RenderBrowser picked={rl ? rl.bundle + rl.path_id : null} onPick={setRl} say={say} /></Guard>}
        {view === 'checklist' && <Guard name="In-game checklist"><Checklist say={say} /></Guard>}
        {view === 'updates' && <Guard name="Game updates"><Updates project={project} say={say} onChanged={reloadClean} /></Guard>}
        {view === 'palette' && project && <Palette project={project} onChanged={reloadClean} say={say} />}
        {view === 'explorer' && <>
        <div className="head">PROJECTS <span><button onClick={importNative} title="Import a native skin folder as a project">⇩</button> <button onClick={newProject} title="New project">+</button></span></div>
        <ul>{projects.map((p) => <li key={p} className={p === project ? 'sel' : ''} onClick={() => openProject(p)}>
          <span>{p}</span>
          <span className="rowbtns">
            {p === project && <button title="Close this project" onClick={(e) => { e.stopPropagation(); closeProject() }}>close</button>}
            <button title="Delete this project (moved to the trash folder)" onClick={(e) => { e.stopPropagation(); deleteProject(p) }}>delete</button>
          </span></li>)}</ul>
        {project && <>
          <div className="head">{project.toUpperCase()} {isFolder && <button onClick={newSheet} title="Add another rule sheet (styles/<game sheet>.uss)">+ sheet</button>}</div>
          {!isFolder && <div className="note">Legacy single-file project. <button onClick={migrate}>Convert to folder</button></div>}
          <ul>{shown.map((f) => <li key={f.path} className={(f.path === active ? 'sel ' : '') + f.kind} onClick={() => f.kind === 'text' && openFile(f.path)}>{f.path}{dirty(f.path) ? ' •' : ''}<small>{f.kind === 'image' ? ' image' : ''}</small></li>)}</ul>
        </>}
        </>}
      </aside>
      <main className="editor">
        {view === 'render' ? <Guard name="Render"><RenderCanvas layout={rl} say={say} project={project} /></Guard> : <>
        <div className="tabs">{tabs.map((t) => <div key={t.path} className={'tab' + (t.path === active ? ' on' : '')} onClick={() => setActive(t.path)}>{t.path.split('/').pop()}{t.readonly ? ' (game)' : ''}{dirty(t.path) ? ' •' : ''}<button onClick={(e) => { e.stopPropagation(); closeTab(t.path) }}>×</button></div>)}</div>
        <div className="surface">
          {tab ? <Editor path={tab.path} language={langOf(tab.path)} theme="vs-dark" value={tab.text}
            onChange={(v) => setTabs((ts) => ts.map((x) => (x.path === tab.path ? { ...x, text: v ?? '' } : x)))}
            onMount={(ed) => {
              editorRef.current = ed; registerTokenCompletion(); registerQuickFixes()
              let timer: ReturnType<typeof setTimeout> | undefined
              const run = () => { const m = ed.getModel(); if (m && m.uri.path.endsWith('.uss')) lint(m) }
              ed.onDidChangeModelContent(() => { clearTimeout(timer); timer = setTimeout(run, 400) })
              ed.onDidChangeModel(run); run()
            }}
            options={{ minimap: { enabled: false }, fontSize: 13, automaticLayout: true, colorDecorators: true, tabSize: 4, readOnly: !!tab.readonly }} />
            : <div className="empty">{project ? 'Open a file from the explorer. Ctrl+S saves; Ctrl+F / Ctrl+H find and replace; Ctrl+Z undo (per file).' : 'Open or create a project.'}</div>}
        </div>
        </>}
      </main>
      <section className="panel">
        <div className="ptabs">
          {(['problems', 'output', 'build', 'preview'] as PanelTab[]).map((p) => <button key={p} className={panel === p ? 'on' : ''} onClick={() => setPanel(p)}>{p.toUpperCase()}{p === 'problems' && problems.length ? ` (${problems.length})` : ''}</button>)}
        </div>
        <div className="pbody">
          {panel === 'problems' && (problems.length ? problems.map((p, i) => <div key={i} className="prob" onClick={() => p.file.endsWith('.uss') || p.file.endsWith('.json') ? openFile(p.file, p.line) : undefined}><b>{p.file}</b>:{p.line ?? '?'} {p.message}</div>) : <div className="dim">{project ? 'No problems.' : ''}</div>)}
          {panel === 'output' && log.map((l, i) => <div key={i} className="mono">{l}</div>)}
          {panel === 'preview' && <Guard name="Preview"><Preview project={project} say={say} /></Guard>}
          {panel === 'build' && <div className="build">
            <p>{project ? <>Target of <b>{project}</b>: <b>{target}</b>.</> : 'Open a project.'}</p>
            {planErr && <div className="warn">{planErr}</div>}
            {plan && <div className="plan">
              <div className="dim">PLAN ({plan.target})</div>
              {plan.operations.map((o, i) => <div key={i}><b>{o.op}</b> {o.summary}</div>)}
              {plan.dropped.map((d, i) => <div key={i} className="warn">dropped: {d.item} - {d.reason}</div>)}
              {plan.warnings.map((w, i) => <div key={i} className="warn">{w}</div>)}
            </div>}
            <button disabled={!project || problems.length > 0} onClick={exportNative}>Export native skin</button>
            <button disabled={!project || problems.length > 0 || !state?.vanilla} onClick={buildBundles}>Build bundles</button>
            <button disabled={!project || !state?.vanilla || !!state?.running} onClick={installBundles} title="Install the latest bundle build (game closed; backup first)">Install build</button>
            <button disabled={!state?.vanilla || !!state?.running} onClick={restoreStock} title="Restore the stock bundles">Restore stock</button>
            {problems.length > 0 && <span className="warn"> fix the problems first</span>}
            {Object.values(jobs).slice(-4).map((j) => <div key={j.id} className="mono">{j.id} {j.title}: {j.state} {Math.round((j.progress || 0) * 100)}% {j.error || ''}</div>)}
          </div>}
        </div>
      </section>
      <footer className="status">
        <span title={state?.install?.game_dir}>FM27 {state?.vanilla?.game_build || state?.install?.version || (state?.install ? 'game found' : 'no game selected')}</span>
        <span className={state?.tamper?.state === 'clean' ? 'ok' : state?.tamper?.state === 'modified' || state?.tamper?.state === 'game_updated' ? 'bad' : ''} title={state?.tamper?.message}>{state?.tamper ? 'files ' + state.tamper.state : ''}</span>
        {state?.snapshot_mismatch && <span className="bad">wrong snapshot</span>}
        <span>{state?.running ? 'game running' : 'game closed'}</span>
        <span className="grow" />
        {running.length > 0 && <span>{running[0].label} {Math.round(running[0].progress * 100)}%</span>}
        <span>target: {target || '-'}</span>
        <span className="click" onClick={() => setModeP(mode === 'expert' ? 'simple' : 'expert')}>{mode}</span>
      </footer>
    </div>
  )
}
