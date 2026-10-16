# TND — The News Detector

TND (The News Detector) is a web-based project designed to explore AI-assisted news analysis and misinformation detection.

The project currently includes a web frontend, a FastAPI backend, and an article extraction pipeline. The analysis engine is under development.

## Features

* **Article Extraction:** Extracts article text and metadata from supported URLs.
* **Metadata Detection:** Attempts to identify the title, publisher, author, and publication date.
* **REST API:** Provides endpoints for health checks and article analysis.
* **Structured Results:** Defines response formats for risk assessments, signals, claims, and supporting evidence.
* **Web Interface:** Includes pages for the main interface, results, about information, and terms and conditions.
* **Dark and Light Branding:** Includes separate logo assets for dark and light modes.

## Tech Stack

### Frontend

* HTML
* CSS
* JavaScript

### Backend

* Python
* FastAPI
* Uvicorn
* Pydantic
* HTTPX
* Trafilatura
* Beautiful Soup

## Project Structure

```text
TND-The-News-Detector/
├── backend/
│   ├── app/
│   │   ├── models/
│   │   ├── routes/
│   │   ├── services/
│   │   └── main.py
│   └── requirements.txt
├── frontend/
│   ├── css/
│   ├── js/
│   ├── index.html
│   ├── results.html
│   ├── about.html
│   └── terms.html
├── .gitignore
└── README.md
```

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/lloydaq/TND-The-News-Detector.git
cd TND-The-News-Detector
```

### 2. Set Up the Backend

Create and activate a Python virtual environment.

**Windows PowerShell:**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
pip install -r requirements.txt
```

Create a `.env` file from `.env.example` before starting the backend. Set
`GNEWS_API_KEY` if GNews evidence is required, and ensure the configured
Ollama model is installed locally (for example, `ollama pull llama3.2:3b`).
Configuration is read from environment variables; no project-specific
absolute paths are required.

### 3. Run the Backend

From the `backend` directory, run:

```powershell
uvicorn app.main:app --reload
```

The API will be available at:

`http://127.0.0.1:8000`

The analysis endpoint limits concurrent work and outbound article responses.
If evidence retrieval or Ollama verification is unavailable, the response
uses `analysisStatus: "DEGRADED"` and includes safe `degradationReasons`
instead of presenting the result as fully verified. Risk scores remain
heuristics and are not probabilities or proof of truth.

For URL input, the backend validates the destination at connection time,
follows only validated HTTP(S) redirects, streams HTML with a 2 MB response
limit, and then tries Trafilatura, JSON-LD `articleBody`, and a constrained
`<article>`/`<main>` paragraph fallback. The extractor records the method,
word count, metadata warnings, and whether the result is partial for internal
analysis diagnostics. Canonical metadata is validated but is never fetched
automatically.

Health check:

`http://127.0.0.1:8000/api/health`

Interactive API documentation:

`http://127.0.0.1:8000/docs`

### 4. Run the Frontend

Open `frontend/index.html` in your browser or use a local development server.

The backend's CORS configuration currently supports local development origins.

## Evidence retrieval

For each extracted claim, TND sends a bounded, deterministic search query to
the configured GNews and GDELT providers. Important claim words, entities,
numbers, negation, attribution, and causal qualifiers are retained; the
application does not rewrite the original claim based on search results.
Provider failures, missing configuration, empty results, rate limits, and
malformed responses are reported separately in `degradationReasons`.

Results preserve provider provenance, the original claim context, source URL,
valid publication dates, and headline-versus-article-text status. HTTPS and
metadata completeness are transparent indicators only, not editorial
credibility or truth scores. Equivalent URLs are deduplicated conservatively;
when both providers return one article, their provenance is retained and
independence remains `UNKNOWN` rather than counting two confirmations.
Article bodies are fetched only through the protected Phase 2 extractor.

## Current Limitations

* Extraction cannot execute JavaScript, bypass paywalls, or recover content that
  a website does not send in its HTML response.
* Websites may block requests or return unsupported content; these failures are
  reported as API errors rather than being treated as article text.
* Short, metadata-only, navigation-heavy, and boilerplate-only pages are
  rejected or reported as partial where appropriate.
* Ollama and evidence-provider failures produce degraded analysis; they do not
  prove that a claim is true or false.
* Missing `GNEWS_API_KEY` disables only GNews; GDELT can still run. Provider
  authentication, quota, timeout, rate-limit, and malformed-response states
  remain visible as degraded retrieval reasons.
* Search ranking, HTTPS, publisher names, and result counts do not measure
  source reputation or truthfulness. Syndicated copies may not be independent.
* Risk scores are explainable heuristics, not probabilities or verified
  measures of truthfulness.

## Roadmap

* [x] Develop a bounded evidence retrieval pipeline.
* [x] Integrate GNews and GDELT as provenance-preserving evidence sources.
* [x] Distinguish supported, contradicted, and unverified claims.
* [x] Improve error handling and article extraction.
* [ ] Connect the frontend to live backend analysis.
* [x] Add automated tests for API endpoints and article extraction.
* [ ] Improve deployment and configuration.

## Disclaimer

TND is an experimental project. Its current analysis output is illustrative and should not be relied upon to determine whether a news article is true or false.

## Author

**Lloyd D'Souza**

GitHub: [lloydaq](https://github.com/lloydaq)
