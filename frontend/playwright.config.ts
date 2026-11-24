import { defineConfig, devices } from '@playwright/test'

// End-to-end tests run their own API (port 8010, seeded *_e2e database, clock pinned to Diwali
// night 2026) and Vite (port 5190), so they never touch the dev servers or real data.
export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://localhost:5190',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'phone', use: { ...devices['Pixel 7'] } },
  ],
  webServer: [
    {
      command: './e2e/start-api.sh',
      url: 'http://localhost:8010/health',
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'npx vite --port 5190 --strictPort',
      env: { VITE_API_BASE_URL: 'http://localhost:8010' },
      url: 'http://localhost:5190',
      timeout: 60_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
})
