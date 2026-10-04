# Reviewarudo

**Turn any material into your learning orbit.**

Reviewarudo is a no-login study workspace that extracts text from academic **PDF, DOCX, and PPTX** files and asks Google Gemini to create source-referenced learning materials. The interface runs as static files on GitHub Pages; a Python API on Render handles extraction and generation.

- Frontend: <https://axistence99.github.io/Reviewarudo/>
- Configured API: <https://reviewarudo.onrender.com>
- Interactive API reference: <https://reviewarudo.onrender.com/docs>

These are deployment addresses, not an uptime or model-access guarantee. Check `/health` and a real generation request after deploying.

## Features

- Multiple-file drag/drop or browse, removal, size/type checks, upload progress, and extracted-text preview.
- Nine formats: reviewer, flashcards, multiple choice, identification, true/false, fill-in-the-blank, key terms, summary, and study guide.
- Academic level, question difficulty, 10/20/30/50/100 questions per activity, language, and learning-style settings. Extra settings are under **Customize your study session**.
- Collapsible reviewer topics and read tracking; flashcard flip/shuffle/known/review-again; interactive quizzes with feedback, explanations, score, and restart.
- Current-session **Library** and **Progress** views. These are not a saved cloud library or a historical analytics service.
- **Current material** or **All materials** downloads as TXT/JSON; browser print/Save as PDF; individual flashcard and reviewer-topic PNG exports.
- Responsive orbit-themed layout, light/dark toggle, keyboard controls, focus indicators, source references, and reduced-motion handling. Dark is the first-visit default; an explicit preference is remembered.
- **Explore a sample study set** works without a backend or API key. It loads `frontend/assets/demo.json`, not an AI response.

## Technology and architecture

| Layer | Implementation |
|---|---|
| Interface | HTML5, ES modules / vanilla JavaScript, custom CSS, Tailwind CDN, Lucide CDN |
| Typography | Optional Google Fonts with local fallbacks |
| API | Python 3.11+, FastAPI, Uvicorn, Pydantic v2, python-dotenv, python-multipart |
| Extraction | pypdf, python-docx, python-pptx |
| Gemini transport | HTTPX, Gemini REST `generateContent` with structured JSON output |
| Backend tests | pytest and FastAPI TestClient; Gemini responses mocked |
| Browser tests | Python Playwright + Chromium, installed separately for development |
| Hosting | GitHub Pages + Render Python web service |

```text
Browser / GitHub Pages
  ├─ POST /api/extract (multipart files)
  │      → FastAPI → document parsers → sections with source references
  └─ POST /api/generate (extracted text + settings)
         → section-aware chunks → summaries only when needed
         → selected-output schema / bounded batches → Gemini
         → JSON + schema + source-coordinate checks
         → complete material envelope → study / practice / export
```

**There is no database, account system, durable job queue, or frontend build.** No Node.js, npm, bundler, React, or TypeScript is required to run or deploy the application. GitHub's supplied actions have their own internal runtime; the application itself does not use Node.js.

### State and privacy

| Data | Lifetime / location |
|---|---|
| Selected file objects and extracted text | JavaScript memory until removed/replaced or the page closes/reloads |
| Upload parsing | Request lifetime; multipart uploads may spill into OS temporary files; handles are closed |
| Generated material | Tab-scoped `sessionStorage`, key `reviewarudo-material` |
| Read topics, card knowledge, current quiz answers | JavaScript memory; resets on reload or a new study set |
| Theme | `localStorage`, key `reviewarudo-theme` |
| Rate-limit timestamps | Backend process memory; reset on restart |

Use **Clear session** in the footer to remove the app's generated set and selected materials. It does not delete downloaded exports or the theme preference. Browser session restore may restore `sessionStorage`; explicitly clear shared devices.

Generation sends extracted text to Google. Google's API data-handling and retention terms apply; the app does not guarantee zero third-party retention. Do not upload private student records, credentials, or sensitive documents.

## Project map

```text
frontend/
  index.html                    Static shell, forms, navigation, theme bootstrapping
  css/styles.css                Base components and responsive/print styles
  css/orbit.css                 Orbit theme and layout overrides (loaded second)
  js/app.js                     Session state, view routing, uploads, study events
  js/api.js                     Single backend URL and XMLHttpRequest transport
  js/ui.js                      Escaped view templates, notices, print rendering
  js/utils.js                   HTML escaping, file downloads, text and PNG exports
  assets/                       Favicon/brand images, demo JSON, sample source notes
backend/
  main.py                       App, endpoints, CORS, request/rate/concurrency guards
  requirements.txt              Python application and backend-test dependencies
  .env.example                  Non-secret configuration template
  services/extraction.py        Signature/container checks and text extraction
  services/gemini.py            System prompt, HTTP calls, repair and error mapping
  services/generator.py         Chunking, synthesis planning, batch merge, citations
  utils/validation.py           Strict request and output models
  tests/test_app.py              Extraction, API, validation, CORS, and health tests
  tests/test_generation_recovery.py  Provider errors, batching, and chunk regressions
tests/
  browser_smoke.py               Core study interactions, demo, theme, downloads
  generation_workflow.py         Mock upload/generation; scroll/error regressions
  material_downloads.py          Scoped exports, download contents, print trigger
  orbit_workspace.py            Library, progress, selection summary, settings
  responsive_layout.py          13 viewport widths in both themes
  accessibility_security.py     Keyboard/labels, escaped hostile content, print PDF
.github/workflows/
  pages.yml                     Static deployment on matching main-branch pushes
  test.yml                      Backend tests on pushes and pull requests
render.yaml                     Optional Render Blueprint
.editorconfig                   Basic editor whitespace conventions
docs/API.md                     REST request/response contracts and errors
docs/DEVELOPMENT.md              Implementation guide, testing and review checklist
```

## Local setup

### 1. Backend

From the repository root:

```bash
cd backend
python -m venv .venv
```

Activate the environment:

```bash
# macOS / Linux
source .venv/bin/activate
```

```bat
:: Windows Command Prompt
.venv\Scripts\activate
```

```powershell
# Windows PowerShell (subject to your execution policy)
.venv\Scripts\Activate.ps1
```

Install packages and create local configuration:

```bash
pip install -r requirements.txt
cp .env.example .env
```

On Windows Command Prompt use `copy .env.example .env`. Edit `.env` locally; never commit it. Then, **from `backend/`**:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Health: `http://localhost:8000/health`; Swagger: `/docs`; ReDoc: `/redoc`. Extraction and health checks work without a Gemini key; generation does not.

### 2. Frontend

In a second terminal, **from the repository root**:

```bash
python -m http.server 8080 --directory frontend
```

Open `http://localhost:8080`. Do not use `file://`; module imports and demo fetching require HTTP.

The committed frontend uses the public Render API. For local backend development, temporarily change `frontend/js/api.js`:

```javascript
export const API_BASE_URL = 'http://localhost:8000';
```

Keep `http://localhost:8080` in backend `CORS_ORIGINS`, and restore the public HTTPS API URL before pushing a production deployment. In remotely hosted previews, browser localhost is not the remote server—use a browser-reachable HTTPS API with the preview origin allowed.

### Build

**There is no frontend build command.** Serve or publish the existing `frontend/` directory. The backend installation step is `pip install -r requirements.txt`; Uvicorn loads Python code directly.

### Configuration

| Name | Default / location | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | No default; backend only | Google API credential; required for generation |
| `GEMINI_MODEL` | No default; backend only | Available model ID supporting `generateContent` and JSON-schema output, without `models/` |
| `CORS_ORIGINS` | Code fallback: `http://localhost:8080` | Comma-separated origins, no paths/trailing slashes; example file also includes GitHub Pages |
| `MAX_FILE_MB` | `10` | Server per-file upload limit; frontend independently enforces 10 MB, so coordinate changes |
| `RATE_LIMIT_PER_HOUR` | `12` | POST requests per client IP per backend process; extraction and generation each count |
| `PORT` | Supplied by Render | Used by the production Uvicorn start command |
| `PYTHON_VERSION` | `3.11.11` in `render.yaml` | Render runtime setting, not read by application code |
| `RENDER_GIT_COMMIT` | Supplied by Render; absent locally | Public deployed revision exposed in `/health`; no secret |
| `API_BASE_URL` | `frontend/js/api.js` | Public backend base URL; currently `https://reviewarudo.onrender.com` |

Model access, pricing, quotas, and availability depend on your Google project. The app does not select a default Gemini model. Choose a currently supported structured-output model from [Google's model documentation](https://ai.google.dev/gemini-api/docs/models). Never put the API key in frontend code, GitHub Pages, or chat.

## Testing

From `backend/` with dependencies installed:

```bash
python -m pytest -q
```

From the repository root, syntax/import compilation:

```bash
python -m compileall -q backend tests
```

For browser tests, install developer tooling separately (not needed by Render or Pages):

```bash
pip install playwright
python -m playwright install --with-deps chromium
```

Keep the frontend server on port 8080 running in a separate terminal. From the repository root:

```bash
python tests/browser_smoke.py
python tests/generation_workflow.py
python tests/material_downloads.py
python tests/orbit_workspace.py
python tests/responsive_layout.py
python tests/accessibility_security.py
```

Browser tests do not call live Gemini: they use the included demo and mock generation routes. The last script also reads a browser-produced print PDF using pypdf, already in backend requirements. Screenshot/PDF artifacts in `tests/` are ignored by Git. Playwright browser binaries/system libraries may need reinstalling in a new environment.

GitHub's `test.yml` currently runs **backend pytest on Python 3.11 only**; browser tests are developer-run, not an existing CI guarantee. Local test results, production smoke results, and code review are different checks; do not infer live Gemini readiness from mocked tests or `ai_configured`.

See [development notes](docs/DEVELOPMENT.md) for coverage boundaries and a release checklist.

## API and database

| Route | Purpose |
|---|---|
| `GET /` | Service name and documentation path |
| `GET /health` | Process liveness, presence of AI settings, deployed revision |
| `POST /api/extract` | Repeated multipart `files` → extracted documents and size estimates |
| `POST /api/generate` | Extracted documents + settings → validated learning materials |
| `GET /docs`, `/redoc`, `/openapi.json` | FastAPI-generated API documentation |

Application endpoints use `success/data` or `success/error` envelopes. Documentation endpoints keep their native HTML/OpenAPI formats. See [API contracts and error codes](docs/API.md).

**Database structure:** none. There are no tables, migrations, persistence models, or database environment variables to configure.

## Deployment

### GitHub Pages

1. Set the public API URL in `frontend/js/api.js`.
2. Enable **Repository → Settings → Pages → Source: GitHub Actions** once.
3. Push approved changes to `main`. The Pages workflow triggers when `frontend/**` or its workflow file changes; backend/docs-only pushes do not redeploy Pages.
4. Alternatively, choose **Run workflow → main** in the Deploy static frontend workflow.
5. Wait for a successful deployment, then verify the public site, demo, upload, generation, and exports.

The workflow uploads only `frontend/`. All frontend resource paths are relative to support `/Reviewarudo/`. No Jekyll, npm install, or build task is required. Branch-based Pages settings do not directly publish arbitrary `/frontend` folders; use the workflow for this monorepo.

CORS must allow **`https://axistence99.github.io`**, not the repository path. An SSH deploy key can push approved commits but does not grant GitHub settings/API administration or personal-account authentication.

### Render

For the existing service, verify that **Auto-Deploy** is enabled for `main`; otherwise use **Manual Deploy → Deploy latest commit**. A Git push does not prove the backend deployed.

Manual service configuration:

| Setting | Value |
|---|---|
| Service type | Web Service |
| Runtime | Python |
| Branch | `main` |
| Root directory | `backend` |
| Build | `pip install -r requirements.txt` |
| Start | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Health check | `/health` |
| Secrets | `GEMINI_API_KEY`, `GEMINI_MODEL` |
| CORS | `https://axistence99.github.io` |

No disk, database, or frontend service on Render is necessary. Set secrets directly in Render. For a **new** deployment, the optional `render.yaml` Blueprint creates a service named `reviewarudo-api`; the current manually named service URL is `reviewarudo.onrender.com`. A Blueprint is not automatically applied to an already-created service.

Verify the revision on the deployed API:

```json
{"success":true,"data":{"status":"ok","ai_configured":true,"revision":"<deployed commit SHA>"}}
```

Locally `revision` is null unless the environment variable is set. `ai_configured: true` only checks that the two variables exist—it is not a credential, quota, model-access, or semantic-quality test. After deployment, use a small non-sensitive source for a real generation test.

### Operations and limitations

- Render Free can sleep/restart. Cold starts can delay the first request; infrastructure may time out before the app's 15-minute deadline. Browser transport allows 16 minutes. There is no durable queue or reconnect/resume.
- Two extraction requests and two generation requests can run concurrently per process. Additional requests get `BUSY`; extraction runs in worker threads, not isolated processes.
- Basic limits: 10 MB/file, 8 files, 30 MB total upload, 32 MB actual request body, 400,000 extracted characters total, 500 PDF pages/PPTX slides, 60 MB expanded Office ZIP, 5,000 ZIP entries. These are safeguards, not protection against every parser/resource attack.
- Per-IP rate limiting resets on process restart, is not distributed, and depends on trusted proxy/client-IP configuration. Keep a single worker for the intended free-service setup. CORS is **not authentication**; a public no-login endpoint can consume Gemini quota. Use Google-side quota controls/budget alerts, monitoring, and stronger edge protection before broad public use.
- Larger sources are summarized in stages; large output sets are batched. Both can increase requests, latency, cost, and quota use. Exact duplicate question text is removed; semantically similar questions can remain.
- Schema/source-coordinate validation does not prove factual accuracy. Verify important facts against the originals. Embedded prompt instructions are treated as untrusted, but the prompt is not a complete prompt-injection defense.
- No OCR or image/chart interpretation. PDF headings/layout are heuristic; formulas, multi-column slides, tables, and footers can be imperfectly extracted. DOCX references are **sections**, not physical pages; original list numbering is normalized.
- Text-answer grading uses normalized exact matching, not semantic scoring. Equivalent wording may be marked incorrect. Revealed answers count as incorrect.
- A new set replaces the current generated set. Progress is not restored after reload. Choosing a practice mode restarts that mode's current score; there is no stored cross-mode history.
- PDF is native **Print → Save as PDF**, not an automatic PDF download. JSON retains the full envelope; TXT uses readable recursive labels. PNG is intended for reasonably sized individual cards/topics; long words or very long content can exceed canvas limits. PNG uses a fixed light export style independent of the screen theme.
- Tailwind/Lucide CDN and Google Fonts are third-party network/trust dependencies. Custom CSS and text labels provide fallbacks, but an offline session is not a fully cached offline app.
- Python dependency ranges are bounded but not locked; test upgrades. Accessibility checks cover selected controls and keyboard paths, not a complete WCAG certification or manual screen-reader audit. Chromium checks do not guarantee every Safari/Firefox/mobile browser behavior.
