// Records a narrated walkthrough video of the app.
//
//   1. powershell -File tts.ps1 -OutDir out/audio     (narration -> WAV, offline Windows voice)
//   2. node record.mjs                                 (drives Chrome, records, muxes -> out/walkthrough.mp4)
//
// Env: APP_URL (default http://127.0.0.1:8000/), CHROME_PATH, REPO_URL.
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ffmpegPath from 'ffmpeg-static'
import { chromium } from 'playwright-core'

const here = path.dirname(fileURLToPath(import.meta.url))
const OUT = path.join(here, 'out')
const AUDIO = path.join(OUT, 'audio')
const APP_URL = process.env.APP_URL ?? 'http://127.0.0.1:8000/'
const REPO = process.env.REPO_URL ?? 'https://github.com/junaidshahzad3/spotter-truck-routing'
const CHROME =
  process.env.CHROME_PATH ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const W = 1440
const H = 900
const PAD_MS = 900 // breathing room after each scene's narration
const FAST = process.env.FAST === '1' // dry run: no narration waits, screenshot per scene, no mux

const scenes = JSON.parse(fs.readFileSync(path.join(here, 'narration.json'), 'utf8'))

function wavSeconds(file) {
  const b = fs.readFileSync(file)
  const byteRate = b.readUInt32LE(28)
  let off = 12
  while (off < b.length) {
    const id = b.toString('ascii', off, off + 4)
    const size = b.readUInt32LE(off + 4)
    if (id === 'data') return size / byteRate
    off += 8 + size
  }
  throw new Error(`no data chunk in ${file}`)
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

// ---------- page helpers -------------------------------------------------------------
const OVERLAY = () => {
  const install = () => {
    if (document.getElementById('__wt_cursor')) return
    const c = document.createElement('div')
    c.id = '__wt_cursor'
    Object.assign(c.style, {
      position: 'fixed', left: '0px', top: '0px', width: '22px', height: '22px',
      marginLeft: '-11px', marginTop: '-11px', borderRadius: '50%', zIndex: 2147483647,
      background: 'rgba(14,165,233,.35)', border: '2px solid #0284c7',
      pointerEvents: 'none', transition: 'transform .12s ease',
    })
    document.documentElement.appendChild(c)
    document.addEventListener('mousemove', (e) => {
      c.style.left = `${e.clientX}px`
      c.style.top = `${e.clientY}px`
    }, true)
    document.addEventListener('mousedown', () => (c.style.transform = 'scale(.7)'), true)
    document.addEventListener('mouseup', () => (c.style.transform = 'scale(1)'), true)
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install)
  else install()
}

async function caption(page, text) {
  await page.evaluate((t) => {
    let el = document.getElementById('__wt_caption')
    if (!el) {
      el = document.createElement('div')
      el.id = '__wt_caption'
      Object.assign(el.style, {
        position: 'fixed', right: '24px', bottom: '24px', zIndex: 2147483646,
        background: 'rgba(15,23,42,.88)', color: '#fff', padding: '10px 16px',
        borderRadius: '12px', font: '600 16px system-ui, Segoe UI, sans-serif',
        boxShadow: '0 10px 30px rgba(0,0,0,.25)', pointerEvents: 'none',
      })
      document.documentElement.appendChild(el)
    }
    el.textContent = t
  }, text)
}

async function moveTo(page, locator) {
  await locator.scrollIntoViewIfNeeded()
  const box = await locator.boundingBox()
  if (!box) throw new Error('element not visible')
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 25 })
  return box
}

async function click(page, locator) {
  await moveTo(page, locator)
  await sleep(250)
  await locator.click()
}

async function typeSlow(page, locator, text) {
  await click(page, locator)
  await locator.pressSequentially(text, { delay: 110 })
}

async function smoothScroll(page, px, ms, at = [W / 2, H / 2]) {
  await page.mouse.move(at[0], at[1], { steps: 10 })
  const steps = Math.max(1, Math.round(ms / 120))
  for (let i = 0; i < steps; i++) {
    await page.mouse.wheel(0, px / steps)
    await sleep(120)
  }
}

async function github(page, file, anchor, label) {
  await page.goto(`${REPO}/blob/main/${file}${anchor ? `#${anchor}` : ''}`, {
    waitUntil: 'domcontentloaded',
  })
  await page.waitForTimeout(2500)
  await caption(page, label)
}

// ---------- scenes -------------------------------------------------------------------
const actions = {
  async '01-intro'(page) {
    await page.setContent(`<!doctype html><html><body style="margin:0;height:100vh;display:grid;
      place-items:center;background:radial-gradient(circle at 30% 20%,#1e3a8a,#0f172a 60%);
      font-family:system-ui,Segoe UI,sans-serif;color:#fff">
      <div style="text-align:center">
        <div style="font-size:18px;letter-spacing:.3em;color:#7dd3fc;text-transform:uppercase">
          Spotter AI · Full Stack take-home</div>
        <h1 style="font-size:64px;margin:18px 0 8px">Weather-Aware Truck Routing</h1>
        <p style="font-size:24px;color:#cbd5e1;margin:0">React + Django · Valhalla · Open-Meteo · MapLibre</p>
        <p style="font-size:18px;color:#94a3b8;margin-top:36px">
          spotter-truck-routing-vh98.onrender.com · github.com/junaidshahzad3/spotter-truck-routing</p>
      </div></body></html>`)
  },

  async '02-form'(page) {
    await page.goto(APP_URL, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1500)
    await caption(page, '1 · Trip details')
    await typeSlow(page, page.getByLabel('Origin', { exact: true }), 'Dallas')
    await page.getByRole('option').first().waitFor({ timeout: 15000 })
    await sleep(600)
    await click(page, page.getByRole('option').first())
    await typeSlow(page, page.getByLabel('Destination', { exact: true }), 'Denver')
    await page.getByRole('option').first().waitFor({ timeout: 15000 })
    await sleep(600)
    await click(page, page.getByRole('option').first())
    await moveTo(page, page.getByLabel('Departure', { exact: true }))
    await sleep(800)
    const weight = page.getByLabel('Load weight', { exact: true })
    await click(page, weight)
    await weight.fill('')
    await weight.pressSequentially('42000', { delay: 120 })
    await sleep(500)
    await moveTo(page, page.getByRole('radio', { name: '10 mi' }))
    await sleep(500)
    await moveTo(page, page.getByRole('radio', { name: '50 mi' }))
    await sleep(500)
    await click(page, page.getByRole('radio', { name: '25 mi' }))
  },

  async '03-plan'(page) {
    await caption(page, '2 · Planning the trip')
    await click(page, page.getByRole('button', { name: 'Plan routes' }))
    await page.getByText(/^Recommended:/).waitFor({ timeout: 90000 })
    await sleep(1500)
  },

  async '04-results'(page) {
    await caption(page, '3 · Recommendation')
    await moveTo(page, page.getByText(/^Recommended:/))
    await sleep(3000)
    const cards = page.locator('section button[aria-pressed]')
    const n = await cards.count()
    for (let i = 0; i < n; i++) {
      await moveTo(page, cards.nth(i))
      await sleep(2200)
    }
  },

  async '05-map'(page) {
    await caption(page, '4 · Routes and checkpoints on the map')
    const cards = page.locator('section button[aria-pressed]')
    if ((await cards.count()) > 1) {
      await click(page, cards.nth(1))
      await sleep(2500)
      await click(page, cards.nth(0))
      await sleep(1500)
    }
    const cp = page.getByRole('button', { name: /^Mile 2\d0\b/ }).first()
    await moveTo(page, cp)
    await sleep(800)
    await cp.click()
    await sleep(3500)
    const cp2 = page.getByRole('button', { name: /^Mile 5\d0\b/ }).first()
    if (await cp2.count()) {
      await moveTo(page, cp2)
      await sleep(600)
      await cp2.click()
      await sleep(3000)
    }
  },

  async '06-heatmap'(page) {
    await caption(page, '5 · 0–48 hour weather heatmap')
    const closePopup = page.locator('.maplibregl-popup-close-button')
    if (await closePopup.count()) await click(page, closePopup.first())
    const zoomOut = page.getByRole('button', { name: 'Zoom out' })
    for (let i = 0; i < 3; i++) {
      await click(page, zoomOut)
      await sleep(500)
    }
    const slider = page.getByRole('slider', { name: 'Hours after departure' })
    const box = await moveTo(page, slider)
    // Drag across the slider by hand, then press play.
    await page.mouse.move(box.x + 4, box.y + box.height / 2, { steps: 15 })
    await page.mouse.down()
    await page.mouse.move(box.x + box.width * 0.75, box.y + box.height / 2, { steps: 60 })
    await page.mouse.up()
    await sleep(1200)
    await click(page, page.getByRole('button', { name: 'Play' }))
  },

  async '07-rules'(page) {
    await github(page, 'backend/routing/risk_rules.py', 'L3-L18', '6 · Risk rules from the brief')
    await sleep(10000)
    await smoothScroll(page, 1500, 9000)
  },

  async '08-classifier'(page) {
    await github(page, 'backend/routing/risk.py', 'L48-L86', '7 · The classifier')
    await sleep(4000)
    await smoothScroll(page, 450, 5000)
  },

  async '09-tests'(page) {
    await github(page, 'backend/tests/test_risk.py', 'L23-L61', '8 · Tests (band edges from the brief)')
    await sleep(8000)
    await smoothScroll(page, 1300, 9000)
  },

  async '10-ranking'(page) {
    await github(page, 'backend/routing/ranking.py', 'L66-L118', '9 · Ranking')
    await sleep(4000)
    await smoothScroll(page, 600, 5000)
  },

  async '11-architecture'(page) {
    await page.goto(`${REPO}#architecture`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(3000)
    await caption(page, '10 · Architecture and decisions')
    await sleep(5000)
    await smoothScroll(page, 1100, 16000)
  },

  async '12-wrap'(page) {
    await page.goto(`${REPO}/actions`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(2000)
    await caption(page, '11 · Deployment and next steps')
    await sleep(6000)
    await page.goto(APP_URL, { waitUntil: 'networkidle' })
    await caption(page, 'spotter-truck-routing-vh98.onrender.com')
  },
}

// ---------- main ---------------------------------------------------------------------
async function main() {
  fs.mkdirSync(OUT, { recursive: true })
  const durations = Object.fromEntries(
    scenes.map((s) => [s.id, wavSeconds(path.join(AUDIO, `${s.id}.wav`))]),
  )

  const browser = await chromium.launch({ executablePath: CHROME, headless: true })
  const context = await browser.newContext({
    viewport: { width: W, height: H },
    recordVideo: { dir: path.join(OUT, 'raw'), size: { width: W, height: H } },
    locale: 'en-US',
    timezoneId: 'America/Chicago',
  })
  await context.addInitScript(OVERLAY)
  const page = await context.newPage()
  page.setDefaultTimeout(15000)
  fs.mkdirSync(path.join(OUT, 'shots'), { recursive: true })
  const t0 = Date.now()
  const marks = []

  for (const scene of scenes) {
    const start = Date.now() - t0
    marks.push({ id: scene.id, startMs: start })
    console.log(`scene ${scene.id} @ ${(start / 1000).toFixed(1)}s`)
    try {
      await actions[scene.id](page)
    } catch (err) {
      console.warn(`  ! ${scene.id}: ${err.message.split('\n')[0]}`)
    }
    await page.screenshot({ path: path.join(OUT, 'shots', `${scene.id}.png`) }).catch(() => {})
    if (FAST) continue
    const minEnd = start + durations[scene.id] * 1000 + PAD_MS
    const wait = minEnd - (Date.now() - t0)
    if (wait > 0) await sleep(wait)
  }
  const totalMs = Date.now() - t0
  const video = page.video()
  await context.close()
  await browser.close()
  const raw = await video.path()
  console.log(`raw video ${raw} (${(totalMs / 1000).toFixed(1)}s)`)
  if (FAST) return

  // Place each narration clip at its scene start, mix, and mux with the video.
  const inputs = ['-i', raw]
  const filters = []
  scenes.forEach((s, i) => {
    inputs.push('-i', path.join(AUDIO, `${s.id}.wav`))
    const d = marks[i].startMs + 300
    filters.push(`[${i + 1}:a]aresample=48000,adelay=${d}|${d}[a${i}]`)
  })
  filters.push(
    `${scenes.map((_, i) => `[a${i}]`).join('')}amix=inputs=${scenes.length}:normalize=0,` +
      `apad,atrim=0:${(totalMs / 1000).toFixed(2)}[aout]`,
  )
  const out = path.join(OUT, 'walkthrough.mp4')
  execFileSync(
    ffmpegPath,
    [
      '-y', ...inputs,
      '-filter_complex', filters.join(';'),
      '-map', '0:v', '-map', '[aout]',
      '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
      '-r', '30', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart',
      out,
    ],
    { stdio: 'inherit' },
  )
  fs.writeFileSync(path.join(OUT, 'marks.json'), JSON.stringify(marks, null, 2))
  console.log(`\nwrote ${out}`)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
