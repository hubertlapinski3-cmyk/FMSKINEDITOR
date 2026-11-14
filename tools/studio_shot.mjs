// Drives the Studio page (Vite dev server + a running engine) in headless Edge through its DevTools port and saves a screenshot: an end-to-end check of the Render view.
// usage: node tools/studio_shot.mjs DEBUG_PORT PAGE_URL OUT_PNG [LAYOUT_NAME]
import { writeFileSync } from 'node:fs'
const [port, url, out, layout = 'LoansTile_4x2'] = process.argv.slice(2)
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
async function target() {
  for (let i = 0; i < 80; i++) {
    try { const l = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); const p = l.find((t) => t.type === 'page' && !t.url.startsWith('devtools')); if (p) return p } catch { /* not up */ }
    await sleep(500)
  }
  throw new Error('no page target')
}
const page = await target()
const ws = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej })
let id = 0; const pending = new Map()
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id) } }
const send = (method, params = {}) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })) })
const ev = async (expression) => { const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }); if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 400)); return r.result?.result?.value }
const waitFor = async (expr, what, ms = 60000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { const v = await ev(expr); if (v) return v } catch { /* page still loading */ } await sleep(400) }
  let seen = ''; try { seen = await ev(`(document.querySelector('.rbrowser') || document.body).innerText.replace(/\\s+/g, ' ').slice(0, 400)`) } catch { /* ignore */ }
  throw new Error('timeout waiting for ' + what + '; the page shows: ' + seen) }
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a)

await send('Emulation.setDeviceMetricsOverride', { width: 1500, height: 950, deviceScaleFactor: 1, mobile: false })
await send('Page.navigate', { url })
await waitFor(`document.body && document.body.innerText.includes('PROJECTS')`, 'the Studio to start')
log('Studio started')
log('open the R view:', await ev(`(() => { const b = [...document.querySelectorAll('.activity button')].find(x => (x.title||'').startsWith('Render')); if (!b) return 'no R button'; b.click(); return 'clicked' })()`))
await waitFor(`!!document.querySelector('.rbrowser li')`, 'the layout list')
log('browser header:', await ev(`document.querySelector('.rbrowser .head').innerText`))
await ev(`document.querySelector('.rbrowser .search').focus()`)
await send('Input.insertText', { text: layout })                       // real text input, as typing would be
await waitFor(`[...document.querySelectorAll('.rbrowser li')].some(li => li.firstChild && li.firstChild.textContent === ${JSON.stringify(layout)})`, 'the filtered layout')
log('pick', layout, await ev(`(() => { const li = [...document.querySelectorAll('.rbrowser li')].find(li => li.firstChild.textContent === ${JSON.stringify(layout)}); li.click(); return 'clicked' })()`))
await waitFor(`document.querySelectorAll('.rstage .rnode').length > 3`, 'the render')
await sleep(500)
log('render:', JSON.stringify(await ev(`({ nodes: document.querySelectorAll('.rstage .rnode').length, flagged: document.querySelectorAll('.rstage .rnode[data-flag]').length,
  notice: document.querySelector('.rnotice')?.innerText.slice(0, 80), bar: document.querySelector('.rbar')?.innerText.replace(/\\s+/g, ' ').slice(0, 120) })`)))
// gutter: drag the side panel divider 150 px to the right with real mouse events and read the result back
const g = await ev(`(() => { const e = document.querySelector('.gutter.x:not(.inflow)'); const r = e.getBoundingClientRect(); return { x: r.left + r.width / 2, y: 300, before: e.getAttribute('aria-valuenow') } })()`)
await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: g.x, y: g.y, button: 'left', clickCount: 1 })
for (let k = 1; k <= 5; k++) await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: g.x + 30 * k, y: g.y, button: 'left' })
await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: g.x + 150, y: g.y, button: 'left', clickCount: 1 })
await sleep(300)
log('side gutter: before', g.before, 'after', await ev(`document.querySelector('.gutter.x:not(.inflow)').getAttribute('aria-valuenow')`), '| remembered:', await ev(`localStorage.getItem('studio.sideW')`))
// click the title text element and read the explain panel
log('select the first flagged element:', await ev(`(() => { const n = document.querySelector('.rstage .rnode[data-flag]'); if (!n) return 'none'; n.click(); return n.getAttribute('data-path') })()`))
await sleep(400)
log('explain:', JSON.stringify(await ev(`({ head: document.querySelector('.rexplain .mono')?.innerText, rules: document.querySelectorAll('.rexplain .rtable')[0]?.rows.length, props: document.querySelectorAll('.rexplain .rtable')[1]?.rows.length })`)))
const shot = await send('Page.captureScreenshot', { format: 'png' })
writeFileSync(out, Buffer.from(shot.result.data, 'base64'))
log('screenshot written:', out)
await send('Browser.close').catch(() => {})
ws.close()
