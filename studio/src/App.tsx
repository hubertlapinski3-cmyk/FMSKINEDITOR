import { Component, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import Editor from '@monaco-editor/react'
import { connect, rpc, subscribe, RpcError, customlayout, type EngineState, type FileItem, type Job, type ProblemItem, type LayoutRecovery } from './engine'
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
import Setup from './Setup'
import Start from './Start'
import PutInGame from './PutInGame'
import LookAtIt from './LookAtIt'
import Pictures from './Pictures'
import Share from './Share'
import Findings from './Findings'
import Explore from './Explore'
import Install from './Install'
import GameLayouts from './GameLayouts'
import Playground from './Playground'
import LayoutCanvas from './LayoutCanvas'
import SkinInspect from './SkinInspect'
import InjectedStyles from './InjectedStyles'
import { fileTabId, layoutTabId, type LayoutSelection, type LayoutTile } from './layoutShared'
import CustomLayouts, { LayoutRecoveryDialog } from './CustomLayouts'
import { resolveMode, readStoredMode, storeMode, type Mode } from './mode'
import { sayOf, sayOfJobError, type Said } from './plainError'
import { RenderScreenView, RenderTableView } from './RenderScreens'
import { RenderBrowser, RenderCanvas, ruleAtLine, rulePaths, tokenAt, tokenPaths, type LayoutRow, type RResult } from './Render'

/** A tab is either a project file (editable in Monaco) or a Game Layout (the canvas in LayoutCanvas).
 *  `active` holds tabKey(tab); keeping one key space lets the same tab bar host both kinds. */
interface FileTab { kind: 'file'; path: string; text: string; saved: string; readonly?: boolean }
interface LayoutTab { kind: 'layout'; name: string }
type Tab = FileTab | LayoutTab
const tabKey = (t: Tab) => (t.kind === 'file' ? fileTabId(t.path) : layoutTabId(t.name))
const isFileTab = (t: Tab): t is FileTab => t.kind === 'file'
interface Plan { target: string; operations: { op: string; count: number; summary: string; detail: any[] }[]; dropped: { item: string; reason: string }[]; warnings: string[] }
type PanelTab = 'problems' | 'output' | 'build' | 'preview'
type View = 'explorer' | 'search' | 'palette' | 'assets' | 'layouts' | 'tiles' | 'tables' | 'updates' | 'checklist' | 'game' | 'render' | 'put' | 'share' | 'findings' | 'explore' | 'install' | 'custom' | 'play' | 'playground' | 'skin_inspect' | 'injected_styles'
const SESSION = 'studio.session'
const DEV_TOOLS = import.meta.env.VITE_DEV_TOOLS === 'true'

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

const SIMPLE_VIEWS: View[] = ['explorer', 'palette', 'assets', 'render', 'put', 'share']
const SIMPLE_NAV: { view: View; label: string; title: string; needsProject?: boolean }[] = [
  { view: 'explorer', label: 'Projects', title: 'Your skins' },
  { view: 'palette', label: 'Colours', title: 'Change the colours', needsProject: true },
  { view: 'assets', label: 'Pictures', title: "Replace the game's pictures and icons", needsProject: true },
  { view: 'render', label: 'Look at it', title: 'See a game screen drawn with your skin (an approximation, not the game)' },
  { view: 'put', label: 'Put it in the game', title: 'Write your skin into your skins folder so the game can use it', needsProject: true },
  { view: 'share', label: 'Share and undo', title: 'Save your skin as a file, open a skin file, or start over' },
]
/** Advanced navigation: the letter is the compact icon, `label` is the accessible name and, when the
 *  activity-labels setting is on, the visible name. Titles stay stable (other tests and muscle memory). */
const ACT_NAV: { view: View; letter: string; label: string; title: string }[] = [
  { view: 'explorer', letter: 'E', label: 'Explorer', title: 'Explorer' },
  { view: 'search', letter: 'S', label: 'Search in project', title: 'Search in project' },
  { view: 'palette', letter: 'P', label: 'Colour palette', title: 'Palette (token colours)' },
  { view: 'assets', letter: 'I', label: 'Pictures and icons', title: "Images: replace the game's pictures, icons and SVGs" },
  { view: 'layouts', letter: 'L', label: 'UXML layouts', title: 'UXML layouts: element trees, class edits' },
  { view: 'tiles', letter: 'T', label: 'Tile layout', title: 'Tile layout: grid compositions per screen and breakpoint, move cells' },
  { view: 'tables', letter: 'V', label: 'Table views', title: 'Table views: columns, widths, order' },
  { view: 'render', letter: 'R', label: 'Render', title: 'Render: draw a game layout offline, with the rules that matched (an approximation)' },
  { view: 'findings', letter: 'F', label: 'Findings', title: 'Findings: what the gallery themes change in the game and what they miss, with the screenshots (Advanced only)' },
  { view: 'checklist', letter: '?', label: 'In-game checklist', title: 'In-game checklist and the prepared packages' },
  { view: 'updates', letter: 'U', label: 'Game updates', title: 'Game updates: version profiles and the diff between two builds' },
  { view: 'game', letter: 'G', label: 'Game stylesheets', title: 'Game: vanilla stylesheets (read-only)' },
  { view: 'explore', letter: 'A', label: 'Assets explorer', title: 'Assets: installation profile, bundle inventory, asset search, dependencies and typed adapters (read-only)' },
  { view: 'install', letter: 'N', label: 'Install skin into the game', title: 'Install skin into the game (transactional): preflight and confirmations, backups, journal, history, recovery and rollback' },
  { view: 'custom', letter: 'C', label: 'Custom layouts', title: 'Custom layouts: read-only folder view, Apply/Rollback with preflight, and unfinished-transaction recovery' },
  { view: 'play', letter: 'GL', label: 'Game Layouts (Playground)', title: 'Game Layouts (Playground): reconstruct a game screen, navigate its hierarchy, inspect every element with its evidence' },
  { view: 'playground', letter: 'Y', label: 'Playground', title: 'Playground: the full interactive screen view with hierarchy, inspector, operations and evidence' },
  { view: 'skin_inspect', letter: 'K', label: 'Inspect skin', title: 'Inspect a third-party skin folder against stock bundles (read-only)' },
  { view: 'injected_styles', letter: 'IS', label: 'Injected styles', title: 'Injected styles (AlwaysAppliedStyleSheet): custom classes, CSS variables, USS editor, reach & cascade preview' },
]
/** UI1b follow-up: a short expert bar for the work people actually do. The rest stay reachable under More. */
const PRIMARY_NAV = ['explorer', 'play', 'playground', 'palette', 'tiles', 'render', 'custom', 'checklist', 'install']
  .map((v) => ACT_NAV.find((n) => n.view === v)).filter((n): n is (typeof ACT_NAV)[number] => !!n)
const MORE_NAV = ACT_NAV.filter((n) => !PRIMARY_NAV.includes(n))
const langOf = (p: string) => (p.endsWith('.json') ? 'json' : p.endsWith('.uss') ? 'css' : 'plaintext')
const SIMPLE_FILES = (f: FileItem) => f.path === 'styles/tokens.uss' || f.path.startsWith('images/')

export default function App() {
  const [boot, setBoot] = useState<'connecting' | 'ready' | string>('connecting')
  const [state, setState] = useState<EngineState | null>(null)
  const [projects, setProjects] = useState<string[]>([])
  const [project, setProject] = useState<string | null>(null)
  const [isFolder, setIsFolder] = useState(true)
  const [target, setTarget] = useState<string>('')
  const [expBundleLayouts, setExpBundleLayouts] = useState(false)
  const [expTileSizes, setExpTileSizes] = useState(false)
  const [expSlotEdits, setExpSlotEdits] = useState(false)
  const [files, setFiles] = useState<FileItem[]>([])
  const [tabs, setTabs] = useState<Tab[]>([])
  const [active, setActive] = useState<string | null>(null)
  const [problems, setProblems] = useState<ProblemItem[]>([])
  const [panel, setPanel] = useState<PanelTab>('problems')
  const [log, setLog] = useState<string[]>([])
  const [jobs, setJobs] = useState<Record<string, Job>>({})
  const [mode, setMode] = useState<Mode>('advanced')          // resolved once the engine has answered (resolveMode): a fresh install, told by an empty workspace, starts in Simple
  const modeResolved = useRef(false)
  const [notice, setNotice] = useState<Said | null>(null)       // the last problem, in plain words (the raw text goes to the OUTPUT log)
  const [view, setView] = useState<View>('explorer')
  const [layoutProfile, setLayoutProfile] = useState<string>('2560x1440 fullscreen, Small, Larger')
  const [projectRev, setProjectRev] = useState(0)
  const editorRef = useRef<any>(null)
  const [lastRender, setLastRender] = useState<{ res: RResult | null; layout: LayoutRow | null }>({ res: null, layout: null })   // the render the editor's caret is matched against
  const [highlight, setHighlight] = useState<string[]>([])         // render nodes to outline (set from the editor: this rule or token styles them)
  const [caret, setCaret] = useState<{ line: number; col: number; text: string } | null>(null)
  const restored = useRef(false)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [planErr, setPlanErr] = useState('')
  const [sheets, setSheets] = useState<{ name: string; bundle: string; rules: number }[]>([])
  const [sheetQ, setSheetQ] = useState('')
  const [rmode, setRmode] = useState<'layout' | 'screen' | 'table'>('layout')          // what the render view shows: one layout, a whole screen on the grid, or a table view
  const [rl, setRl] = useState<LayoutRow | null>(null)                             // the layout picked in the render view
  const [lookStart, setLookStart] = useState<{ name: string; label: string } | null>(null)   // S6: the layout "See it in Look at it" opens
  const [sideW, setSideW] = useStoredSize('studio.sideW', 250, 160, 640)           // resizable panels, remembered between runs
  const [panelH, setPanelH] = useStoredSize('studio.panelH', 210, 80, 560)
  const [layoutRecovery, setLayoutRecovery] = useState<LayoutRecovery[]>([])       // UI1: scanned as soon as Studio starts
  const [layoutSel, setLayoutSel] = useState<LayoutSelection | null>(null)          // UI1b: selection in the active Game Layout tab
  const [actLabels, setActLabels] = useState(() => {                                // UI1b: optional icon+label activity bar
    try { return localStorage.getItem('studio.activityLabels') === '1' } catch { return false }
  })
  const [moreOpen, setMoreOpen] = useState(false)                                    // expert bar: the less-used tools live under More
  const [appUpdate, setAppUpdate] = useState<{ checking: boolean; version?: string; current?: string; error?: string; installing?: boolean }>({ checking: false })
  const [appUpdateDismissed, setAppUpdateDismissed] = useState(false)   // one popup per launch; Continue just dismisses it
  const [aboutOpen, setAboutOpen] = useState(false)
  const [gameUpdate, setGameUpdate] = useState<{ state: string; message?: string; rereading?: boolean; doneMsg?: string; errMsg?: string } | null>(null)

  const installAppUpdate = useCallback(async () => {
    if (!appUpdate.version) return
    setAppUpdate((u) => ({ ...u, installing: true, error: undefined }))
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      await invoke<void>('app_update_install')
    } catch (e) {
      const msg = String(e).slice(0, 300)
      setAppUpdate((u) => ({ ...u, installing: false, error: msg }))
    }
  }, [appUpdate.version])

  const say = useCallback((s: string) => setLog((l) => [...l.slice(-300), new Date().toLocaleTimeString() + '  ' + s]), [])
  const fail = useCallback((e: unknown) => { const s = sayOf(e); say('ERROR ' + s.details); setNotice(s); setPanel('output') }, [say])

  const refreshState = useCallback(async () => {
    try { const s = await rpc<EngineState>('app.state'); const list = await rpc<string[]>('project.list'); setProjects(list); setState(s) } catch (e) { fail(e) }   // both set together: the session restore waits for both
  }, [fail])
  const reloadLayoutRecovery = useCallback(async () => {
    try { setLayoutRecovery(await customlayout.recovery_scan()) } catch { setLayoutRecovery([]) }
  }, [])

  useEffect(() => {
    let off = () => {}
    connect().then(async () => { setBoot('ready'); await refreshState(); await reloadLayoutRecovery(); off = subscribe((t, d) => {
      const id = d.id as string
      setJobs((j) => ({ ...j, [id]: { ...(j[id] || {}), ...d } as Job }))
      if (t === 'job.done' || t === 'job.failed') say(`${t}: ${d.title || id}${d.error ? ' - ' + d.error : ''}`)
      if (t === 'job.failed' && d.error) sayOfJobError(String(d.error)).then(setNotice)
    }) }).catch((e) => setBoot(String(e.message || e)))
    const iv = setInterval(() => { rpc<EngineState>('app.state').then(setState).catch(() => {}); reloadLayoutRecovery() }, 15000)
    return () => { off(); clearInterval(iv) }
  }, [refreshState, say, reloadLayoutRecovery])

  // UI1 follow-up: check for an app update on EVERY launch, in the installed desktop app.
  // In a browser/dev there is no signed installer, so the check is a no-op. The result is
  // shown in the status strip; it never blocks editing or applying a layout.
  useEffect(() => {
    if (!('__TAURI_INTERNALS__' in window)) return
    let live = true
    setAppUpdate({ checking: true })
    ;(async () => {
      try {
        const { invoke } = await import('@tauri-apps/api/core')
        const info = await invoke<{ version: string; current: string } | null>('app_update_check')
        if (live) setAppUpdate({ checking: false, version: info?.version, current: info?.current })
      } catch (e) {
        if (live) setAppUpdate({ checking: false, error: String(e).slice(0, 200) })
      }
    })()
    return () => { live = false }
  }, [])

  const openProject = useCallback(async (name: string, keepTabs?: string[], keepActive?: string | null) => {
    if (!keepTabs && tabs.some((t) => isFileTab(t) && t.text !== t.saved) && !confirm('Discard unsaved changes in the open files?')) return
    try {
      const f = await rpc<{ folder: boolean; files: FileItem[] }>('project.files', { project: name })
      setProject(name); setIsFolder(f.folder); setFiles(f.files); setTabs([]); setActive(null); setProblems([]); setLayoutSel(null)
      if (keepTabs) {
        const opened: Tab[] = []
        for (const key of keepTabs) {
          if (key.startsWith('layout:')) { opened.push({ kind: 'layout', name: key.slice('layout:'.length) }); continue }
          const p = key.startsWith('file:') ? key.slice('file:'.length) : key
          if (!f.files.some((x) => x.path === p && x.kind === 'text')) continue
          try { const r = await rpc<{ text: string }>('project.read_file', { project: name, path: p }); opened.push({ kind: 'file', path: p, text: r.text, saved: r.text }) } catch { /* file gone */ }
        }
        setTabs(opened)
        setActive(keepActive && opened.some((x) => tabKey(x) === keepActive) ? keepActive : opened.length ? tabKey(opened[0]) : null)
      }
      if (f.folder) setProblems((await rpc<{ problems: ProblemItem[] }>('project.problems', { project: name })).problems)
      const m = await rpc<any>('project.get', { name }); setTarget(m.options?.output || 'bundles')
      setExpBundleLayouts(Boolean(m.options?.experimental_bundle_layout_edits_explicit && m.options?.experimental_bundle_layout_edits))
      setExpTileSizes(Boolean(m.options?.experimental_tile_sizes_explicit && m.options?.experimental_tile_sizes))
      setExpSlotEdits(Boolean(m.options?.experimental_slot_edits_explicit && m.options?.experimental_slot_edits))
      say(`opened ${name}${f.folder ? '' : ' (legacy single-file project)'}`)
    } catch (e) { fail(e) }
  }, [tabs, say, fail])

  const openFile = useCallback(async (path: string, line?: number) => {
    if (!project) return
    if (!tabs.some((t) => isFileTab(t) && t.path === path)) {
      try { const r = await rpc<{ text: string }>('project.read_file', { project, path }); setTabs((t) => [...t, { kind: 'file', path, text: r.text, saved: r.text }]) } catch (e) { return fail(e) }
    }
    setActive(fileTabId(path))
    if (line) setTimeout(() => { editorRef.current?.revealLineInCenter(line); editorRef.current?.setPosition({ lineNumber: line, column: 1 }); editorRef.current?.focus() }, 80)
  }, [project, tabs, fail])

  const openSheet = useCallback(async (name: string, bundle: string) => {
    const path = `game/${bundle.replace(/^ui-styles_assets_|\.bundle$/g, '')}/${name}.uss`
    if (!tabs.some((t) => isFileTab(t) && t.path === path)) {
      try { const r = await rpc<{ text: string }>('game.sheet', { name, bundle }); setTabs((ts) => [...ts, { kind: 'file', path, text: r.text, saved: r.text, readonly: true }]) } catch (e) { return fail(e) }
    }
    setActive(fileTabId(path))
  }, [tabs, fail])

  /** UI1b step 1: a composition from Game Layouts opens (or focuses) its own tab in the main tab bar. */
  const openLayout = useCallback((name: string) => {
    const id = layoutTabId(name)
    if (!tabs.some((t) => tabKey(t) === id)) setTabs((ts) => [...ts, { kind: 'layout', name }])
    setActive(id)
    setLayoutSel((s) => (s && s.composition === name ? s : null))
    setPanel('output')                      // UI1b step 3: layout edits go to the output/history panel
  }, [tabs])

  const selectLayoutTile = useCallback((tile: LayoutTile) => {
    if (!active?.startsWith('layout:')) return
    setLayoutSel({ composition: active.slice('layout:'.length), tile })
  }, [active])

  const loadPlan = useCallback(async () => {
    if (!project) return
    setPlanErr('')
    try { setPlan(await rpc<Plan>('build.plan', { project })) } catch (e) { setPlan(null); setPlanErr(e instanceof RpcError ? e.message : String(e)) }
  }, [project])
  useEffect(() => { if (panel === 'build' && project) loadPlan() }, [panel, project, problems.length, loadPlan])
  useEffect(() => { if (view === 'game' && !sheets.length) rpc<typeof sheets>('game.sheets').then(setSheets).catch(() => {}) }, [view, sheets.length])

  const save = useCallback(async () => {
    const t = tabs.find((x) => isFileTab(x) && fileTabId(x.path) === active)
    if (!t || !isFileTab(t) || !project || t.readonly) return
    try {
      const r = await rpc<{ problems: ProblemItem[] }>('project.write_file', { project, path: t.path, text: t.text })
      setTabs((ts) => ts.map((x) => (isFileTab(x) && x.path === t.path ? { ...x, saved: t.text } : x)))
      setProblems(r.problems); say(`saved ${t.path}: ${r.problems.length} problem(s)`)
      setFiles((await rpc<{ files: FileItem[] }>('project.files', { project })).files)
    } catch (e) { fail(e) }
  }, [tabs, active, project, say, fail])

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); save() } }
    window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h)
  }, [save])

  const closeTab = (key: string) => {
    const t = tabs.find((x) => tabKey(x) === key)
    if (!t) return
    if (isFileTab(t) && t.text !== t.saved && !confirm(`Close ${t.path} without saving?`)) return
    const rest = tabs.filter((x) => tabKey(x) !== key); setTabs(rest)
    if (active === key) {
      setActive(rest.length ? tabKey(rest[rest.length - 1]) : null)
      if (t.kind === 'layout') setLayoutSel(null)
    }
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
    if (tabs.some((t) => isFileTab(t) && t.text !== t.saved) && !confirm('Discard unsaved changes in the open files?')) return
    setProject(null); setFiles([]); setTabs([]); setActive(null); setProblems([]); setPlan(null); setLayoutSel(null)
    try { localStorage.removeItem(SESSION) } catch { /* no storage */ }
  }
  const deleteProject = async (name: string) => {
    if (!confirm(`Delete project "${name}"?\n\nIt is moved to the trash folder inside the workspace, not erased.`)) return
    try {
      const r = await rpc<{ trash: string }>('project.delete', { project: name })
      say(`deleted ${name} (moved to ${r.trash})`)
      if (name === project) { setProject(null); setFiles([]); setTabs([]); setActive(null); setProblems([]); setPlan(null); setLayoutSel(null); try { localStorage.removeItem(SESSION) } catch { /* no storage */ } }
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
  const setProjectTarget = async (v: string) => {
    if (!project || v === target) return
    try {
      const p = await rpc<any>('project.get', { name: project })
      p.options = { ...(p.options || {}), output: v }
      await rpc('project.save', { project: p })
      setTarget(v)
      say(`project target set to ${v}`)
      await loadPlan()
    } catch (e) { fail(e) }
  }
  const toggleExpBundleLayouts = async (on: boolean) => {
    if (!project) return
    try {
      const p = await rpc<any>('project.get', { name: project })
      p.options = { ...(p.options || {}), experimental_bundle_layout_edits: on, experimental_bundle_layout_edits_explicit: true }
      await rpc('project.save', { project: p })
      setExpBundleLayouts(on)
      say(`experimental: layout edits via bundles ${on ? 'enabled' : 'disabled'}`)
      await loadPlan()
    } catch (e) { fail(e) }
  }
  const toggleExpTileSizes = async (on: boolean) => {
    if (!project) return
    try {
      const p = await rpc<any>('project.get', { name: project })
      p.options = { ...(p.options || {}), experimental_tile_sizes: on, experimental_tile_sizes_explicit: true }
      await rpc('project.save', { project: p })
      setExpTileSizes(on)
      say(`experimental: tile sizes ${on ? 'enabled' : 'disabled'}`)
    } catch (e) { fail(e) }
  }
  const toggleExpSlotEdits = async (on: boolean) => {
    if (!project) return
    try {
      const p = await rpc<any>('project.get', { name: project })
      p.options = { ...(p.options || {}), experimental_slot_edits: on, experimental_slot_edits_explicit: true }
      await rpc('project.save', { project: p })
      setExpSlotEdits(on)
      say(`experimental: slot edits ${on ? 'enabled' : 'disabled'}`)
    } catch (e) { fail(e) }
  }
  const buildBundles = async () => {
    if (!project) return
    try { const r = await rpc<{ job: string }>('build.bundles', { name: project }); say(`bundle build queued (${r.job})`); setPanel('output') } catch (e) { fail(e) }
  }
  const installBundles = async () => {
    if (!project) return
    let bundles: string[] = []
    let staleMsg = ''
    try {
      const pf = await rpc<any>('install.preflight', { project })
      if (pf) {
        if (pf.no_build) {
          say('No bundle build exists for this project yet. Build bundles first.')
          setPanel('build')
          return
        }
        const hard = (pf.blocked || []).filter((b: any) => !b.confirmation)
        if (hard.length > 0) {
          fail(new Error(hard.map((b: any) => b.message).join('; ')))
          return
        }
        const staleWarn = (pf.warnings || []).find((w: any) => w.code === 'stale_package')
        if (staleWarn) staleMsg = staleWarn.message
        bundles = (pf.file_operations || []).map((o: any) => String(o.rel_path)).filter(Boolean)
      }
    } catch { /* fallback to builds.list below */ }
    if (!bundles.length) {
      try {
        const bl = await rpc<any>('builds.list', { project, limit: 1 })
        const pkg = (bl?.packages || [])[0]
        if (pkg?.files) bundles = Object.keys(pkg.files)
      } catch { /* let install.bundles check and report if no build exists */ }
    }
    const listText = bundles.length ? `\n\nBundles to replace (${bundles.length}):\n- ${bundles.join('\n- ')}` : ''
    const staleText = staleMsg ? `\n\nWARNING (older package): ${staleMsg}` : ''
    if (!confirm(`Install the latest build of "${project}" into the game?${listText}${staleText}\n\nThe game must be closed. Every bundle it replaces must have a verified stock backup first; the copy is verified and rolled back on a mismatch. Native skins are not affected.`)) return
    try {
      const r = await rpc<any>('install.bundles', staleMsg ? { name: project, confirm_stale: true } : { name: project })
      say('installed: ' + JSON.stringify(r).slice(0, 400))
      setProjectRev((n) => n + 1)
      setPanel('output')
    } catch (e) { fail(e) }
  }
  const restoreStock = async () => {
    if (!confirm('Put the stock game files back for every bundle this editor changed?\n\nThe game must be closed. Hashes are verified afterwards.')) return
    try { const r = await rpc<any>('backup.restore', { backup: 'vanilla' }); say('restored: ' + JSON.stringify(r).slice(0, 400)); setPanel('output') } catch (e) { fail(e) }
  }
  const setModeP = (m: Mode) => { setMode(m); storeMode(m); if (m === 'simple' && !SIMPLE_VIEWS.includes(view)) setView('explorer'); if (m === 'simple' && (panel === 'build' || panel === 'preview')) setPanel('problems') }

  useEffect(() => {              // the mode, once the engine has said how many projects exist: a fresh install (no projects, nothing stored) is Simple, an existing one Advanced
    if (boot !== 'ready' || modeResolved.current || !state) return
    modeResolved.current = true
    const m = resolveMode(readStoredMode(), projects.length)
    setMode(m); storeMode(m)
    if (m === 'simple') setPanel((p) => (p === 'build' || p === 'preview' ? 'problems' : p))
  }, [boot, state, projects])

  useEffect(() => {
    if (boot !== 'ready' || restored.current || !state) return
    restored.current = true
    try { const s = JSON.parse(localStorage.getItem(SESSION) || 'null'); if (s?.project && projects.includes(s.project)) { if (s.view) setView(s.view); openProject(s.project, s.tabs || [], s.active) } } catch { /* no session */ }
  }, [boot, state, projects, openProject])
  useEffect(() => {
    if (!restored.current || !project) return
    localStorage.setItem(SESSION, JSON.stringify({ project, tabs: tabs.map(tabKey), active, view }))
  }, [project, tabs, active, view])

  const reloadClean = useCallback(async () => {
    setProjectRev((n) => n + 1)
    if (!project) return
    setFiles((await rpc<{ files: FileItem[] }>('project.files', { project })).files)
    setProblems((await rpc<{ problems: ProblemItem[] }>('project.problems', { project })).problems)
    const clean = tabs.filter((t): t is FileTab => isFileTab(t) && t.text === t.saved)
    const fresh = await Promise.all(clean.map(async (t) => { try { return [t.path, (await rpc<{ text: string }>('project.read_file', { project, path: t.path })).text] as const } catch { return [t.path, t.text] as const } }))
    setTabs((ts) => ts.map((t) => {
      if (!isFileTab(t)) return t
      const f = fresh.find((x) => x[0] === t.path)
      return f && t.text === t.saved ? { ...t, text: f[1], saved: f[1] } : t
    }))
  }, [project, tabs])

  useEffect(() => {
    if (boot !== 'ready') return
    rpc<{ status?: { state: string; message?: string } }>('update.status')
      .then((r) => {
        if (r?.status?.state === 'catalog_changed') {
          setGameUpdate({ state: 'catalog_changed', message: r.status.message })
        }
      })
      .catch(() => { /* ignore when offline or mocked */ })
  }, [boot])

  const rereadFromBanner = useCallback(async () => {
    setGameUpdate((g) => (g ? { ...g, rereading: true, errMsg: undefined } : g))
    try {
      const { job } = await rpc<{ job: string }>('snapshot.reread')
      for (;;) {
        const v = await rpc<{ state: string; error: string | null; result: { snapshot?: { catalog_hash?: string | null }; index?: { sheets?: number; tokens?: number } } | null }>('jobs.get', { id: job })
        if (v.state === 'done' || v.state === 'failed' || v.state === 'cancelled') {
          if (v.state === 'done' && v.result) {
            const ch = v.result.snapshot?.catalog_hash ?? '?'
            const sh = v.result.index?.sheets ?? 0
            const tk = v.result.index?.tokens ?? 0
            setGameUpdate({ state: 'done', doneMsg: `Done: reread complete (catalog ${ch}, ${sh} sheets, ${tk} colours, no layout changes).` })
            say(`re-read the game: catalog ${ch} · ${sh} sheets, ${tk} colours`)
            await reloadClean()
          } else {
            const s = await sayOfJobError(v.error || 'the re-read did not finish')
            setGameUpdate((g) => (g ? { ...g, rereading: false, errMsg: s.plain } : g))
          }
          break
        }
        await new Promise((r) => setTimeout(r, 150))
      }
    } catch (e) {
      const s = sayOf(e)
      setGameUpdate((g) => (g ? { ...g, rereading: false, errMsg: s.plain } : g))
    }
  }, [reloadClean, say])

  const dirty = (p: string) => { const t = tabs.find((x) => isFileTab(x) && x.path === p); return !!t && isFileTab(t) && t.text !== t.saved }
  const tab = tabs.find((t) => tabKey(t) === active)
  // UI1b step 3: style diagnostics from other modes are not shown while the Game Layouts view is on screen.
  const shownProblems = view === 'play' ? [] : problems
  const shown = useMemo(() => (mode === 'simple' ? files.filter(SIMPLE_FILES) : files), [files, mode])
  const running = Object.values(jobs).filter((j) => j.state === 'running' || j.state === 'queued')

  if (boot !== 'ready') return <div className="boot"><h1>FM Skin Studio</h1><p>{boot === 'connecting' ? 'Starting the engine ...' : boot}</p></div>

  const actW = actLabels ? 196 : mode === 'simple' ? 132 : 44                           // words need a wider rail (remembered in localStorage)
  const needsSetup = !!state && (!state.install || !state.vanilla || !state.indexed)   // a fresh install: the game has not been found and read yet (S1a)
  const panelTabs: PanelTab[] = mode === 'simple' ? ['problems', 'output'] : DEV_TOOLS ? ['problems', 'output', 'build', 'preview'] : ['problems', 'output', 'build']        // Simple mode hides Build/Preview; release builds hide dev-only Preview unless VITE_DEV_TOOLS=true
  const showStart = !project && !needsSetup && view === 'explorer'                      // the choices are the landing page in both modes while no project is open; the other views (render, layouts, ...) still work without a project
  const pickGameFolder = async () => {
    if ('__TAURI_INTERNALS__' in window) {
      const { open } = await import('@tauri-apps/plugin-dialog'); const r = await open({ directory: true, multiple: false, title: "Pick the folder that contains the game's fm.exe" }); return typeof r === 'string' ? r : undefined
    }
    return prompt("Folder of your Football Manager 27 install (the one that contains fm.exe):")?.trim() || undefined
  }

  return (
    <div className="app" style={{ gridTemplateColumns: `${actW}px ${sideW}px 1fr`, gridTemplateRows: `1fr ${panelH}px 24px` }}>
      <Gutter axis="x" value={sideW} min={160} max={640} def={250} onChange={setSideW} label="Side panel width" style={{ left: actW + sideW - 3, top: 0, bottom: 24 }} />
      <Gutter axis="y" invert value={panelH} min={80} max={560} def={210} onChange={setPanelH} label="Bottom panel height" style={{ left: actW + sideW, right: 0, bottom: 24 + panelH - 3 }} />
      {mode === 'simple' ? <nav className="activity simple" aria-label="Main navigation">
        {SIMPLE_NAV.map((n) => <button key={n.view} className={view === n.view ? 'on' : ''} title={n.title} aria-label={n.label} disabled={(n.needsProject && !project) || needsSetup} onClick={() => setView(n.view)}>{n.label}</button>)}
        <span className="grow" />
        <button title="Show every tool (the full editor)" aria-label="Show every tool (the full editor)" onClick={() => setModeP('advanced')}>Advanced</button>
      </nav> : <nav className={'activity' + (actLabels ? ' labelled' : '')} aria-label="Main navigation">
        {PRIMARY_NAV.map((n) => <button key={n.view} className={view === n.view ? 'on' : ''} title={n.title} aria-label={n.label}
          onClick={() => setView(n.view)}>{actLabels
            ? <><span className="act-ico">{n.letter}</span><span className="act-lbl">{n.label}</span></>
            : n.letter}</button>)}
        <button className={moreOpen ? 'on' : ''} title="More tools" aria-label="More tools" aria-expanded={moreOpen}
          data-testid="activity-more" onClick={() => setMoreOpen((v) => !v)}>{actLabels ? 'More tools' : '⋯'}</button>
        {moreOpen && <div className="act-more" data-testid="activity-more-menu" role="menu">
          {MORE_NAV.map((n) => <button key={n.view} role="menuitem" title={n.title} aria-label={n.label}
            className={view === n.view ? 'on' : ''} onClick={() => { setView(n.view); setMoreOpen(false) }}>{n.label}</button>)}
        </div>}
        <span className="grow" />
        <button title="Advanced mode (click for Simple)" aria-label="Advanced mode (click for Simple)" onClick={() => setModeP('simple')}>
          {actLabels ? <><span className="act-ico">S</span><span className="act-lbl">Advanced mode (click for Simple)</span></> : 'S'}</button>
        <button title={actLabels ? 'Show letters only in the activity bar' : 'Show names in the activity bar'}
          aria-label="Toggle activity bar labels" onClick={() => {
            const v = !actLabels; setActLabels(v)
            try { localStorage.setItem('studio.activityLabels', v ? '1' : '0') } catch { /* not remembered */ }
          }}>{actLabels ? '⇤' : '≡'}</button>
      </nav>}
      <aside className={'explorer' + (view === 'play' ? ' layout' : '')}>
        {view === 'search' && <Search project={project} onOpen={openFile} />}
        {view === 'game' && <div className="gameview"><div className="head">GAME STYLESHEETS ({sheets.length})</div>
          <input className="search" placeholder="Filter ..." value={sheetQ} onChange={(e) => setSheetQ(e.target.value)} />
          <ul>{sheets.filter((s) => s.name.toLowerCase().includes(sheetQ.toLowerCase())).map((s) => <li key={s.bundle + '|' + s.name} onClick={() => openSheet(s.name, s.bundle)} title={s.bundle}>{s.name}<small> {s.rules}</small></li>)}</ul></div>}
        {project && mode !== 'simple' && <div hidden={view !== 'assets'}><Guard name="Images"><Assets key={project} project={project} onChanged={reloadClean} say={say} /></Guard></div>}   {/* stays mounted so unsaved staging survives a view switch */}
        {view === 'layouts' && <Guard name="Layouts"><Layouts key={project ?? ''} project={project} target={target} onChanged={reloadClean} say={say} /></Guard>}
        {view === 'tiles' && <Guard name="Tile layout"><Tiles key={project ?? ''} project={project} target={target} expTileSizes={expTileSizes} onChanged={reloadClean} say={say} /></Guard>}
        {view === 'tables' && <Guard name="Table views"><Tables key={project ?? ''} project={project} target={target} onChanged={reloadClean} say={say} /></Guard>}
        {view === 'render' && mode !== 'simple' && <div className="rmodes" role="tablist">{(['layout', 'screen', 'table'] as const).map((m) => <button key={m} role="tab" aria-selected={rmode === m} className={rmode === m ? 'on' : ''} onClick={() => setRmode(m)}>{m}</button>)}</div>}
        {view === 'render' && mode !== 'simple' && rmode === 'layout' && <Guard name="Render browser"><RenderBrowser picked={rl ? rl.bundle + rl.path_id : null} onPick={setRl} say={say} /></Guard>}
        {view === 'checklist' && <Guard name="In-game checklist"><Checklist say={say} /></Guard>}
        {view === 'updates' && <Guard name="Game updates"><Updates project={project} say={say} onChanged={reloadClean} /></Guard>}
        {view === 'explore' && <Guard name="Assets"><Explore key={state?.install?.aa_dir ?? ''} say={say} /></Guard>}
        {view === 'install' && <Guard name="Install"><Install key={project ?? ''} project={project} say={say} /></Guard>}
        {view === 'custom' && <Guard name="Custom layouts"><CustomLayouts project={project} say={say} recovery={layoutRecovery} showRecoveryDialog={false} onRecoveryChange={reloadLayoutRecovery} /></Guard>}
        {view === 'play' && <Guard name="Game Layouts"><GameLayouts project={project}
          activeComposition={tab?.kind === 'layout' ? tab.name : null} selection={layoutSel}
          profile={layoutProfile} onProfileChange={setLayoutProfile}
          onOpenLayout={openLayout} onSelectTile={selectLayoutTile} /></Guard>}
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
        {gameUpdate && (
          <div className="notice" role="status" data-testid="game-updated-banner">
            <div>
              {gameUpdate.state === 'catalog_changed' && (
                <>
                  <strong>FM27 was updated. Studio needs to reread the game before installing anything.</strong>{' '}
                  <span className="small dim">Game Layouts keeps working throughout. Restore stock refuses old-build backups until reread completes.</span>{' '}
                  <button className="primary" disabled={!!gameUpdate.rereading} data-testid="game-updated-reread-now" onClick={rereadFromBanner}>
                    {gameUpdate.rereading ? 'Rereading ...' : 'Reread now'}
                  </button>
                </>
              )}
              {gameUpdate.state === 'done' && <span data-testid="game-updated-done">{gameUpdate.doneMsg}</span>}
              {gameUpdate.errMsg && <div className="warn small">{gameUpdate.errMsg}</div>}
            </div>
            <button onClick={() => setGameUpdate(null)} aria-label="Dismiss">×</button>
          </div>
        )}
        {layoutRecovery.length > 0 && <div className="pad"><LayoutRecoveryDialog items={layoutRecovery} project={project} say={say} onDone={reloadLayoutRecovery} /></div>}
        {notice && !needsSetup && <div className="notice" role="alert"><div>{notice.plain}</div><details><summary>details</summary><div className="mono small">{notice.details}</div></details><button onClick={() => setNotice(null)} aria-label="Dismiss">×</button></div>}
        {needsSetup && state ? <Guard name="Setup"><Setup state={state} refresh={refreshState} say={say} pickFolder={pickGameFolder} /></Guard> : view === 'skin_inspect' && mode !== 'simple' ? <Guard name="Inspect skin"><SkinInspect say={say} onOpenGameLayout={(c) => { setView('play'); openLayout(c) }} /></Guard> : view === 'injected_styles' && mode !== 'simple' ? <Guard name="Injected styles"><InjectedStyles key={project ?? ''} project={project} say={say} onChanged={reloadClean} onExportNative={exportNative} onBuildBundles={buildBundles} /></Guard> : view === 'playground' ? <Guard name="Playground"><Playground key={project ?? ''} project={project} say={say} onOpenInstall={() => setView('install')} /></Guard> : view === 'render' && mode === 'simple' ? <Guard name="Look at it"><LookAtIt project={project} say={say} start={lookStart} /></Guard> : view === 'assets' && mode === 'simple' && project ? <Guard name="Pictures"><Pictures key={project} project={project} say={say} onChanged={reloadClean} onLook={(s) => { setLookStart(s); setView('render') }} /></Guard> : view === 'findings' && mode !== 'simple' ? <Guard name="Findings"><Findings say={say} /></Guard> : view === 'share' && mode === 'simple' ? <Guard name="Share and undo"><Share project={project} projects={projects} say={say} onOpened={async (n) => { await refreshState(); await openProject(n); setView('palette') }} onChanged={async () => { await refreshState(); if (project) await openProject(project) }} /></Guard> : view === 'put' && project ? <Guard name="Put it in the game"><PutInGame key={project} project={project} say={say} /></Guard> : showStart ? <Guard name="Start"><Start projects={projects} say={say} onImport={mode === 'simple' ? () => setView('share') : importNative} onCreated={async (n) => { await refreshState(); await openProject(n); setView('palette') }} /></Guard> : view === 'render' && rmode === 'screen' ? <Guard name="Render screen"><RenderScreenView project={project} say={say} /></Guard> : view === 'render' && rmode === 'table' ? <Guard name="Render table"><RenderTableView project={project} say={say} /></Guard> : view === 'render' ? <Guard name="Render"><RenderCanvas layout={rl} say={say} project={project} highlight={highlight} onResult={(res, layout) => setLastRender({ res, layout })} onOpenFile={(f, l) => { setView('explorer'); openFile(f, l) }} /></Guard> : <>
        <div className="tabs" data-testid="main-tabs">{tabs.map((t) => {
          const key = tabKey(t)
          const label = t.kind === 'layout' ? t.name : t.path.split('/').pop()
          return <div key={key} data-testid="main-tab" data-kind={t.kind} className={'tab' + (t.kind === 'layout' ? ' layout' : '') + (key === active ? ' on' : '')}
            title={t.kind === 'layout' ? `Game Layout: ${t.name}` : t.path} onClick={() => setActive(key)}>
            {t.kind === 'layout' ? '◇ ' : ''}{label}
            {t.kind === 'file' && t.readonly ? ' (game)' : ''}{t.kind === 'file' && dirty(t.path) ? ' •' : ''}
            <button aria-label={`Close ${label}`} onClick={(e) => { e.stopPropagation(); closeTab(key) }}>×</button>
          </div>
        })}</div>
        <div className="surface">
          {tab && tab.kind === 'layout'
            ? <LayoutCanvas key={tab.name} project={project} composition={tab.name}
                profile={layoutProfile} tileRev={projectRev} expSlotEdits={expSlotEdits} onProfileChange={setLayoutProfile}
                onSelect={selectLayoutTile} say={say} />
            : tab && isFileTab(tab) ? <Editor path={tab.path} language={langOf(tab.path)} theme="vs-dark" value={tab.text}
            onChange={(v) => setTabs((ts) => ts.map((x) => (x.kind === 'file' && x.path === tab.path ? { ...x, text: v ?? '' } : x)))}
            onMount={(ed) => {
              editorRef.current = ed; registerTokenCompletion(); registerQuickFixes()
              let timer: ReturnType<typeof setTimeout> | undefined
              const run = () => { const m = ed.getModel(); if (m && m.uri.path.endsWith('.uss')) lint(m) }
              ed.onDidChangeModelContent(() => { clearTimeout(timer); timer = setTimeout(run, 400) })
              ed.onDidChangeModel(run); run()
              ed.onDidChangeCursorPosition((e: any) => { const m = ed.getModel(); setCaret(m ? { line: e.position.lineNumber, col: e.position.column, text: m.getLineContent(e.position.lineNumber) } : null) })
            }}
            options={{ minimap: { enabled: false }, fontSize: 13, automaticLayout: true, colorDecorators: true, tabSize: 4, readOnly: !!tab.readonly }} />
            : <div className="empty" data-testid="empty-editor">{view === 'play'
              ? 'Pick a composition from Game Layouts to open it in a tab here.'
              : project ? 'Open a file from the explorer. Ctrl+S saves; Ctrl+F / Ctrl+H find and replace; Ctrl+Z undo (per file).' : 'Open or create a project.'}</div>}
        </div>
        {(() => {
          const res = lastRender.res
          if (!res || !tab || !isFileTab(tab) || !caret || !res.origins) return null
          const rule = ruleAtLine(res.origins, tab.path, caret.line)
          const token = tokenAt(caret.text, caret.col)
          const rp = rule ? rulePaths(res.tree, rule.ids) : []
          const tp = token ? tokenPaths(res.tree, token) : []
          if (!rp.length && !tp.length) return null
          const show = (paths: string[]) => { setHighlight(paths); setView('render') }
          return <div className="caretbar" data-testid="caretbar">
            {rule && <span>This rule styles <b>{rp.length}</b> element(s) in {lastRender.layout?.name}</span>}
            {rp.length > 0 && <button onClick={() => show(rp)}>Show in render</button>}
            {token && tp.length > 0 && <span>Token <b className="mono">{token}</b> paints <b>{tp.length}</b></span>}
            {tp.length > 0 && <button onClick={() => show(tp)}>Show in render</button>}
          </div>
        })()}
        </>}
      </main>
      <section className="panel">
        <div className="ptabs">
          {panelTabs.map((p) => <button key={p} className={panel === p ? 'on' : ''} onClick={() => setPanel(p)}>{p.toUpperCase()}{p === 'problems' && shownProblems.length ? ` (${shownProblems.length})` : ''}</button>)}
          <span className="grow" />
          {tab?.kind !== 'layout' && <button className="pact" data-testid="panel-install" disabled={!project || !state?.vanilla || !!state?.running}
            onClick={installBundles} title="Install the latest bundle build into the game (FM27 closed; backup first). Never installs layout edits — use Apply on the layout tab.">Install into game</button>}
        </div>
        <div className="pbody">
          {panel === 'problems' && (shownProblems.length ? shownProblems.map((p, i) => <div key={i} className="prob" onClick={() => p.file.endsWith('.uss') || p.file.endsWith('.json') ? openFile(p.file, p.line) : undefined}><b>{p.file}</b>:{p.line ?? '?'} {p.message}</div>) : <div className="dim">{project ? 'No problems.' : ''}</div>)}
          {panel === 'output' && log.map((l, i) => <div key={i} className="mono">{l}</div>)}
          {DEV_TOOLS && panel === 'preview' && mode !== 'simple' && <Guard name="Preview"><Preview project={project} say={say} /></Guard>}
          {panel === 'build' && mode !== 'simple' && <div className="build">
            <p>{project ? <>Target of <b>{project}</b>: <select data-testid="build-target" value={target}
              onChange={(e) => setProjectTarget(e.target.value)}
              title="Styles and images target. Grid-composition layout edits go through custom-layout files (Apply on the layout tab) unless the experimental bundle setting is enabled.">
              <option value="native">native</option><option value="bundles">bundles</option>
            </select>.{' '}
            <label className="small"><input type="checkbox" data-testid="experimental-bundle-layouts" checked={expBundleLayouts}
              onChange={(e) => toggleExpBundleLayouts(e.target.checked)} /> experimental: layout edits via bundles</label>{' '}
            <label className="small" title="Not owner-confirmed in v1.5"><input type="checkbox" data-testid="experimental-tile-sizes" checked={expTileSizes}
              onChange={(e) => toggleExpTileSizes(e.target.checked)} /> experimental: tile sizes (not owner-confirmed)</label>{' '}
            <label className="small" title="Rolled back before an in-game check in v1.5"><input type="checkbox" data-testid="experimental-slot-edits" checked={expSlotEdits}
              onChange={(e) => toggleExpSlotEdits(e.target.checked)} /> experimental: slot edits (not confirmed in-game)</label></> : 'Open a project.'}</p>
            {expBundleLayouts && <div className="warn small" data-testid="experimental-bundle-layouts-warning">
              Warning: experimental: layout edits via bundles is on — bundle composition edits rewrite ui-tileslayouts_assets_all.bundle, move every stored composition in that bundle, and are ignored on screens customised in the game.
            </div>}
            {expTileSizes && <div className="warn small" data-testid="experimental-tile-sizes-warning">
              Warning: experimental: tile sizes is on — adding new tile sizes to TileDescriptions is not owner-confirmed in v1.5; test in-game after building and installing bundles.
            </div>}
            {expSlotEdits && <div className="warn small" data-testid="experimental-slot-edits-warning">
              Warning: experimental: slot edits is on — adding, removing, or reordering optional slots is not confirmed in-game in v1.5; test in-game after Apply and keep a rollback backup ready.
            </div>}
            {planErr && <div className="warn">{planErr}</div>}
            {plan && <div className="plan">
              <div className="dim">PLAN ({plan.target})</div>
              {plan.operations.map((o, i) => <div key={i}><b>{o.op}</b> {o.summary}</div>)}
              {plan.dropped.map((d, i) => <div key={i} className="warn">dropped: {d.item} - {d.reason}</div>)}
              {plan.warnings.map((w, i) => <div key={i} className="warn">{w}</div>)}
            </div>}
            <div className="build-actions" data-testid="build-actions">
              <button disabled={!project || problems.length > 0} onClick={exportNative}>Export native skin</button>
              <button disabled={!project || problems.length > 0 || !state?.vanilla} onClick={buildBundles}>Build bundles</button>
              <button disabled={!project || !state?.vanilla || !!state?.running} onClick={installBundles} title="Install the latest bundle build (game closed; backup first). Never installs layout edits — use Apply on the layout tab.">Install build</button>
              <button disabled={!state?.vanilla || !!state?.running} onClick={restoreStock} title="Restore the stock bundles">Restore stock</button>
              {problems.length > 0 && <span className="warn"> fix the problems first</span>}
            </div>
            {Object.values(jobs).slice(-4).map((j) => <div key={j.id} className="mono">{j.id} {j.title}: {j.state} {Math.round((j.progress || 0) * 100)}% {j.error || ''}</div>)}
          </div>}
        </div>
      </section>
      <footer className="status">
        <span className="click" data-testid="about-button" title="About FM Skin Studio" onClick={() => setAboutOpen(true)}>FM Skin Studio {state?.app_version || '1.5.0'}</span>
        <span title={state?.install?.game_dir}>FM27 {state?.vanilla?.game_build || state?.install?.version || (state?.install ? 'game found' : 'no game selected')}</span>
        <span data-testid="app-update-status" title="Checked automatically at launch"
          className={appUpdate.version ? 'ok' : ''}>
          {appUpdate.checking ? 'checking for app updates ...'
            : appUpdate.version ? `app update ${appUpdate.version} available`
              : appUpdate.error ? 'app update check unavailable' : 'app up to date'}
        </span>
        {appUpdate.version && <button className="linkish" data-testid="app-update-install"
          title="Closes the game's tools, installs and restarts. Refused while FM27 is running."
          disabled={appUpdate.installing} onClick={installAppUpdate}>
          {appUpdate.installing ? 'installing ...' : 'Install and restart'}
        </button>}
        {appUpdate.error && <span className="bad" data-testid="app-update-error">{appUpdate.error}</span>}
        <span className={state?.tamper?.state === 'clean' ? 'ok' : state?.tamper?.state === 'modified' || state?.tamper?.state === 'game_updated' ? 'bad' : ''} title={state?.tamper?.message}>{state?.tamper ? 'files ' + state.tamper.state : ''}</span>
        {state?.snapshot_mismatch && <span className="bad">wrong snapshot</span>}
        <span>{state?.running ? 'game running' : 'game closed'}</span>
        <span className="grow" />
        {running.length > 0 && <span>{running[0].label} {Math.round(running[0].progress * 100)}%</span>}
        <span>target: {target || '-'}</span>
        <span className="click" onClick={() => setModeP(mode === 'advanced' ? 'simple' : 'advanced')}>{mode}</span>
      </footer>
      {appUpdate.version && !appUpdateDismissed && <div className="modal-shade" data-testid="app-update-dialog">
        <div className="modal" role="dialog" aria-modal="true" aria-labelledby="app-update-title">
          <h2 id="app-update-title">A newer FM Skin Studio is available</h2>
          <p>Version <b>{appUpdate.version}</b> is available (you have {appUpdate.current || 'an older version'}). This check ran when the Studio launched.</p>
          <p className="small dim">Installing closes the Studio and the game tools, applies the signed update and restarts. Close FM27 first. Your projects and layout edits are kept in the workspace.</p>
          {appUpdate.installing && <p className="small">Downloading and installing ...</p>}
          {appUpdate.error && <p className="bad small" data-testid="app-update-dialog-error">{appUpdate.error}</p>}
          <div className="row">
            <button className="primary" data-testid="app-update-dialog-install" disabled={appUpdate.installing} onClick={installAppUpdate}>
              {appUpdate.installing ? 'Installing ...' : 'Install and restart'}
            </button>
            <button data-testid="app-update-dialog-later" onClick={() => setAppUpdateDismissed(true)}>Continue without updating</button>
          </div>
        </div>
      </div>}
      {aboutOpen && <div className="modal-shade" data-testid="about-dialog">
        <div className="modal" role="dialog" aria-modal="true" aria-labelledby="about-title">
          <h2 id="about-title">FM Skin Studio</h2>
          <p>Version <b>{state?.app_version || '1.5.0'}</b></p>
          <p className="small dim">Engine: {state?.app_version || '1.5.0'}{state?.unitypy ? ` · UnityPy ${state.unitypy}` : ''}</p>
          <p className="small dim">Open-source Football Manager 27 skin and layout editor. See CHANGELOG.md, USER-GUIDE.md, and THIRD_PARTY_NOTICES.md in the application folder.</p>
          <div className="row">
            <button className="primary" data-testid="about-close" onClick={() => setAboutOpen(false)}>Close</button>
          </div>
        </div>
      </div>}
    </div>
  )
}
