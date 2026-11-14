// Reads the `data-rects` attribute a rendered page leaves on <body> through the browser's DevTools port, then closes the browser.
// usage: node tools/cdp_measure.mjs PORT URL_SUFFIX [OUT_PNG WIDTH HEIGHT]     (prints the attribute's JSON, or exits 2)
const [port, suffix] = [process.argv[2], process.argv[3]]
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
async function page() {
  for (let i = 0; i < 60; i++) {
    try {
      const l = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
      const p = l.find((t) => t.type === 'page' && t.url.endsWith(suffix))
      if (p) return p
    } catch { /* browser not up yet */ }
    await sleep(500)
  }
  return null
}
const p = await page()
if (!p) { console.error('no page'); process.exit(2) }
const ws = new WebSocket(p.webSocketDebuggerUrl)
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej })
let id = 0; const pending = new Map()
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id) } }
const send = (method, params = {}) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })) })
let out = null
for (let i = 0; i < 60 && !out; i++) {
  const r = await send('Runtime.evaluate', { expression: `document.body && document.body.getAttribute('data-rects')`, returnByValue: true })
  out = r.result?.result?.value || null
  if (!out) await sleep(250)
}
if (process.argv[4]) {
  const [png, w, h] = [process.argv[4], Number(process.argv[5]), Number(process.argv[6])]
  const s = await send('Page.captureScreenshot', { format: 'png', clip: { x: 0, y: 0, width: w, height: h, scale: 2 } })
  if (s.result?.data) (await import('node:fs')).writeFileSync(png, Buffer.from(s.result.data, 'base64'))
}
await send('Browser.close').catch(() => {})
ws.close()
if (!out) { console.error('no measurement'); process.exit(2) }
console.log(out)
