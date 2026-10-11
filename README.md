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

### 3. Run the Backend

From the `backend` directory, run:

```powershell
uvicorn app.main:app --reload
```

The API will be available at:

`http://127.0.0.1:8000`

Health check:

`http://127.0.0.1:8000/api/health`

Interactive API documentation:

`http://127.0.0.1:8000/docs`

### 4. Run the Frontend

Open `frontend/index.html` in your browser or use a local development server.

The backend's CORS configuration currently supports local development origins.

## Current Limitations

* The analysis engine currently returns mock risk scores, signals, claims, and evidence.
* Article extraction depends on the accessibility and structure of the source website.
* Actual claim verification against independent evidence is still under development.
* Risk scores should not be interpreted as verified measures of truthfulness.

## Roadmap

* [ ] Develop an evidence-based claim analysis pipeline.
* [ ] Integrate reliable external evidence sources.
* [ ] Distinguish supported, contradicted, and unverified claims.
* [ ] Improve error handling and article extraction.
* [ ] Connect the frontend to live backend analysis.
* [ ] Add automated tests for API endpoints and article extraction.
* [ ] Improve deployment and configuration.

## Disclaimer

TND is an experimental project. Its current analysis output is illustrative and should not be relied upon to determine whether a news article is true or false.

## Author

**Lloyd D'Souza**

GitHub: [lloydaq](https://github.com/lloydaq)
