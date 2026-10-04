"""Temporary, expiring, capability-protected synthetic provider comparison."""

import asyncio
import hashlib
import hmac
import os
import re
import time
import httpx
from fastapi import APIRouter, Request, HTTPException
from services.generator import output_schema

router = APIRouter()
TOKEN_HASH = "9821773fe3125e776d5aab7f3cee0712f9eebf3a115d5a37f58fa49bb642170f"
EXPIRES = 1791107292
lock = asyncio.Lock()
results = {}


def redact(message, key):
    if not isinstance(message, str):
        return "No textual provider error"
    message = message.replace(key, "[redacted]") if key else message
    message = re.sub(r"https?://\S+|[\w.+-]+@[\w.-]+", "[redacted]", message)
    message = re.sub(r"[A-Za-z0-9_=-]{28,}|\b\d{6,}\b", "[redacted]", message)
    return message[:1500]


@router.post("/api/internal/provider-comparison", include_in_schema=False)
async def compare(request: Request, mode: str = "minimal"):
    token = request.headers.get("x-diagnostic-token", "")
    if time.time() > EXPIRES or not hmac.compare_digest(
        hashlib.sha256(token.encode()).hexdigest(), TOKEN_HASH
    ):
        raise HTTPException(404)
    if mode not in {"minimal", "small_schema", "app_schema", "new_format"}:
        raise HTTPException(400)
    async with lock:
        if mode in results:
            return results[mode]
        # Consume the slot before network I/O; failures cannot cause unbounded retries.
        results[mode] = {"mode": mode, "state": "attempted"}
        key, model = os.getenv("GEMINI_API_KEY", ""), os.getenv("GEMINI_MODEL", "")
        if not key or not model:
            results[mode] = {"mode": mode, "state": "unconfigured"}
            return results[mode]
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": "This is a synthetic test. Water freezes at zero degrees Celsius. "
                            "Return a JSON object matching the requested schema. Use synthetic.txt page 1 "
                            "as the source reference, one example per list, and an empty warnings list. "
                            'If there is no schema, return {"ok":true}.'
                        }
                    ],
                }
            ]
        }
        if mode != "minimal":
            schema = (
                {
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"],
                }
                if mode == "small_schema"
                else output_schema(
                    ["reviewer", "flashcards", "quiz"], 20
                ).model_json_schema()
            )
            body["generationConfig"] = {"temperature": 0.2}
            if mode == "new_format":
                body["generationConfig"]["responseFormat"] = {
                    "text": {"mimeType": "application/json", "schema": schema}
                }
            else:
                body["generationConfig"].update(
                    {
                        "responseMimeType": "application/json",
                        "responseJsonSchema": schema,
                    }
                )
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": key},
                    json=body,
                )
            result = {"mode": mode, "http_status": response.status_code}
            if response.status_code >= 400:
                try:
                    payload = response.json()
                    error = (
                        payload.get("error", {}) if isinstance(payload, dict) else {}
                    )
                    message = error.get("message") if isinstance(error, dict) else None
                except ValueError:
                    message = "Non-JSON provider error"
                # Only synthetic requests; never include metadata, headers, or response dumps.
                result["synthetic_error"] = redact(message, key)
            else:
                result["state"] = "accepted"
            results[mode] = result
        except httpx.HTTPError:
            results[mode] = {"mode": mode, "state": "transport_failure"}
        return results[mode]
