// Monaco runs from the bundled package (no CDN: the shell must work offline). USS is CSS-shaped, so the CSS language service
// highlights it; completion for var(--token) comes from the engine's token list.
import * as monaco from 'monaco-editor'
import { loader } from '@monaco-editor/react'
import editorWorker from 'monaco-editor/editor/editor.worker?worker'
import cssWorker from 'monaco-editor/language/css/css.worker?worker'
import jsonWorker from 'monaco-editor/language/json/json.worker?worker'
import { rpc } from './engine'

;(self as any).MonacoEnvironment = {
  getWorker(_: unknown, label: string) {
    if (label === 'json') return new jsonWorker()
    if (label === 'css') return new cssWorker()
    return new editorWorker()
  },
}
loader.config({ monaco })

let registered = false
export function registerTokenCompletion() {
  if (registered) return
  registered = true
  monaco.languages.registerCompletionItemProvider('css', {
    triggerCharacters: ['-', '('],
    async provideCompletionItems(model, position) {
      const before = model.getValueInRange({ startLineNumber: position.lineNumber, startColumn: 1, endLineNumber: position.lineNumber, endColumn: position.column })
      const m = /(--[\w-]*)$/.exec(before)
      if (!m) return { suggestions: [] }
      let rows: any[] = []
      try { rows = (await rpc('tokens.list', { q: m[1], colours: false })).rows } catch { return { suggestions: [] } }
      const range = new monaco.Range(position.lineNumber, position.column - m[1].length, position.lineNumber, position.column)
      return {
        suggestions: rows.slice(0, 60).map((t) => ({
          label: t.name, kind: monaco.languages.CompletionItemKind.Variable, insertText: t.name, range,
          detail: t.resolved ? `${t.resolved.rgb} alpha ${t.resolved.a.toFixed(3)}` : String(t.value),
          documentation: `chain: ${t.chain.join(' -> ')}  reach: ${t.reach}`,
        })),
      }
    },
  })
}
interface Diag { line: number; col: number; end_col: number; severity: 'error' | 'warning' | 'info'; code: string; message: string; suggest?: string }
const SEV = { error: monaco.MarkerSeverity.Error, warning: monaco.MarkerSeverity.Warning, info: monaco.MarkerSeverity.Info }
const suggestions = new Map<string, string>()   // `${model uri}|${line}:${col}` -> replacement text for the highlighted range

/** Ask the engine for diagnostics of a USS model and show them as markers (and remember quick-fix suggestions). */
export async function lint(model: monaco.editor.ITextModel) {
  const version = model.getVersionId()
  let diags: Diag[] = []
  const sheet = /\/styles\/([A-Za-z0-9_.-]+)\.uss$/.exec(model.uri.path)?.[1]       // styles/<GameSheet>.uss: its rules go to that game sheet
  try { diags = (await rpc<{ diagnostics: Diag[] }>('uss.diagnostics', { text: model.getValue(), ...(sheet ? { sheet } : {}) })).diagnostics } catch { return }
  if (model.isDisposed() || model.getVersionId() !== version) return        // the text moved on; a newer lint is coming
  for (const k of [...suggestions.keys()]) if (k.startsWith(model.uri.toString() + '|')) suggestions.delete(k)
  monaco.editor.setModelMarkers(model, 'uss', diags.map((d) => {
    if (d.suggest) suggestions.set(`${model.uri.toString()}|${d.line}:${d.col}`, d.suggest)
    return { severity: SEV[d.severity], message: d.message, code: d.code, startLineNumber: d.line, startColumn: d.col, endLineNumber: d.line, endColumn: d.end_col }
  }))
}

let actions = false
export function registerQuickFixes() {
  if (actions) return
  actions = true
  monaco.languages.registerCodeActionProvider('css', {
    provideCodeActions(model, _range, context) {
      const out: monaco.languages.CodeAction[] = []
      for (const m of context.markers) {
        const fix = suggestions.get(`${model.uri.toString()}|${m.startLineNumber}:${m.startColumn}`)
        if (!fix) continue
        out.push({ title: `Replace with ${fix}`, kind: 'quickfix', isPreferred: true, diagnostics: [m],
          edit: { edits: [{ resource: model.uri, versionId: model.getVersionId(), textEdit: { range: new monaco.Range(m.startLineNumber, m.startColumn, m.endLineNumber, m.endColumn), text: fix } }] } })
      }
      return { actions: out, dispose() {} }
    },
  }, { providedCodeActionKinds: ['quickfix'] })
}
export { monaco }
