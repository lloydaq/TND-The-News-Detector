// @ts-check
import { defineConfig, devices } from '@playwright/test';

/**
 * UI regression tests mock POST /api/analyze, so they need only the static
 * frontend. Live tests (tests/live/) call the real backend, Ollama and the
 * evidence providers; they run only via `npm run test:e2e:live`, which sets
 * TND_LIVE=1, because their outcome depends on external services.
 */
const live = Boolean(process.env.TND_LIVE);
const python = process.platform === 'win32' ? 'python' : 'python3';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // python -m http.server has a 5-connection listen backlog; more parallel
  // workers make it refuse static asset requests.
  workers: process.env.CI ? 1 : 2,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    // 5500 is in the backend's default CORS allowlist.
    baseURL: 'http://127.0.0.1:5500',
    trace: 'on-first-retry',
  },
  webServer: {
    command: `${python} -m http.server 5500 --bind 127.0.0.1 --directory frontend`,
    url: 'http://127.0.0.1:5500/index.html',
    reuseExistingServer: !process.env.CI,
  },
  projects: live
    ? [
        {
          name: 'live',
          testMatch: 'live/**/*.spec.js',
          timeout: 300_000,
          use: { ...devices['Desktop Chrome'] },
        },
      ]
    : [
        { name: 'chromium', testIgnore: 'live/**', use: { ...devices['Desktop Chrome'] } },
        { name: 'firefox', testIgnore: 'live/**', use: { ...devices['Desktop Firefox'] } },
        { name: 'webkit', testIgnore: 'live/**', use: { ...devices['Desktop Safari'] } },
        { name: 'mobile-chromium', testIgnore: 'live/**', use: { ...devices['Pixel 7'] } },
      ],
});
