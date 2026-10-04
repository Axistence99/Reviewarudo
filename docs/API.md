# REST API contract

Source of truth: `backend/main.py` and `backend/utils/validation.py`. The API has no login and no server-side session ID. Requests are stateless except for transient rate/concurrency guards. The browser sends extracted documents back with each generation request.

## Envelopes

Successful application response:

```json
{"success": true, "data": {}}
```

Controlled error:

```json
{"success": false, "error": {"code": "INVALID_FILE", "message": "Human-readable explanation."}}
```

Use HTTP status and `success`, not text matching. Infrastructure/proxy errors may be non-JSON; `frontend/js/api.js` handles those as connection failures. `/docs`, `/redoc`, and `/openapi.json` are exceptions to the application envelope.

## GET `/`

```json
{"success":true,"data":{"name":"Reviewarudo","docs":"/docs"}}
```

## GET `/health`

```json
{"success":true,"data":{"status":"ok","ai_configured":true,"revision":null}}
```

The process is running. `ai_configured` reflects the presence of both Gemini environment variables only. `revision` is `RENDER_GIT_COMMIT` if available, otherwise null. No API key or model response is exposed.

## POST `/api/extract`

Content type: `multipart/form-data`. Repeat the field name **`files`** for 1–8 files.

```bash
curl -F "files=@lecture.pdf" -F "files=@notes.docx" http://localhost:8000/api/extract
```

Supported extensions/MIME types:

| Extension | MIME |
|---|---|
| `.pdf` | `application/pdf` |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| `.pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` |

An empty MIME or `application/octet-stream` is allowed, with extension/signature/container checks still applied. Filenames are reduced to a basename and sanitized; source filenames must be unique when submitted for generation.

Example result:

```json
{
  "success": true,
  "data": {
    "files": [{
      "source_type": "pdf",
      "filename": "lecture.pdf",
      "sections": [{"page": 1, "title": "Cells", "content": "Cells are the basic units of life."}]
    }],
    "characters": 34,
    "approximate_tokens": 9
  }
}
```

`characters` is the sum of section-content lengths. `approximate_tokens` is ceiling(characters/4), a heuristic that varies in accuracy by language. It excludes prompt/schema/source-label overhead. Unreadable/blank pages are filtered; surviving PDF/PPTX page numbers remain the original numbers. Word sections are indexed by extracted heading boundaries, not rendered pages. No OCR occurs.

## POST `/api/generate`

Content type: `application/json`. The `files` property is the **extracted document array**, not file paths, browser File objects, or multipart binaries.

```json
{
  "files": [{
    "source_type": "pdf",
    "filename": "lecture.pdf",
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

That tiny source demonstrates request shape, not enough content for 20 distinct questions.

### Settings and validation

| Field | Allowed values / constraints | Default |
|---|---|---|
| `files` | 1–8 documents; source type `pdf`, `docx`, `pptx`; filename 1–200 characters; 1–2,000 sections/document | Required |
| `sections[].page` | Integer ≥1, unique within a document | Required |
| `sections[].title` | String up to 500 characters | Required |
| `sections[].content` | String up to 500,000 characters per section, but **400,000 total** across the request; each document must have readable content | Required |
| `material_types` | 1–9 entries from `reviewer`, `flashcards`, `quiz`, `identification`, `true_false`, `fill_in_the_blank`, `key_terms`, `summary`, `study_guide` | Required |
| `difficulty` | `beginner`, `intermediate`, `advanced`, `college` | `college` |
| `question_difficulty` | `easy`, `mixed`, `challenging` | `mixed` |
| `question_count` | Integer 10, 20, 30, 50, or 100; target **per selected question/card activity** | 20 |
| `language` | Nonempty string, up to 60 characters | `English` |
| `learning_style` | `Quick Review`, `Detailed Study`, `Exam Preparation`, `Memorization`, `Concept Understanding` | `Exam Preparation` |

Models forbid extra fields and use strict types: e.g. `"20"` is not an integer and `"true"` is not a boolean. Duplicate resource selections are de-duplicated in synthesis. Duplicate source filenames/references are rejected.

### Generated material

Every successful result contains these keys; unselected arrays are empty, unselected summary/guide are null:

| Key | Content |
|---|---|
| `title` | Generated set title |
| `source_files` | Actual submitted filenames, set by the backend |
| `summary` | `overview`, `section_summaries`, `key_takeaways`, `final_review`, reference; or null |
| `topics` | Reviewer topics: `title`, `summary`, `key_points`, `key_terms`, `examples`, `relationships`, reference |
| `flashcards` | `question`, `answer`, reference |
| `quiz` | `question`, four distinct `choices`, `correct_answer` exactly matching a choice, `explanation`, reference |
| `identification` | `question`, `answer`, reference |
| `true_false` | `statement`, boolean `answer`, `explanation`, reference |
| `fill_in_the_blank` | `question`, `answer`, reference; underscore blank is requested in the prompt, not mechanically checked |
| `key_terms` | `term`, `definition`, reference |
| `study_guide` | `main_topics`, `learning_objectives`, `important_concepts`, `key_terminology`, `common_misconceptions`, `examples`, `review_questions`, `final_summary`, reference; or null |
| `warnings` | Shortfalls, duplicate removal, staged summaries/batching and model notes |

A reference has this exact shape:

```json
{"source_reference":{"file":"lecture.pdf","page":1}}
```

The UI labels it Page, Slide, or Section based on extension. Coordinates are checked against supplied files. This does not verify semantic entailment. Successful output may contain fewer questions than requested; unsupported facts must not be invented to fill the target. Quiz difficulty, broad coverage, and semantic uniqueness are prompt-guided, not provable schema constraints.

## Error reference

| Code | HTTP | Meaning / next action |
|---|---|---|
| `INVALID_FILE` | 400 | Unsupported, unreadable, empty, protected, corrupt, or unsafe-sized internal document structure |
| `FILE_TOO_LARGE`, `TEXT_TOO_LARGE` | 413 | Split files/content to meet limits |
| `REQUEST_ERROR` | Varies | HTTP-layer error, including actual-body-size and missing routes |
| `INVALID_REQUEST` | 422 | Strict request schema/content validation failed |
| `RATE_LIMIT` | 429 | App's per-IP hourly POST allowance exhausted |
| `BUSY` | 503 | Extraction/generation concurrency or guard capacity reached |
| `AI_ERROR` | 502 | Generic AI error, including missing Gemini configuration |
| `AI_RATE_LIMIT` | 429 | Gemini quota/rate limit; wait or check Google project quota/billing |
| `AI_ACCESS_DENIED` | 502 | Upstream 401/403; check backend credential and project permissions |
| `AI_MODEL_NOT_FOUND` | 502 | Upstream 404; check configured model ID/access |
| `AI_REQUEST_REJECTED` | 502 | Upstream 400; message includes a fixed diagnostic category (see below) |
| `AI_UNAVAILABLE` | 503 | Upstream service failure after bounded attempts |
| `AI_CONNECTION_ERROR` | 504 | HTTP transport failure or upstream request timeout |
| `AI_BLOCKED` | 502 | Prompt/candidate blocked by the provider; not malformed JSON |
| `AI_EMPTY_RESPONSE` | 502 | No readable response envelope/text after recovery attempts |
| `AI_OUTPUT_TRUNCATED` | 502 | Token limit reached; smaller-task fallback could not complete |
| `AI_INVALID_OUTPUT` | 502 | JSON/schema recovery and applicable fallback exhausted |
| `AI_SOURCE_REFERENCE` | 502 | A generated reference points outside the supplied coordinates |
| `AI_INSUFFICIENT_SOURCE` | 502 | A selected resource is still empty after synthesis |
| `TIMEOUT` | 504 | Overall generation exceeded 900 seconds |
| `SERVER_ERROR` | 500 | Unexpected application error; no traceback is returned to the browser |

The wrapper maps errors without returning raw provider messages. Retry/backoff is at most three HTTP attempts per model call; task splitting can create more model calls. Quota/access/outage errors do not split into additional tasks. Upstream 429/5xx must never be described as JSON validation failures.

### Safe provider diagnostics

Upstream HTTP 400 errors retain the `AI_REQUEST_REJECTED` code and HTTP 502
status. Their message includes `Diagnostic: <category>.`, an allowlisted canonical
Google status (or `unknown`), and a fixed response-body shape label. The Gemini
wrapper also logs these labels with HTTP `status` and `attempt`.

Categories are application-owned labels: `api_key_invalid`, `api_key_restricted`,
`service_disabled`, `billing_disabled`, `schema_too_complex`, `schema_rejected`,
`request_field_unsupported`, `model_unsupported`, `region_unsupported`,
`quota_exceeded`, `service_unavailable`, `api_key_revoked`, `credential_rejected`,
`generation_setting_rejected`, `payload_too_large`, `precondition_failed`, or
`unclassified`. Body shapes are `non_json`, `json_non_object`,
`json_without_error_object`, or `json_error_object`. Unknown provider status
strings are never copied into logs or public responses.

The classifier checks allowlisted Google ErrorInfo reasons and known message
patterns internally, but never returns or logs the raw provider body, its message,
arbitrary reason strings, metadata, credentials, or source text. Message-based
categories are diagnostic hints, not proof of the underlying cause. Unknown or
malformed responses remain `unclassified`. Retry behavior is unchanged; this
instrumentation does not itself fix rejected requests or provider outages.
