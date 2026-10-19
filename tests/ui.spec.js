// @ts-check
// UI regression tests. POST /api/analyze is mocked, so these are deterministic
// and need no backend, Ollama, or evidence provider.
import { test as base, expect } from '@playwright/test';

const API = '**/api/analyze';

/** Builds an API response matching backend/app/models/schemas.py. */
function analysis(overrides = {}) {
  return {
    title: 'Provided Text',
    source: 'user-provided text',
    publisher: 'User Provided',
    author: null,
    publishedAt: null,
    riskScore: 40,
    riskLabel: 'Needs Verification',
    sourceReliability: 'Unknown',
    signals: [
      { name: 'Sensational Language', status: 'positive' },
      { name: 'Source Attribution', status: 'warning' },
    ],
    claims: [
      {
        id: 1,
        text: 'The council approved a budget of 5 million dollars.',
        status: 'Needs Verification',
        verificationStatus: 'INSUFFICIENT_EVIDENCE',
        evidence: [],
      },
      {
        id: 2,
        text: 'The vote took place on Monday.',
        status: 'Needs Verification',
        verificationStatus: 'SUPPORTED',
        evidence: [
          {
            source: 'Example Daily',
            description: 'Council passes budget in Monday vote',
            url: 'https://news.example.test/budget',
            relevance: 'SUPPORTS',
            explanation: 'The article directly reports the Monday vote.',
          },
        ],
      },
    ],
    analysisStatus: 'COMPLETE',
    degradationReasons: [],
    analysisExplanation:
      'Risk score: 40/100 (Needs Verification). Risk score is a heuristic warning indicator, not a probability of misinformation.',
    ...overrides,
  };
}

/** Fails the test on console errors, uncaught exceptions, or failed requests. */
const test = base.extend({
  pageIssues: [
    async ({ page }, use) => {
      const issues = [];
      page.on('pageerror', (error) => issues.push(`pageerror: ${error.message}`));
      page.on('console', (message) => {
        if (message.type() !== 'error') return;
        // The pages declare no favicon; browsers request /favicon.ico anyway.
        if (/favicon\.ico/.test(message.location().url) || /favicon/.test(message.text())) return;
        // Deliberate API failures (error statuses, aborted requests) are logged by
        // the browser as failed loads; the tests assert the UI's handling instead.
        // Chromium/WebKit: "Failed to load resource"; Firefox: "Cross-Origin Request Blocked".
        const apiFailure = /Failed to load resource|Cross-Origin Request Blocked/.test(message.text());
        if (apiFailure && /api\/analyze/.test(`${message.location().url} ${message.text()}`)) return;
        issues.push(`console: ${message.text()}`);
      });
      page.on('requestfailed', (request) => {
        if (request.url().includes('/api/analyze')) return; // aborted on purpose in one test
        if (request.url().endsWith('/favicon.ico')) return;
        // A load the browser cancelled (the theme script swaps the logo src, or the
        // page navigated away) is not a failed resource.
        if (/NS_BINDING_ABORTED|net::ERR_ABORTED|cancelled/i.test(request.failure()?.errorText || '')) return;
        issues.push(`requestfailed: ${request.url()} ${request.failure()?.errorText}`);
      });
      await use(issues);
      expect(issues, 'browser console errors / failed requests').toEqual([]);
    },
    { auto: true },
  ],
});

async function mockAnalysis(page, body, { status = 200, delayMs = 0 } = {}) {
  const requests = [];
  await page.route(API, async (route) => {
    requests.push(route.request().postDataJSON());
    if (delayMs) await new Promise((resolve) => setTimeout(resolve, delayMs));
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
  });
  return requests;
}

async function fill(page, type, value) {
  await page.goto('/index.html');
  await page.locator(`.input-tab[data-type="${type}"]`).click();
  await page.locator('#newsInput').fill(value);
  await page.locator('#terms').check();
}

test.describe('pages and navigation', () => {
  for (const path of ['/index.html', '/about.html', '/terms.html', '/results.html']) {
    test(`${path} renders without horizontal overflow`, async ({ page }) => {
      await page.goto(path);
      await expect(page.locator('h1:visible')).toHaveCount(1);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow).toBeLessThanOrEqual(0);
    });
  }

  test('results page without a stored result shows the fallback', async ({ page }) => {
    await page.goto('/results.html');
    await expect(page.locator('#resultFallback')).toBeVisible();
    await expect(page.locator('#resultsContent')).toBeHidden();
    await page.locator('#resultFallback a.primary-button').click();
    await expect(page).toHaveURL(/index\.html$/);
  });

  test('header links navigate between pages', async ({ page, isMobile }) => {
    await page.goto('/index.html');
    await page.locator('nav a[href="about.html"]').click();
    await expect(page).toHaveURL(/about\.html$/);
    await expect(page.locator('h1')).toHaveText('Better context for the news you read.');
    await page.locator('nav a').first().click();
    await expect(page).toHaveURL(/index\.html/);
    test.info().annotations.push({ type: 'viewport', description: isMobile ? 'mobile' : 'desktop' });
  });
});

test.describe('input validation', () => {
  test('empty and whitespace-only input cannot be submitted', async ({ page }) => {
    const requests = await mockAnalysis(page, analysis());
    await page.goto('/index.html');
    await page.locator('#terms').check();
    await expect(page.locator('#analyzeButton')).toBeDisabled();
    await page.locator('#newsInput').fill('    ');
    await expect(page.locator('#analyzeButton')).toBeDisabled();
    expect(requests).toHaveLength(0);
  });

  test('terms must be accepted before analyzing', async ({ page }) => {
    await page.goto('/index.html');
    await page.locator('#newsInput').fill('https://news.example.test/story');
    await expect(page.locator('#analyzeButton')).toBeDisabled();
  });

  for (const value of ['not a url', 'ftp://news.example.test/story', 'javascript:alert(1)']) {
    test(`malformed or unsupported URL is rejected client-side: ${value}`, async ({ page }) => {
      const requests = await mockAnalysis(page, analysis());
      await fill(page, 'url', value);
      await page.locator('#analyzeButton').click();
      await expect(page.locator('#validationMessage')).toHaveText(/valid article URL/);
      expect(requests).toHaveLength(0);
      await expect(page).toHaveURL(/index\.html$/);
    });
  }

  test('content over 100,000 characters is rejected client-side', async ({ page }) => {
    const requests = await mockAnalysis(page, analysis());
    await fill(page, 'text', 'a'.repeat(100_001));
    await page.locator('#analyzeButton').click();
    await expect(page.locator('#validationMessage')).toHaveText(/at most 100,000 characters/);
    expect(requests).toHaveLength(0);
  });
});

test.describe('analysis workflow', () => {
  test('text analysis shows loading, then renders the API result', async ({ page }) => {
    const requests = await mockAnalysis(page, analysis(), { delayMs: 1200 });
    await fill(page, 'text', 'The council approved a budget of 5 million dollars on Monday.');
    await page.locator('#analyzeButton').click();

    await expect(page.locator('#loadingOverlay')).toHaveClass(/visible/);
    await expect(page.locator('#loadingOverlay')).toHaveAttribute('aria-hidden', 'false');
    await expect(page.locator('#analyzeButton')).toBeDisabled();
    await page.waitForURL(/results\.html$/);

    expect(requests).toEqual([
      { type: 'text', content: 'The council approved a budget of 5 million dollars on Monday.' },
    ]);
    await expect(page.locator('#riskScore')).toHaveText('40');
    await expect(page.locator('#riskLabel')).toHaveText('Needs Verification');
    await expect(page.locator('.risk-summary')).toHaveAttribute('data-level', 'moderate');
    await expect(page.locator('#riskMeter span')).toHaveAttribute('style', /width: 40%/);
    await expect(page.locator('#degradedNotice')).toBeHidden();
    await expect(page.locator('#signalList li')).toHaveCount(2);
    await expect(page.locator('#reliabilityValue')).toHaveText('Unknown');
    await expect(page.locator('#resultInput')).toHaveText(/council approved a budget/);

    const claims = page.locator('#claimsList .claim');
    await expect(claims).toHaveCount(2);
    await expect(claims.nth(0).locator('.status').first()).toHaveText('Insufficient Evidence');
    await expect(claims.nth(0)).toContainText('remains unverified');
    await expect(claims.nth(1).locator('.status').first()).toHaveText('Supported');

    // Evidence is collapsed until requested, and links open safely.
    const evidence = claims.nth(1).locator('.evidence');
    await expect(evidence).toBeHidden();
    await claims.nth(1).locator('.evidence-button').click();
    await expect(evidence).toBeVisible();
    await expect(evidence).toContainText('Example Daily: Council passes budget in Monday vote');
    const link = evidence.locator('a');
    await expect(link).toHaveAttribute('href', 'https://news.example.test/budget');
    await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    await expect(link).toHaveAttribute('target', '_blank');
  });

  test('URL analysis renders article metadata', async ({ page }) => {
    await mockAnalysis(page, analysis({
      title: 'Council passes budget',
      source: 'https://news.example.test/budget',
      publisher: 'Example Daily',
      sourceReliability: 'Moderate',
      riskScore: 22,
      riskLabel: 'Low Risk',
    }));
    await fill(page, 'url', 'https://news.example.test/budget');
    await page.locator('#analyzeButton').click();
    await page.waitForURL(/results\.html$/);
    await expect(page.locator('#publisherValue')).toHaveText('Example Daily');
    await expect(page.locator('#sourceValue')).toHaveText('https://news.example.test/budget');
    await expect(page.locator('#riskLabel')).toHaveText('Low Risk');
    await expect(page.locator('.risk-summary')).toHaveAttribute('data-level', 'low');
  });

  test('insufficient evidence is not presented as misinformation or a probability', async ({ page }) => {
    await mockAnalysis(page, analysis({
      claims: [analysis().claims[0]],
    }));
    await fill(page, 'text', 'A claim with no evidence found.');
    await page.locator('#analyzeButton').click();
    await page.waitForURL(/results\.html$/);

    const results = page.locator('#resultsContent');
    await expect(results).not.toContainText(/false|fake|misinformation confirmed/i);
    await expect(page.locator('#claimsList')).toContainText('Insufficient Evidence');
    await expect(page.locator('#claimsList')).toContainText('remains unverified');
    // The score is shown out of 100, never as a percentage chance.
    await expect(page.locator('#riskScore')).toHaveText('40');
    await expect(page.locator('.risk-summary h2')).toContainText('/ 100');
    await expect(page.locator('.risk-summary h2')).not.toContainText('%');
    await expect(page.locator('#assessmentNote')).toContainText('not a probability');
  });

  test('degraded analysis lists readable reasons', async ({ page }) => {
    await mockAnalysis(page, analysis({
      analysisStatus: 'DEGRADED',
      degradationReasons: ['GDELT: Evidence provider timed out', 'GNEWS: Evidence provider returned no results'],
    }));
    await fill(page, 'text', 'Some article text.');
    await page.locator('#analyzeButton').click();
    await page.waitForURL(/results\.html$/);
    await expect(page.locator('#degradedNotice')).toBeVisible();
    await expect(page.locator('#degradationReasons li')).toHaveText([
      'The GDELT evidence source timed out.',
      'The GNews evidence source returned no results for at least one claim.',
    ]);
    await expect(page.locator('#riskScore')).toHaveText('40');
  });

  test('analysis that produced nothing is shown as not assessed, not scored', async ({ page }) => {
    await mockAnalysis(page, analysis({
      riskScore: 50,
      analysisStatus: 'DEGRADED',
      degradationReasons: ['Ollama connection failed'],
      signals: [],
      claims: [],
    }));
    await fill(page, 'text', 'Some article text.');
    await page.locator('#analyzeButton').click();
    await page.waitForURL(/results\.html$/);
    await expect(page.locator('#riskScore')).toHaveText('—');
    await expect(page.locator('#riskLabel')).toHaveText('Not assessed');
    await expect(page.locator('.risk-summary')).toHaveAttribute('data-level', 'unassessed');
    await expect(page.locator('#riskMeter span')).toHaveAttribute('style', /width: 0%/);
    await expect(page.locator('#degradationReasons li')).toHaveText([
      'The local AI service (Ollama) could not be reached.',
    ]);
    await expect(page.locator('#resultsContent')).not.toContainText('50');
  });

  test('"Analyze Another" returns home and clears the stored result', async ({ page }) => {
    await mockAnalysis(page, analysis());
    await fill(page, 'text', 'Some article text.');
    await page.locator('#analyzeButton').click();
    await page.waitForURL(/results\.html$/);
    await page.locator('#analyzeAnother').click();
    await expect(page).toHaveURL(/index\.html$/);
    expect(await page.evaluate(() => sessionStorage.getItem('tndAnalysisResult'))).toBeNull();
  });

  test('results survive a page refresh', async ({ page }) => {
    await mockAnalysis(page, analysis());
    await fill(page, 'text', 'Some article text.');
    await page.locator('#analyzeButton').click();
    await page.waitForURL(/results\.html$/);
    await page.reload();
    await expect(page.locator('#resultsContent')).toBeVisible();
    await expect(page.locator('#riskScore')).toHaveText('40');
  });
});

test.describe('errors and retry', () => {
  const cases = [
    { status: 502, detail: 'Unable to fetch the external webpage.' },
    { status: 400, detail: 'Invalid URL.' },
    { status: 422, detail: 'No article content could be extracted.' },
    { status: 503, detail: 'Too many analyses are running. Please try again shortly.' },
    { status: 500, detail: 'The analysis failed unexpectedly. Please try again.' },
  ];
  for (const { status, detail } of cases) {
    test(`HTTP ${status} shows the API message and allows retry`, async ({ page }) => {
      await mockAnalysis(page, { detail }, { status });
      await fill(page, 'url', 'https://news.example.test/story');
      await page.locator('#analyzeButton').click();
      await expect(page.locator('#validationMessage')).toHaveText(detail);
      await expect(page.locator('#loadingOverlay')).not.toHaveClass(/visible/);
      await expect(page.locator('.loading-step.complete')).toHaveCount(0);
      await expect(page.locator('#analyzeButton')).toBeEnabled();
      await expect(page).toHaveURL(/index\.html$/);

      // Retry with a working backend.
      await page.unroute(API);
      await mockAnalysis(page, analysis());
      await page.locator('#analyzeButton').click();
      await page.waitForURL(/results\.html$/);
      await expect(page.locator('#riskScore')).toHaveText('40');
    });
  }

  test('a non-string error detail is never shown as raw JSON', async ({ page }) => {
    await mockAnalysis(page, { detail: [{ loc: ['body'], msg: 'x', input: 'secret' }] }, { status: 422 });
    await fill(page, 'text', 'Some article text.');
    await page.locator('#analyzeButton').click();
    await expect(page.locator('#validationMessage')).not.toHaveText('');
    await expect(page.locator('#validationMessage')).not.toContainText('{');
    await expect(page.locator('#validationMessage')).not.toContainText('secret');
  });

  test('unreachable backend shows a connection message', async ({ page }) => {
    await page.route(API, (route) => route.abort('connectionrefused'));
    await fill(page, 'text', 'Some article text.');
    await page.locator('#analyzeButton').click();
    await expect(page.locator('#validationMessage')).toContainText('Unable to connect to the TND analysis server');
    await expect(page.locator('#analyzeButton')).toBeEnabled();
  });

  test('an invalid response body is rejected, not rendered', async ({ page }) => {
    await mockAnalysis(page, { riskScore: 'high' });
    await fill(page, 'text', 'Some article text.');
    await page.locator('#analyzeButton').click();
    await expect(page.locator('#validationMessage')).toHaveText('The analysis server returned an invalid response.');
    await expect(page).toHaveURL(/index\.html$/);
  });

  test('a second click while analyzing sends only one request', async ({ page }) => {
    const requests = await mockAnalysis(page, analysis(), { delayMs: 1500 });
    await fill(page, 'text', 'Some article text.');
    await page.locator('#analyzeButton').click();
    // Typing re-enables the button; the in-flight guard must still hold.
    await page.locator('#newsInput').press('End');
    await page.locator('#newsInput').pressSequentially('!');
    await page.locator('#analyzeButton').dispatchEvent('click');
    await page.waitForURL(/results\.html$/);
    expect(requests).toHaveLength(1);
  });
});

test.describe('safe rendering', () => {
  test('untrusted article, claim, and evidence content is rendered as text', async ({ page }) => {
    const payload = '<img src=x onerror="window.__tndXss=1">';
    await mockAnalysis(page, analysis({
      title: payload,
      source: payload,
      publisher: payload,
      signals: [{ name: payload, status: 'warning' }],
      degradationReasons: [payload],
      analysisStatus: 'DEGRADED',
      claims: [
        {
          id: 1,
          text: payload,
          status: payload,
          verificationStatus: 'MIXED',
          evidence: [
            { source: payload, description: payload, url: 'javascript:window.__tndXss=2', explanation: payload, relevance: 'RELATED_ONLY' },
          ],
        },
      ],
    }));
    await fill(page, 'text', payload);
    await page.locator('#analyzeButton').click();
    await page.waitForURL(/results\.html$/);
    await page.locator('.evidence-button').click();

    expect(await page.evaluate(() => window.__tndXss)).toBeUndefined();
    await expect(page.locator('#resultsContent img[src="x"]')).toHaveCount(0);
    await expect(page.locator('#publisherValue')).toHaveText(payload);
    await expect(page.locator('#claimsList blockquote')).toHaveText(`“${payload}”`);
    // A javascript: evidence URL must not become a link.
    await expect(page.locator('#claimsList .evidence a')).toHaveCount(0);
  });
});

test.describe('themes', () => {
  for (const [choice, scheme, expected] of [
    ['light', 'dark', 'light'],
    ['dark', 'light', 'dark'],
    ['system', 'dark', 'dark'],
    ['system', 'light', 'light'],
  ]) {
    test(`${choice} theme with OS ${scheme} resolves to ${expected}`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto('/index.html');
      await page.locator(`[data-theme-choice="${choice}"]`).click();
      await expect(page.locator('html')).toHaveAttribute('data-theme', expected);
      await expect(page.locator(`[data-theme-choice="${choice}"]`)).toHaveAttribute('aria-pressed', 'true');
      await expect(page.locator('.theme-logo').first()).toHaveAttribute('src', `logo(${expected}mode).png`);
      // The choice persists to other pages.
      await page.goto('/about.html');
      await expect(page.locator('html')).toHaveAttribute('data-theme', expected);
    });
  }
});
