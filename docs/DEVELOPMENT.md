# Development and maintenance guide

## Responsibility boundaries

The project is intentionally small. Keep the existing static frontend / REST backend split. There is no frontend framework, package manager, build system, database, authentication service, or application plugin system to extend.

### Frontend

- `index.html` defines stable element IDs consumed by the controller. Keep IDs and delegated `data-*` attributes synchronized with JavaScript.
- `app.js` owns state and UI transitions. `showView()` toggles sections, updates navigation/download visibility, resets scroll, and focuses the main region. `renderCurrentView()` delegates view rendering; `handleStudyAction()` handles dynamic study buttons.
- `setProcessingState()` owns the busy flag, `inert` application shell, overlay, timer, and upload progress. All async extraction/generation paths release it in `finally`; changing that behavior can leave the interface unusable.
- `extractSelectedFiles()` posts binaries, stores the returned sections, and builds a preview. Direct Generate extracts first if necessary; explicit preview is available but not mandatory.
- `saveStudySession()` writes only generated data. Selected file objects and extraction text are not stored in local/session storage. Avoid introducing storage for originals without an explicit privacy design.
- `ui.js` contains render helpers, escaped reading views, source labels, notice scrolling and print markup. Generated content is plain text: do not replace escaping with raw model HTML or Markdown injection.
- `utils.js` owns escaping and browser-native downloads. Object URLs are revoked after a delay to allow browsers to start the download. PNG uses Canvas text, not HTML screenshots.
- `api.js` uses XMLHttpRequest for real upload progress, a 16-minute transport timeout, and standardized errors. It cannot see intermediate Gemini work; do not present invented completion percentages.
- `styles.css` contains shared/base component styles and older component selectors; `orbit.css` intentionally overrides the current theme and responsive layout. **Load order matters.** Do not consolidate/reorder rules casually: later breakpoints and specificity are part of current behavior.

Dark is the default unless the user saved light. Session data survives a same-tab reload; activity progress does not. Library shows only the current set. `New reviewer` navigates to creation—it is not a destructive reset. The footer Clear session action asks for confirmation.

### Backend

- `main.py`: startup configuration, standardized responses, request-body limiter, per-IP timestamps, two extraction slots, two generation slots, route orchestration. Run it from `backend/` because imports are rooted there.
- `validation.py`: strict request and complete response shapes. Keep the final `Material` shape compatible with the browser even when the model receives a smaller schema.
- `extraction.py`: reject unsupported inputs; inspect PDF signatures or Office ZIP contents; normalize filenames; return sections. `run_in_threadpool` prevents synchronous parsing from blocking the async loop but does not provide process isolation or hard per-file CPU timeouts.
- `generator.py`: combines sources, chunks, optionally summarizes, constructs a synthesis plan, merges valid batches, removes exact duplicate question text, fills unused fields, and verifies source coordinates.
- `gemini.py`: provider-specific REST body, system instruction, JSON parsing/recovery, typed validation, safe diagnostics, retries, and classified `AIError`. It does not store files or access browser state.

## Non-obvious generation rules

1. **Label sections, not lines.** Each whole section gets one source header. Preserve short pages; split only oversized sections, preferring paragraph/newline/space boundaries. The chunk budget includes source headers. Blank sections are skipped.
2. **Avoid needless summaries.** One chunk goes directly to synthesis. Multiple chunks get sequential intermediate notes (schema capped at 6,000 characters); notes over 45,000 characters are reduced in groups of four before final synthesis. The approximation is character-based, not a tokenizer.
3. **Keep model schemas focused.** `output_schema()` includes only selected resources plus title/warnings. `synthesize()` builds the complete browser-facing envelope itself, including trusted source filenames and empty/null unselected fields.
4. **Bound output work.** Requests with no question types, or at most 20 questions/activity and 40 total question items, start as one task. Larger requests group narrative outputs and split question types into batches of at most 20. Thus the default reviewer + 20 flashcards + 20 MCQs remains one synthesis task when successful.
5. **Recover without hiding the cause.** Each model call gets at most three attempts. Schema repair includes field/constraint feedback. `MAX_TOKENS` is not accepted as complete output. Truncation/schema failures can split a combined task by type, then split a question batch down to 10. Those fallbacks terminate; quota, access, blocked-content and service failures do not fan out.
6. **Never invent a completion.** Invalid citations are rejected, not replaced. Empty selected resources fail. Fewer valid questions produce warnings. Exact case-folded/trimmed question text is deduplicated; no semantic duplicate detector is claimed.
7. **Atomic result.** The browser receives the complete validated set or an error, not a partial streamed result. An already-generated browser set is not replaced until a new request succeeds. Batching can increase cost/latency; the outer 900-second deadline still applies.

## Security and accessibility review points

- Never commit `.env`, private keys, uploaded originals, extracted private text, generated private content, or API credentials. Do not turn diagnostic logs into document storage.
- The Gemini wrapper logs HTTP status, attempt, and fixed diagnostic categories, not provider text, source content, or credentials. HTTP 400 public messages also include the safe category (see `API.md`). Keep unknown ErrorInfo reasons and malformed bodies unclassified; never interpolate provider values into logs or responses. Generic unexpected-error logging still requires operational review before handling sensitive data.
- Preserve extension/MIME/signature/ZIP expansion/body/character checks and strict Pydantic validation. Uploaded documents and model outputs are untrusted.
- Escape every interpolated filename, question, answer, term, and title. Do not use `eval`, raw model HTML, or AI-generated executable code.
- CORS is a browser-origin policy, not API authorization. Rate limiting is basic/per-process; trusted proxy settings must be verified in the actual hosting environment. Do not broadly trust arbitrary forwarded headers.
- Confirm decorative icons are hidden from assistive technology; icon-only actions need accessible names. Maintain associated input labels, visible focus on interactive controls, keyboard card navigation, and reduced-motion CSS.
- Keep alert feedback below the sticky navbar, including after closing the processing overlay. A successful view change must reset long-page scroll; regression tests cover both.
- Test a small phone width as well as desktop. Keep the logo and wordmark separate with their intended gap. A horizontally scrollable tool navigation is intentional; page-wide overflow is not.
- Do not claim a full security audit, WCAG certification, or all-browser compatibility from these tests.

## Verification workflow

1. Inspect `git status`, the files being changed, call sites, and existing tests before editing. Preserve unrelated working changes.
2. Make focused edits; preserve UI/architecture and avoid new dependencies unless justified. Source files are intentionally unminified for readability.
3. Run `python -m compileall -q backend tests` from root and `python -m pytest -q` from `backend/`.
4. Serve `frontend/` at port 8080 and run all six `tests/*.py` browser scripts listed in README. Imports execute in Chromium, so parse/import/runtime failures surface without Node.js.
5. `responsive_layout.py` checks 320, 360, 375, 390, 430, 640, 768, 980, 1024, 1180, 1280, 1440, and 1920 pixels in both themes. It checks overflow, brand gap, control bounds/touch height, and navigation—not every screenshot or possible content length.
6. `accessibility_security.py` checks selected keyboard/name/label paths, escaped hostile text, no unexpected dialog execution, browser error events, and a headless print PDF. The other export test intercepts `window.print()` to verify the trigger and answer-key content. Neither automates the operating system's Save as PDF dialog.
7. Mocked provider tests cover success/failure/control flow, not live credentials, quota, semantic fidelity or model availability. Use an approved non-sensitive sample for a separate live test; live requests may incur cost.
8. Review `git diff --check`, filenames, secrets and generated artifacts before staging. No private uploaded PDFs belong in the repository. `tests/*.png` and `tests/*.pdf` are ignored test artifacts.
9. Commit/push/deploy only with explicit authorization. For release, check GitHub tests and Pages, then verify Render's `/health` revision separately. If Render Auto-Deploy is disabled or fails, use its dashboard rather than claiming a push deployed it.

## Changes that need coordinated edits

| Change | Review together |
|---|---|
| New output type | Pydantic models, generator field/batch mappings, frontend selection/library/render/export, tests, API docs |
| File support/limits | HTML accept list, app validation, API parsing/limits, extraction, fixtures and README |
| Backend hostname | `frontend/js/api.js`, Render CORS for the frontend origin, deployment docs |
| Output schema | Dynamic selected schema and complete `Material`, demo JSON, frontend/print rendering and tests |
| Theme/layout | Both stylesheets, boot-time theme script and controller, keyboard/mobile/print behavior |
| Error handling | `AIError`, HTTP status/envelope, frontend notices, provider mocks and error reference |

## Formatting conventions

Use two-space indentation in JS/CSS/HTML and four in Python; preserve UTF-8. `.editorconfig` captures this without adding a build dependency. Formatting tools used during maintenance are not required at runtime. Avoid formatting the model system prompt or generated content in ways that change meaning. Reformatting CSS must not change selector order, declaration values, breakpoints, or specificity.

Keep API/module entry points stable. Prefer explicit action/function names to terse abbreviations, but do not introduce a component framework, global event bus, generic repository layer, or a second validation framework solely to rename a few handlers.
