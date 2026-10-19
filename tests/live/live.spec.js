// @ts-check
// Live integration tests: real backend (http://127.0.0.1:8000), Ollama and the
// GNews/GDELT providers. Run with `npm run test:e2e:live` while the backend is
// running. Provider outages make results DEGRADED; that is expected and is
// checked for honest reporting, not treated as a failure.
import { test, expect } from '@playwright/test';

const ARTICLE_URL =
  'https://www.esa.int/Newsroom/Press_Releases/ESA_s_Juice_lifts_off_on_quest_to_discover_secrets_of_Jupiter_s_icy_moons';
const ARTICLE_TEXT =
  'The European Space Agency launched the Juice spacecraft on 14 April 2023 on an Ariane 5 rocket from Kourou, ' +
  "French Guiana. The mission will study Jupiter's icy moons Ganymede, Callisto and Europa and is due to arrive " +
  'at Jupiter in July 2031.';

test.beforeAll(async ({ request }) => {
  const health = await request.get('http://127.0.0.1:8000/api/health');
  expect(health.ok(), 'start the backend before running live tests').toBeTruthy();
});

async function analyze(page, type, value) {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/index.html');
  await page.locator(`.input-tab[data-type="${type}"]`).click();
  await page.locator('#newsInput').fill(value);
  await page.locator('#terms').check();
  await page.locator('#analyzeButton').click();
  await expect(page.locator('#loadingOverlay')).toHaveClass(/visible/);
  await page.waitForURL(/results\.html$/, { timeout: 240_000 });
  expect(errors).toEqual([]);
  return page.evaluate(() => JSON.parse(sessionStorage.getItem('tndAnalysisResult') || 'null'));
}

/** Checks that what results.html shows is exactly what the API returned. */
async function expectRenderedFaithfully(page, result) {
  const unassessed = result.analysisStatus === 'DEGRADED' && !result.signals.length && !result.claims.length;
  await expect(page.locator('#riskScore')).toHaveText(unassessed ? '—' : String(result.riskScore));
  await expect(page.locator('#riskLabel')).toHaveText(unassessed ? 'Not assessed' : result.riskLabel);
  await expect(page.locator('#degradedNotice')).toBeVisible({ visible: result.analysisStatus === 'DEGRADED' });
  await expect(page.locator('#claimsList .claim')).toHaveCount(result.claims.length);
  for (const [index, claim] of result.claims.entries()) {
    const element = page.locator('#claimsList .claim').nth(index);
    await expect(element.locator('blockquote')).toHaveText(`“${claim.text}”`);
    await expect(element.locator('.evidence-item')).toHaveCount(claim.evidence.length);
    // Unresolved claims must never be labelled as refuted.
    if (['INSUFFICIENT_EVIDENCE', 'UNVERIFIABLE'].includes(claim.verificationStatus)) {
      await expect(element.locator('.status').first()).not.toHaveText('Contradicted');
    }
  }
  await expect(page.locator('body')).not.toContainText(/Traceback|File "|Exception:/);
}

test('real text analysis completes and renders faithfully', async ({ page }) => {
  const result = await analyze(page, 'text', ARTICLE_TEXT);
  expect(result.sourceReliability).toBe('Unknown'); // pasted text has no source to rate
  await expectRenderedFaithfully(page, result);
  test.info().annotations.push({
    type: 'outcome',
    description: `${result.analysisStatus} ${result.riskScore} ${result.riskLabel}; reasons: ${result.degradationReasons.join(' | ') || 'none'}`,
  });
});

test('real URL analysis completes and renders faithfully', async ({ page }) => {
  const result = await analyze(page, 'url', ARTICLE_URL);
  expect(result.publisher).toBeTruthy();
  await expect(page.locator('#publisherValue')).toHaveText(result.publisher);
  await expectRenderedFaithfully(page, result);
  test.info().annotations.push({
    type: 'outcome',
    description: `${result.analysisStatus} ${result.riskScore} ${result.riskLabel}; reasons: ${result.degradationReasons.join(' | ') || 'none'}`,
  });
});

test('unreachable article URL shows an honest error without internals', async ({ page }) => {
  await page.goto('/index.html');
  await page.locator('.input-tab[data-type="url"]').click();
  await page.locator('#newsInput').fill('https://tnd-unreachable-check.invalid/news/story');
  await page.locator('#terms').check();
  await page.locator('#analyzeButton').click();
  await expect(page.locator('#validationMessage')).toHaveText('Unable to fetch the external webpage.', { timeout: 60_000 });
  await expect(page).toHaveURL(/index\.html$/);
});
