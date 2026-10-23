# TND brag plan

**Input:** this project (`lloydaq/TND-The-News-Detector`), read from the local checkout.
**Format:** landscape 1920×1080, 30fps, 21.5s.
**Tone:** `polished` with a dry, deadpan edge. Creative direction: *a calm, honest second look.*

## Answers

- **What is it?** A web app that gives you a second look at a news article: paste a URL or text, a local model (Ollama) pulls out the checkable claims, TND searches GNews and GDELT for related coverage, checks each claim against the evidence it actually retrieved, and returns an explainable 0–100 risk score.
- **Who is it for?** Readers who want to check an article before they believe or share it.
- **What sets it apart?** It is honest about its limits: it does not decide what is true, *insufficient evidence* is never treated as false, failures are listed instead of hidden, and the model runs locally.
- **Most striking claim:** "TND does not decide what is true." (README)
- **Visual hook:** the amber `40 / 100 · Needs Verification` score with its meter, and the `Insufficient Evidence` pills in the dark theme.
- **Real UI / flow:** home page → URL typed, terms ticked, **Analyze News →** → the real loading checklist (Extracting content → Analyzing language → Evaluating credibility signals → Checking claims) → results page → claims with evidence.
- **Share caption:** "A news detector that won't tell you what's true — it shows you the claims, the evidence it actually found, and what it couldn't check."

## Angle

The joke and the brag are the same thing: a "detector" that refuses to give a verdict. Lead with that, then prove it is a real working tool by showing the flow, and land on its core rule: insufficient evidence ≠ false.

## Visual identity (from `frontend/css/style.css`, dark theme)

- Background `#0f172a`, surface `#172033`, line `#334155`, muted `#94a3b8`
- Text/headings `#f8fafc`, accent `#4c8ed0` (steel-blue night), amber `#a55d12`
- Fonts: Manrope 800 (display), DM Sans (body)
- Logo: `frontend/logo(darkmode).png`

## Source material

The video loads the **real** `frontend/index.html` and `frontend/results.html` in iframes with the real CSS, JS, fonts and logo, and drives them frame by frame. Results come from a seeded `sessionStorage` result.

**Stand-ins (no personal data):** the article URL is a fictional `news.example.com` address, and the evidence publisher is the fictional "Example Daily" (the same placeholder the UI tests use). The claim text is the README's public ESA Juice demo text.

## Storyboard

| # | Time | Scene | On screen | Audio |
|---|---|---|---|---|
| 1 | 0.0–3.5 | **Hook** | "A news detector that won't tell you what's true." words land one by one; "On purpose." in accent blue at 1.6s | Soft D-major pad; one low note per word line |
| 2 | 3.5–5.5 | **Reveal** | TND logo scales in from a glow; "Know Before You Believe." rises under it | Swell + bell hit on the logo |
| 3 | 5.5–8.5 | **Paste** | Real home page in a browser frame. Caption "Paste an article." URL types in, cursor ticks the terms box, clicks **Analyze News →** | Beat enters; soft key ticks; in-key click |
| 4 | 8.5–11.5 | **Check** | Real loading overlay; four steps tick off on the beat. Caption "Every claim, checked against real coverage." | Each step = a pluck from the chord |
| 5 | 11.5–15.0 | **Score** | Real results page; camera on the risk card; score counts 0→40, meter fills amber, "Needs Verification". Caption "An explainable score. Not a verdict." | Rising ticks into a soft hit |
| 6 | 15.0–18.5 | **Claims** | Scroll to Claims; zoom on "Insufficient Evidence" pills and an expanded evidence item. Caption "Insufficient evidence is never called false." | Groove continues |
| 7 | 18.5–21.5 | **Outro** | Logo, "Know Before You Believe.", "Local AI with Ollama · Evidence from GNews & GDELT", repo link | Final chord rings out and fades |

Transitions dip through the background (old content out, then new in) so there is no muddy double exposure. Captions are held at least ~0.3s per word once fully on screen.

## Music

An original synthesized bed: D major, 120 BPM (beat 0.5s, bar 2s), progression D – Bm – G – A. Pad-only during the hook, a soft kick and hats from the paste scene, a final D chord at the outro. SFX are tuned to the key and mixed under the music.
