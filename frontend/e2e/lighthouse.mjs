// Lighthouse on the Air tab (production build, seeded e2e API).
// Fails when accessibility < 90 (phone or desktop) or desktop performance < 80. Phone
// performance is printed and must be 80+ when run on a laptop; shared CI runners are slower
// than Lighthouse's simulated phone assumes, so there it only warns.
//   npm run lighthouse
import { execFileSync, spawn } from 'node:child_process'
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const API = 'http://localhost:8010'
const WEB = 'http://localhost:5191'
const out = mkdtempSync(join(tmpdir(), 'vk-lh-'))
const kids = []

async function waitFor(url, ms = 120_000) {
  const end = Date.now() + ms
  while (Date.now() < end) {
    try {
      if ((await fetch(url)).ok) return
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 1000))
  }
  throw new Error(`timed out waiting for ${url}`)
}

function start(cmd, args, env = {}) {
  const p = spawn(cmd, args, { env: { ...process.env, ...env }, stdio: 'inherit' })
  kids.push(p)
}

let failed = false
try {
  try {
    await fetch(`${API}/health`)
  } catch {
    start('./e2e/start-api.sh', [])
  }
  await waitFor(`${API}/health`)
  execFileSync('npx', ['vite', 'build', '--outDir', join(out, 'dist')], {
    env: { ...process.env, VITE_API_BASE_URL: API },
    stdio: 'inherit',
  })
  start('npx', ['vite', 'preview', '--outDir', join(out, 'dist'), '--port', '5191', '--strictPort'])
  await waitFor(WEB)

  for (const form of ['mobile', 'desktop']) {
    const file = join(out, `${form}.json`)
    execFileSync(
      'npx',
      ['--yes', 'lighthouse@12.8.2', `${WEB}/air?place=delhi`,
        ...(form === 'desktop' ? ['--preset=desktop'] : []),
        '--only-categories=performance,accessibility,best-practices,seo',
        '--chrome-flags=--headless=new --no-sandbox', '--output=json', `--output-path=${file}`, '--quiet'],
      { stdio: 'inherit' },
    ) // prettier-ignore
    const cats = JSON.parse(readFileSync(file, 'utf8')).categories
    const s = Object.fromEntries(Object.entries(cats).map(([k, v]) => [k, Math.round(v.score * 100)]))
    console.log(`${form}: ${JSON.stringify(s)}`)
    if (s.accessibility < 90) failed = true
    if (s.performance < 80) {
      if (form === 'desktop' || !process.env.CI) failed = true
      else console.warn('phone performance below 80 on this CI runner (simulated slow phone)')
    }
  }
} finally {
  for (const k of kids) k.kill('SIGTERM')
}
if (failed) {
  console.error('Lighthouse thresholds not met')
  process.exit(1)
}
