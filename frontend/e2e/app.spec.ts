import { expect, test, type Page } from '@playwright/test'

// The e2e API answers as if it were 20:30 IST on Diwali 2026; pin the browser clock to match
// so "updated ... ago" labels read like they would live.
const REPLAY = new Date('2026-11-08T15:00:00Z')

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(REPLAY)
})

const nav = (page: Page) => page.getByRole('navigation', { name: 'Main' })

async function go(page: Page, label: string) {
  await nav(page).getByRole('link', { name: label }).click()
}

test('switches between the tabs and keeps the place', async ({ page }) => {
  await page.goto('/air?place=delhi')
  await expect(page.getByRole('region', { name: 'Pollution map and current air quality' })).toBeVisible()
  await expect(page.getByText('Data completeness').filter({ visible: true }).first()).toBeVisible()

  await go(page, 'Temperature')
  await expect(page).toHaveURL(/\/temperature\?place=delhi/)
  await expect(page.getByRole('heading', { name: 'Temperature trend' })).toBeVisible()

  await go(page, 'Heat')
  await expect(page).toHaveURL(/\/heat\?place=delhi/)
  await expect(page.getByRole('heading', { name: 'Heat stress' })).toBeVisible()

  await go(page, 'Air quality')
  await expect(page).toHaveURL(/\/air\?place=delhi/)
  await expect(nav(page).getByRole('link', { name: 'Air quality' })).toHaveAttribute('aria-current', 'page')
})

test('opens Places from the location button and changes the city', async ({ page }) => {
  await page.goto('/air?place=delhi')
  await page.getByRole('button', { name: /Change place\. Current place: Delhi/ }).click()
  const drawer = page.getByRole('dialog')
  await expect(drawer).toBeVisible()
  await drawer.getByRole('region', { name: 'Covered cities' }).getByRole('button', { name: /Shimla/ }).click()
  await expect(page).toHaveURL(/place=shimla/)
  await expect(page.getByRole('button', { name: /Current place: Shimla, Himachal Pradesh/ })).toBeVisible()
  // Shimla has no CPCB station in the seed: values must be labelled as estimates
  await expect(page.getByText(/No CPCB station in this district/)).toBeVisible()
})

test('switches the AQI chart between hourly, 10 days and monthly', async ({ page }, info) => {
  test.skip(info.project.name === 'phone', 'same component; covered on desktop')
  await page.goto('/air?place=delhi')
  for (const name of ['10 days', 'Monthly', 'Hourly']) {
    const tab = page.getByRole('tab', { name })
    await tab.click()
    await expect(tab).toHaveAttribute('aria-selected', 'true')
  }
})

test('answers from VayuKavach data with sources and refuses off-topic questions', async ({ page }) => {
  await page.goto('/ask?place=delhi')
  await page.getByLabel('Your question').fill('What is the AQI in Delhi right now?')
  await page.getByRole('button', { name: 'Send question' }).click()
  const sources = page.getByRole('list', { name: 'Sources' }).first()
  await expect(sources).toBeVisible()
  await expect(sources).toContainText(/CPCB|OpenAQ|CAMS/)
  await expect(page.getByRole('log')).toContainText(/AQI[^0-9]*\d{2,3}/)

  await page.getByLabel('Your question').fill('Who will win the cricket match?')
  await page.getByRole('button', { name: 'Send question' }).click()
  await expect(page.getByTestId('refusal')).toBeVisible()
})

test('shows the data report for Diwali with a working CSV download', async ({ page, request }) => {
  await page.goto('/air?place=delhi')
  await page.getByRole('link', { name: 'Data report' }).filter({ visible: true }).first().click()
  await expect(page).toHaveURL(/\/reports\?place=delhi/)
  await page.getByLabel('Date').fill('2026-11-08')
  await expect(page.getByText('Silent stations', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Show all' }).click()
  await expect(page.getByRole('table')).toBeVisible()
  const href = await page.getByRole('link', { name: /Download CSV/ }).getAttribute('href')
  const csv = await request.get(href!)
  expect(csv.ok()).toBeTruthy()
  expect(await csv.text()).toMatch(/^station_id,station,pollutant/)
})

test('alerts page says when no channel is set up and previews the message', async ({ page }) => {
  await page.goto('/air?place=delhi')
  await go(page, 'Alerts')
  await expect(page.getByText(/WhatsApp alerts are not set up/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Send code' })).toBeDisabled()
  await expect(page.locator('pre')).toContainText('VayuKavach · Delhi')
})
