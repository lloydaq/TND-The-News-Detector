# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Everyday news readers. The typical moment: someone meets an article, link, or forwarded story and wants a second look before they believe or share it. They are not professional fact-checkers and arrive with a single article in hand, not a research workflow.

## Product Purpose

Trustworthy News Detector (TND) analyzes a news article, given as a URL or pasted text, and surfaces signals that may warrant further verification: claims and how the retrieved evidence bears on them, content signals such as sensational language, and source information. It returns an explainable, heuristic assessment rather than a verdict.

Success means the reader pauses, understands *why* parts of an article may need checking, and goes on to verify against original and independent sources. Success does not mean the reader treats TND's output as the truth.

## Positioning

TND does not tell you what to believe. It shows its work: each claim is checked independently against bounded, provenance-preserving evidence from GNews and GDELT, classified as `SUPPORTED`, `CONTRADICTED`, `MIXED`, `INSUFFICIENT_EVIDENCE`, or `UNVERIFIABLE`, and the result says plainly when the analysis is incomplete (`DEGRADED`) instead of looking more certain than it is. Syndicated copies are not counted as independent corroboration. "A second look, not the final word."

## Operating Context

- Flow: submit a URL or article text, accept the Terms, analyze (extracting content → analyzing language → evaluating credibility signals → checking claims), then review the results page (risk score out of 100, source, content signals, claims, degradation notice).
- Analysis can be slow and can partially fail. Evidence providers or the local Ollama model may be unavailable, and the result then carries sanitized `degradationReasons`.
- Extraction cannot run JavaScript, bypass paywalls, or recover content that a site doesn't send. Some sites block requests or return unsupported content, and those cases surface as errors.

## Capabilities and Constraints

- Frontend: static HTML/CSS/JavaScript (`frontend/`), with Light / System / Dark theme switching. Backend: Python, FastAPI, Trafilatura, HTTPX, Ollama, GNews, GDELT.
- The risk score is an explainable heuristic. It is **not** a probability and not proof of truth or falsity, and the UI must never present it as one.
- HTTPS, metadata completeness, publisher names, search ranking, and result counts are transparency indicators only, never credibility or truth scores.
- Terminology: claim statuses as listed above; evidence relations `SUPPORTS`, `CONTRADICTS`, `RELATED_ONLY`, `INSUFFICIENT_INFORMATION`; analysis status `DEGRADED`.
- The frontend calls the live backend (`POST /api/analyze`); verified by the live Playwright suite.
- Deployment: intended as a public website soon. Public hosting requires rate limiting and body limits at the proxy or gateway. Local development is the current deployment assumption.

## Brand Commitments

- Canonical name: **Trustworthy News Detector**, abbreviated **TND**. (The README's "The News Detector" is outdated.)
- Tagline in use: "Know Before You Believe."
- Logo assets: `frontend/logo(lightmode).png`, `frontend/logo(darkmode).png`.
- Voice: calm, careful, and non-authoritative. Hedged where the system is uncertain ("may require further verification"), never alarmist, and never claiming definitive fact-checking authority.

## Evidence on Hand

- Real product copy: About, How It Works, and Terms & Conditions (last updated October 4, 2026).
- No user testimonials, usage numbers, accuracy benchmarks, press, or partner endorsements exist. Future work must not fabricate them, and must not imply that accuracy has been measured.

## Product Principles

1. **Signals, not verdicts.** Every surface frames output as something to verify, never as truth or falsehood.
2. **Show the reasoning.** Claims, evidence, and provenance stay visible and traceable. A score never appears without its explanation.
3. **Honest about incompleteness.** Degraded, partial, or unverifiable results are stated plainly and are never dressed up as confident.
4. **Respect the reader's judgment.** Encourage the pause and the check. Don't persuade or alarm.
5. **Plain language first.** The audience is everyday readers, so explain internal vocabulary rather than exposing it raw.
