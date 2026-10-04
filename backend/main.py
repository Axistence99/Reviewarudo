import asyncio
import os
import time
import logging
from collections import defaultdict, deque
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.concurrency import run_in_threadpool
from services.extraction import extract
from services.generator import generate
from services.gemini import AIError
from services.provider_probe import router as provider_probe_router
from utils.validation import GenerateRequest

load_dotenv()
app = FastAPI(
    title="Reviewarudo API",
    version="1.0.0",
    description="Temporary document extraction and source-grounded learning materials. Files are not persisted.",
)
app.include_router(provider_probe_router)

origins = [
    s.strip()
    for s in os.getenv("CORS_ORIGINS", "http://localhost:8080").split(",")
    if s.strip()
]


def error(code, message, status=400):
    return JSONResponse(
        {"success": False, "error": {"code": code, "message": message}},
        status_code=status,
    )


# Bound actual streamed request size, not just the client-supplied Content-Length.
class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        size = 0

        async def limited():
            nonlocal size
            message = await receive()
            size += len(message.get("body", b""))
            if size > 32 * 1024 * 1024:
                raise HTTPException(413, "Request exceeds the 32 MB limit.")
            return message

        await self.app(scope, limited, send)


app.add_middleware(BodyLimit)


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    return error(
        "INVALID_REQUEST",
        "Invalid request. Check settings, document structure, and the 400,000-character text limit.",
        422,
    )


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return error("REQUEST_ERROR", str(exc.detail), exc.status_code)


@app.exception_handler(Exception)
async def unexpected(request, exc):
    logging.exception("Request failed")
    return error(
        "SERVER_ERROR",
        "The server could not process this request. Please try again.",
        500,
    )


calls = defaultdict(deque)
active = asyncio.Semaphore(2)
extract_active = asyncio.Semaphore(2)


@app.middleware("http")
async def guard(request: Request, call_next):
    if request.method == "POST":
        # Render's trusted proxy is configured through Uvicorn's proxy support.
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        for key in list(calls):
            while calls[key] and calls[key][0] < now - 3600:
                calls[key].popleft()
            if not calls[key]:
                del calls[key]
        bucket = calls[ip]
        if len(bucket) >= int(os.getenv("RATE_LIMIT_PER_HOUR", "12")):
            return error(
                "RATE_LIMIT", "Request limit reached. Please try again in an hour.", 429
            )
        if len(calls) > 10000:
            return error("BUSY", "The server is busy. Please try again later.", 503)
        bucket.append(now)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", summary="Service information")
async def root():
    return {"success": True, "data": {"name": "Reviewarudo", "docs": "/docs"}}


@app.get("/health", summary="Liveness and configuration status")
async def health():
    return {
        "success": True,
        "data": {
            "status": "ok",
            "ai_configured": bool(
                os.getenv("GEMINI_API_KEY") and os.getenv("GEMINI_MODEL")
            ),
            "revision": os.getenv("RENDER_GIT_COMMIT"),
        },
    }


@app.post("/api/extract", summary="Extract PDF, DOCX, and PPTX in memory")
async def extract_files(files: list[UploadFile] = File(...)):
    try:
        if not 1 <= len(files) <= 8:
            return error("INVALID_FILE", "Upload between 1 and 8 documents.")
        if extract_active.locked():
            return error(
                "BUSY",
                "The server is processing other documents. Please try again shortly.",
                503,
            )
        documents, total = [], 0
        async with extract_active:
            for file in files:
                data = await file.read(
                    int(os.getenv("MAX_FILE_MB", "10")) * 1024 * 1024 + 1
                )
                total += len(data)
                if (
                    len(data) > int(os.getenv("MAX_FILE_MB", "10")) * 1024 * 1024
                    or total > 30 * 1024 * 1024
                ):
                    return error(
                        "FILE_TOO_LARGE", "Maximum 10 MB per file and 30 MB total.", 413
                    )
                try:
                    document = await run_in_threadpool(
                        extract,
                        data,
                        file.filename or "document",
                        file.content_type or "",
                    )
                except ValueError as exc:
                    return error("INVALID_FILE", str(exc))
                except Exception:
                    return error(
                        "INVALID_FILE",
                        "This document could not be read. It may be corrupted or password-protected.",
                    )
                documents.append(document)
        characters = sum(len(s["content"]) for d in documents for s in d["sections"])
        if characters > 400000:
            return error(
                "TEXT_TOO_LARGE",
                "Combined text exceeds 400,000 characters. Please split the documents.",
                413,
            )
        return {
            "success": True,
            "data": {
                "files": documents,
                "characters": characters,
                "approximate_tokens": (characters + 3) // 4,
            },
        }
    finally:
        for file in files:
            await file.close()


@app.post(
    "/api/generate", summary="Generate and validate source-grounded study resources"
)
async def generate_material(body: GenerateRequest):
    if active.locked():
        return error(
            "BUSY",
            "The server is creating other study materials. Please try again shortly.",
            503,
        )
    try:
        async with active:
            result = await asyncio.wait_for(generate(body), timeout=900)
        return {"success": True, "data": result.model_dump()}
    except AIError as exc:
        return error(exc.code, str(exc), exc.status_code)
    except asyncio.TimeoutError:
        return error(
            "TIMEOUT", "Generation took too long. Try fewer documents or outputs.", 504
        )


# CORS wraps request guards so controlled rate/size errors remain readable by the frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
)
