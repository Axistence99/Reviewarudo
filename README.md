# Reviewarudo

**Your notes. A smarter way to study.**

Reviewarudo turns academic PDFs, Word documents, and PowerPoint presentations into source-referenced reviewers, flashcards, quizzes, glossaries, summaries, and study guides using Google Gemini. No account, database, Node.js, npm, bundler, or frontend build is required.

## Quick start

- Run the static frontend and click **Try a demo**. No backend or API key is required for the demo.
- For real generation: deploy the backend, configure its Gemini key and model, then set the single `API_BASE_URL` in `frontend/js/api.js`.
- Deployment files are included. **This project does not include credentials or a pre-provisioned Render service.** Live Gemini generation must be verified with your model and account before launch.

## Features

- Multi-file drag-and-drop upload, browse, removal, validation, actual upload progress, extraction preview, and combination of documents.
- PDF page text, DOCX headings/lists/tables, and PPTX titles/text/bullets/tables/speaker notes.
- Nine output types: comprehensive reviewer, flashcards, multiple choice, identification, true/false, fill-in-the-blank, glossary, summary, study guide.
- Academic level, question difficulty, question count (10/20/30/50/100), language (English/Filipino/custom), and learning style settings.
- Topic cards, collapsible sections, read progress, and visible source references.
- Flippable flashcards, previous/next, Fisher–Yates shuffle, known/review-again tracking, Space and arrow-key shortcuts.
- Interactive quizzes with one submission per question, immediate feedback, explanations, progress, score, and restart.
- Separate practice modes for identification, true/false, and fill-in-the-blank.
- Browser print / Save as PDF with source files and answer key; JSON and text downloads; individual flashcard/topic PNG exports.
- Space-inspired creation workspace with a lavender orbit illustration, responsive creation deck, and live study-set sidebar.
- Library for the current generated set and in-session reading, flashcard, and quiz progress.
- Responsive layouts, light/dark themes, visible focus, semantic controls, accessible labels, reduced-motion support. The orbit design defaults to dark; an explicit theme choice is remembered.
- Demo content with its illustrative source notes under `frontend/assets/`.
- Temporary generated-resource storage in `sessionStorage`; theme preference in `localStorage`.
- Backend-only Gemini credentials, typed input/output validation, bounded JSON recovery, safe escaped UI output, CORS allowlist, request limits, and a basic in-memory rate limit.

## Architecture

```text
Static frontend / GitHub Pages
        │ REST + JSON (multipart for extraction)
        ▼
FastAPI / Render
        ├── File validation → pypdf / python-docx / python-pptx
        ├── Section-aware chunking → intermediate notes (large sources)
        └── Gemini API → JSON parsing → Pydantic validation → source-reference checks
        │
        ▼
Browser learning interface → study / practice / export
```

There is no server-side database, login, durable job queue, or document storage. Upload parsers may spool larger files to the operating system’s temporary storage; upload handles are closed after extraction. Extracted text is returned to the browser and sent back with the generation request. Generated resources are stored only in that tab’s `sessionStorage`, and can be removed with **Clear study session**. Browser session restore may restore session storage; clear the session explicitly on shared devices.

Extracted content is sent to Google for generation. Google's API data-handling and retention terms apply. Do not upload private student records, credentials, or sensitive documents. No claim is made that third-party processing has zero retention.

## Project structure

```text
frontend/
  index.html
  css/styles.css
  js/app.js                 # State, upload, study interactions
  js/api.js                 # Single backend URL and request transport
  js/ui.js                  # Escaped rendering and print layout
  js/utils.js               # Downloads, text, PNG rendering
  assets/demo.json
  assets/sample-notes.txt
backend/
  main.py                   # API, limits, CORS, errors
  requirements.txt
  .env.example
  services/extraction.py
  services/gemini.py
  services/generator.py
  utils/validation.py
  tests/test_app.py
tests/browser_smoke.py
.github/workflows/pages.yml
.github/workflows/test.yml
render.yaml
README.md
```

## Local development

Python **3.11 or later** is required.

### Backend

```bash
cd backend
python -m venv .venv
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Windows (Command Prompt):

```bat
.venv\Scripts\activate
```

Install and configure:

```bash
pip install -r requirements.txt
cp .env.example .env
```

On Windows, use `copy .env.example .env`. Edit `.env` locally, then run:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Backend: `http://localhost:8000`; API docs: `/docs`; ReDoc: `/redoc`.

### Frontend

In another terminal, from the repository root:

```bash
python -m http.server 8080 --directory frontend
```

Open `http://localhost:8080`. For local generation, temporarily set this value in `frontend/js/api.js`:

```javascript
export const API_BASE_URL = 'http://localhost:8000';
```

Do not open `index.html` using `file://`: ES modules and demo fetching require HTTP. The localhost URL is only for development on your own computer. For remotely hosted previews, use a reachable HTTPS backend with the preview origin added to CORS; browser localhost is not the remote server.

### Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | For generation | Backend-only Google API credential |
| `GEMINI_MODEL` | For generation | Currently available model ID that supports JSON-schema structured output and `generateContent`; use the ID without `models/` |
| `CORS_ORIGINS` | For deployed frontend | Comma-separated allowed origins, no paths/trailing slashes |
| `MAX_FILE_MB` | No | File limit, default 10; keep the frontend limit synchronized if changing it |
| `RATE_LIMIT_PER_HOUR` | No | POST requests per client IP per process, default 12; extraction and generation each count |
| `PORT` | Render supplies | Web service listening port |

Example backend environment:

```dotenv
GEMINI_API_KEY=your-secret-key
GEMINI_MODEL=your-current-supported-model-id
CORS_ORIGINS=https://axistence99.github.io,http://localhost:8080
MAX_FILE_MB=10
RATE_LIMIT_PER_HOUR=12
```

Select an available structured-output model in your Google account; this project intentionally does not assume a model name remains supported forever. No key goes into frontend files, GitHub Pages, Git commits, or screenshots. `.env` is ignored by Git.

## Deploy to Render

### Blueprint option

1. Push the project to GitHub.
2. In Render, create a new **Blueprint** and connect the repository.
3. Render reads `render.yaml` and creates a free Python web service.
4. Supply `GEMINI_API_KEY` and `GEMINI_MODEL` in Render, not in source control.
5. Confirm `CORS_ORIGINS=https://axistence99.github.io` (or your actual frontend origin).
6. Deploy and open `https://<your-service>.onrender.com/health`.

Expected response once configured:

```json
{"success":true,"data":{"status":"ok","ai_configured":true}}
```

`ai_configured` means values exist, not that credentials, quota, and model access have been verified.

### Manual service option

- Runtime: Python
- Root directory: `backend`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`
- Add the same environment variables listed above.

The free service can sleep or restart. Cold starts and long requests may fail or time out; retry with smaller documents or fewer outputs. There is no paid hosting or AI quota included. Keep a single worker on the free service: concurrency and rate limits are per process. Heavy public use requires more robust infrastructure.

## Deploy to GitHub Pages

1. Set `API_BASE_URL` in `frontend/js/api.js` to your real HTTPS Render URL.
2. Push to the repository’s `main` branch.
3. Open **Repository → Settings → Pages → Build and deployment → Source → GitHub Actions**.
4. Run the included **Deploy static frontend** workflow if it has not already run. It uploads only `frontend/`, not backend code or credentials.
5. The expected project-site path for this repository is `https://axistence99.github.io/Reviewarudo/`.
6. Open the deployed site and run the demo.
7. Check backend `/health`, upload a small text-based document, preview the extracted content, generate one resource, and check a citation.
8. Test every selected resource, mobile layout, dark mode, print/PDF, and downloads.

All frontend paths are relative and compatible with a GitHub Pages repository subpath. CORS uses only the origin `https://axistence99.github.io`, **not** `/Reviewarudo/`. If your default branch has another name, update the Pages workflow’s branch filter. Protected environments may require deployment approval.

Alternatively, publish the contents of `frontend/` at the root of a dedicated Pages branch/repository. GitHub's branch-based Pages setup does not directly publish an arbitrary `/frontend` subdirectory; use the included workflow for this monorepo.

Tailwind and Lucide load through CDN as requested. Custom CSS provides the layout independently of Tailwind; text controls still function if the icon CDN is unavailable. Google Fonts is optional and falls back to local sans-serif. CDN availability is needed for those external assets, and CDN scripts are a third-party trust dependency.

## API contract

`GET /` — service information. `GET /health` — liveness/configuration flag.

`POST /api/extract` accepts `multipart/form-data`, with 1–8 repeated fields named `files`.

```bash
curl -F "files=@biology.pdf" http://localhost:8000/api/extract
```

Successful extraction:

```json
{
  "success": true,
  "data": {
    "files": [{
      "source_type": "pdf",
      "filename": "biology.pdf",
      "sections": [{"page": 1, "title": "Cells", "content": "Cells are the basic units of life."}]
    }],
    "characters": 34,
    "approximate_tokens": 9
  }
}
```

`POST /api/generate` accepts extracted documents (not binary uploads):

```json
{
  "files": [{
    "source_type": "pdf",
    "filename": "biology.pdf",
    "sections": [{"page": 1, "title": "Cells", "content": "Cells are the basic units of life."}]
  }],
  "material_types": ["reviewer", "flashcards", "quiz"],
  "difficulty": "college",
  "question_difficulty": "mixed",
  "question_count": 20,
  "language": "English",
  "learning_style": "Exam Preparation"
}
```

This tiny example demonstrates the request shape, not a source sufficient for 20 distinct questions. Insufficient source coverage produces fewer items and a warning rather than intentional padding.

Generation returns `{"success":true,"data":{...}}`. The complete response model is in `backend/utils/validation.py`: `title`, `source_files`, `summary`, `topics`, `flashcards`, `quiz`, `identification`, `true_false`, `fill_in_the_blank`, `key_terms`, `study_guide`, and `warnings`. Unselected resource arrays are instructed to be empty; optional summary/guide objects use null.

All application API errors use:

```json
{"success":false,"error":{"code":"INVALID_FILE","message":"The uploaded file is not supported."}}
```

Typical status codes: 400 invalid/corrupt document, 413 limits exceeded, 422 bad request schema, 429 rate limit, 502 AI error, 503 busy, 504 generation timeout. Infrastructure failures outside the app may produce other response shapes; the frontend handles these as connection failures. Swagger/ReDoc intentionally return HTML and OpenAPI returns its standard schema.

## Generation, recovery, and fidelity

1. Validate extensions, MIME where provided, signatures/container structure, compressed document expansion, size, and counts.
2. Extract page/slide/heading sections. Preview is available before generation; direct Generate also extracts automatically.
3. Estimate tokens as characters / 4 (a heuristic, especially approximate for non-English languages).
4. Accumulate section-labelled paragraphs into chunks of about 18,000 characters. Oversized paragraphs split at whitespace where possible; section references repeat across split pieces.
5. For multiple chunks, generate compact source-referenced notes and hierarchically reduce if necessary before final synthesis. Chunk processing is sequential to avoid request bursts.
6. Request structured JSON with a Pydantic-derived JSON schema. The system prompt prioritizes source fidelity and treats embedded document instructions as untrusted data.
7. Parse directly, strip accidental code fences, or recover the first decodable JSON object. Never use `eval` or execute model code.
8. Validate typed schema, four distinct quiz choices and correct-answer membership. Invalid output triggers bounded full regeneration from the original prompt. Transient upstream failures use bounded backoff. There are at most three attempts per model call.
9. Verify every source reference points to an actual supplied file and section. Invalid citations or empty selected resources return controlled errors.

**Important limitations:** Valid JSON and valid reference coordinates do not prove factual correctness or that a sentence is entailed by the cited source. There is no independent semantic fact-checker. Always verify important information. Large-document synthesis can omit detail; the UI warns when it is used. Questions are prompted to cover distinct facts, but semantic duplication is not mechanically guaranteed.

- PDF extraction preserves layout text and page numbers; headings are heuristic. No OCR, image understanding, or reliable reconstruction of complex PDF reading order/math is provided.
- Word files do not contain stable rendered page numbers. Their references are explicitly displayed as **Section**, based on extracted headings.
- DOCX list markers are normalized; exact multilevel numbering is not reconstructed. Tables become pipe-separated text.
- Slides include text, tables, and available notes, not text embedded in images or charts.
- Text-answer grading is case-normalized exact matching with trailing punctuation normalization, not semantic grading. Equivalent phrasing can be marked incorrect; the UI discloses this.
- PDF export is native browser **Print → Save as PDF**, not an automatic binary-PDF download.
- PNG export is intended for individual, reasonably sized cards/topics; unusually long content can exceed browser canvas limits.
- Source file names should be unique; rename same-named documents before combining them.

## Limits and public-service security

Defaults: 10 MB/file, 8 files, 30 MB aggregate uploads, 32 MB actual HTTP body, 400,000 extracted characters combined, 500 PDF pages or slides/file, 60 MB expanded Office archive, 5,000 ZIP entries. Two extraction requests and two generation requests can run concurrently; additional requests receive a busy response. Generation is bounded to 15 minutes server-side, and infrastructure may impose shorter limits.

This is a practical initial no-login/no-database deployment, **not a fully abuse-resistant public AI gateway**. CORS is not authentication. An unauthenticated endpoint can consume your AI quota. The in-memory rate limiter resets on restart and is neither distributed nor persistent; verify trusted-proxy/client-IP behavior on your deployment. Never broadly trust arbitrary forwarded headers. Before broad public launch:

- Set Google API quotas and budget alerts; limit key usage to the required API.
- Consider a privacy-conscious challenge and edge rate limiting; enforce any challenge on the backend.
- Monitor service health and upstream errors without logging documents or secrets.
- Load-test on the actual Render instance and verify memory/CPU behavior with representative files.
- Consider isolated extraction workers and stronger resource limits for adversarial file uploads.
- Review dependency/security updates and your privacy notice.
- A paid service or durable queue may be necessary for heavy or long-running workloads.

## Testing

Backend tests:

```bash
cd backend
python -m pytest -q
```

They cover real PDF/DOCX/PPTX extraction fixtures, speaker notes, tables, blank/corrupt files, upload size, source validation, chunking, strict booleans, malformed-JSON recovery, bounded AI repair (mocked), CORS, rate limits, routes, and controlled errors.

Optional browser tests (Python tooling only; not required for deployment):

```bash
pip install playwright
python -m playwright install --with-deps chromium
# Keep the frontend HTTP server on port 8080 running in a separate terminal.
python tests/browser_smoke.py
```

Browser smoke checks cover demo navigation, read tracking, flashcard interactions, quiz feedback, fill-in grading, glossary/guide, downloads, session restoration, theme, and mobile overflow. Tests save screenshots to ignored `tests/*.png` files.

**Verification performed during implementation:** 24 backend tests passed; Chromium browser smoke checks passed. Live Google API calls, hosted Render behavior, and GitHub Pages deployment have not been verified without account configuration. A real end-to-end smoke test remains a release gate.

## Resources needed from the owner

1. A repository-scoped writable GitHub connection/deploy key. A deploy key authenticates access to this repo, not the personal account identity.
2. Preferred commit name and a GitHub-verified/noreply author email for attribution.
3. A Render account connected to the repository.
4. A Google Gemini API key, currently supported structured-output model, and sufficient quota. Configure secrets directly in Render, never in chat or frontend code.
5. The resulting Render HTTPS service URL.
6. GitHub Pages set to GitHub Actions, and approval to merge/deploy the initial branch.

No database, storage bucket, custom domain, or paid frontend tooling is required for this initial version.
