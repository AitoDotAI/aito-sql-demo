#!/usr/bin/env node
/**
 * Cold-load route tests: does a pasted link open exactly what the sender saw?
 *
 * Every case starts a FRESH browser context — no storage, no history, no prior
 * page — because that is what a recipient has. A test that reuses a context
 * can pass on state the sender's browser happened to be holding, which is the
 * whole failure mode being checked.
 *
 * Usage:
 *   node frontend/scripts/route-state.cjs
 *   BASE_URL=http://127.0.0.1:8800 CHROME_PATH=$(which google-chrome-stable) ...
 *
 * The backend must be serving a built frontend (./do build && ./do backend).
 */

const { chromium } = require('playwright-core')

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8800').replace(/\/$/, '')
const CHROME = process.env.CHROME_PATH || (process.platform === 'linux' ? '/usr/bin/chromium' : undefined)
const SETTLE = Number(process.env.SETTLE_MS || 3000)

// `networkidle` is deliberately NOT used: /scoring polls while it computes and
// analytics keeps a request open, so idle never arrives and every case dies on
// a 30s timeout. The pages are asserted after an explicit settle instead.

/** Assertions get the page after a cold load of `path`. */
const CASES = [
  {
    name: 'cards: default expands the first card',
    path: '/',
    async check(page) {
      const open = await page.locator('.card.card-open').count()
      expect(open === 1, `expected 1 open card, found ${open}`)
    },
  },
  {
    name: 'cards: ?card= opens that card, not the default',
    path: '/?card=duty',
    async check(page) {
      const openKeys = await page.locator('.card.card-open').evaluateAll(
        (els) => els.map((e) => e.getAttribute('data-card')))
      expect(openKeys.length === 1, `expected exactly 1 open card, got ${openKeys.length}`)
      expect(openKeys[0] === 'duty', `expected 'duty' open, got ${openKeys[0]}`)
    },
  },
  {
    name: 'cards: an unknown ?card= opens nothing rather than guessing',
    path: '/?card=no-such-card',
    async check(page) {
      const open = await page.locator('.card.card-open').count()
      expect(open === 0, `expected nothing open for an unknown key, found ${open}`)
    },
  },
  {
    name: 'patterns: ?open= expands that pattern',
    path: '/patterns?open=1',
    async check(page) {
      const cases = await page.locator('.pat-cases').count()
      expect(cases === 1, `expected 1 expanded pattern, found ${cases}`)
      const which = await page.locator('.pat').nth(1).locator('.pat-cases').count()
      expect(which === 1, 'the expanded pattern is not the one the URL named')
    },
  },
  {
    name: 'patterns: an out-of-range ?open= expands nothing',
    path: '/patterns?open=999',
    async check(page) {
      const cases = await page.locator('.pat-cases').count()
      expect(cases === 0, `expected nothing expanded, found ${cases}`)
    },
  },
  {
    name: 'explore: ?where= opens that slice (regression guard — already worked)',
    path: '/explore?where=climate:hot,cooling:passive',
    async check(page) {
      const trail = await page.locator('.trail').innerText()
      expect(/climate/.test(trail) && /hot/.test(trail), `trail lacks the slice: ${trail}`)
      expect(/cooling/.test(trail) && /passive/.test(trail), `trail lacks the slice: ${trail}`)
    },
  },
]

/**
 * CLICKING must move the URL, not just loading one.
 *
 * Every case above does a `goto`, which reads the URL correctly even if
 * navigation is broken — so they would all pass while the address bar never
 * changed as you used the page, and nothing would ever BE copyable. In a Next
 * static export `router.push` can silently do nothing (it waits on a server
 * payload that is never generated), which is exactly this failure and exactly
 * what a goto-only test cannot see. Flagged by the ecommerce lane.
 */
async function interactions(page, log) {
  const failures = []

  async function check(name, fn) {
    try {
      await fn()
      log(`  ok    ${name}`)
    } catch (e) {
      failures.push([name, e.message])
      log(`  FAIL  ${name}\n          ${e.message}`)
    }
  }

  await check('cards: expanding a card puts it in the address bar', async () => {
    await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(SETTLE)
    const second = page.locator('.card').nth(1)
    const key = await second.getAttribute('data-card')
    await second.locator('.card-toggle').click()
    await page.waitForTimeout(1200)
    const url = page.url()
    expect(url.includes(`card=${key}`), `url is '${url}', expected card=${key}`)
    const openNow = await page.locator(`.card.card-open[data-card="${key}"]`).count()
    expect(openNow === 1, 'the clicked card did not open')
  })

  await check('patterns: showing cases puts it in the address bar', async () => {
    await page.goto(`${BASE}/patterns`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(SETTLE)
    await page.locator('.pat').first().locator('.sql-toggle').click()
    await page.waitForTimeout(1200)
    expect(page.url().includes('open=0'), `url is '${page.url()}', expected open=0`)
  })

  await check('explore: narrowing puts the slice in the address bar', async () => {
    await page.goto(`${BASE}/explore`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(SETTLE)
    await page.locator('.chip').first().click()
    await page.waitForTimeout(2000)
    expect(/where=/.test(page.url()), `url is '${page.url()}', expected a where=`)
  })

  return failures
}

/** Back must return to the previous view, not to a re-rendered default. */
async function backForward(page, log) {
  await page.goto(`${BASE}/?card=thermal`, { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(SETTLE)
  await page.goto(`${BASE}/?card=duty`, { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(SETTLE)

  await page.goBack({ waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(SETTLE)
  let keys = await page.locator('.card.card-open').evaluateAll(
    (els) => els.map((e) => e.getAttribute('data-card')))
  expect(keys[0] === 'thermal', `back gave '${keys[0]}', expected 'thermal'`)

  await page.goForward({ waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(SETTLE)
  keys = await page.locator('.card.card-open').evaluateAll(
    (els) => els.map((e) => e.getAttribute('data-card')))
  expect(keys[0] === 'duty', `forward gave '${keys[0]}', expected 'duty'`)
  log('  ok    back/forward preserve the card')
}

function expect(cond, message) {
  if (!cond) throw new Error(message)
}

async function main() {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true })
  const failures = []
  const log = console.log
  log(`cold-load route tests — ${BASE}\n`)

  for (const c of CASES) {
    // A fresh CONTEXT, not just a fresh page: a recipient has no storage.
    const context = await browser.newContext()
    const page = await context.newPage()
    try {
      await page.goto(`${BASE}${c.path}`, { waitUntil: 'domcontentloaded' })
      await page.waitForTimeout(SETTLE)
      await c.check(page)
      log(`  ok    ${c.name}`)
    } catch (e) {
      failures.push([c.name, e.message])
      log(`  FAIL  ${c.name}\n          ${e.message}`)
    }
    await context.close()
  }

  let context = await browser.newContext()
  let page = await context.newPage()
  for (const f of await interactions(page, log)) failures.push(f)
  await context.close()

  context = await browser.newContext()
  page = await context.newPage()
  try {
    await backForward(page, log)
  } catch (e) {
    failures.push(['back/forward', e.message])
    log(`  FAIL  back/forward\n          ${e.message}`)
  }
  await context.close()
  await browser.close()

  log('')
  if (failures.length) {
    log(`${failures.length} failed`)
    return 1
  }
  log('every link opens what it says')
  return 0
}

main().then((code) => process.exit(code)).catch((e) => {
  console.error(e)
  process.exit(1)
})
