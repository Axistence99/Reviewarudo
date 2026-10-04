import asyncio
import copy
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from main import app, calls
from services import gemini, generator
from services.gemini import AIError
from utils.validation import GenerateRequest, Material


@pytest.fixture
def sample():
    return json.loads(
        (Path(__file__).resolve().parents[2] / "frontend/assets/demo.json").read_text()
    )


@pytest.fixture
def mock_provider(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-never-log")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    client = AsyncMock()
    client.__aenter__.return_value = client
    monkeypatch.setattr(gemini.httpx, "AsyncClient", lambda **kwargs: client)
    monkeypatch.setattr(gemini.asyncio, "sleep", AsyncMock())
    return client


def response(text="", finish="STOP", status=200):
    body = {
        "candidates": [{"finishReason": finish, "content": {"parts": [{"text": text}]}}]
    }
    if status != 200:
        body = {"error": {"message": "test-secret-never-log private content"}}
    return httpx.Response(status, json=body)


def run_json():
    return asyncio.run(gemini.generate_json("private source text", Material))


@pytest.mark.parametrize(
    "status,code",
    [(429, "AI_RATE_LIMIT"), (503, "AI_UNAVAILABLE"), (500, "AI_UNAVAILABLE")],
)
def test_exhausted_provider_failure_is_not_validation(
    mock_provider, status, code, caplog
):
    mock_provider.post.return_value = response(status=status)
    with pytest.raises(AIError) as caught:
        run_json()
    assert caught.value.code == code
    assert "could not be validated" not in str(caught.value)
    assert mock_provider.post.await_count == 3
    assert "test-secret-never-log" not in caplog.text
    assert "private source text" not in caplog.text


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "AI_ACCESS_DENIED"),
        (403, "AI_ACCESS_DENIED"),
        (404, "AI_MODEL_NOT_FOUND"),
        (400, "AI_REQUEST_REJECTED"),
    ],
)
def test_non_retryable_errors(mock_provider, status, code):
    mock_provider.post.return_value = response(status=status)
    with pytest.raises(AIError) as caught:
        run_json()
    assert caught.value.code == code
    assert mock_provider.post.await_count == 1


def test_last_cause_survives_a_previous_validation_error(mock_provider):
    mock_provider.post.side_effect = [
        response("{bad"),
        response(status=429),
        response(status=429),
    ]
    with pytest.raises(AIError) as caught:
        run_json()
    assert caught.value.code == "AI_RATE_LIMIT"


def test_transient_failure_recovers(mock_provider, sample):
    mock_provider.post.side_effect = [
        response(status=503),
        response(json.dumps(sample)),
    ]
    assert run_json().title == sample["title"]


def test_transport_is_not_validation(mock_provider):
    mock_provider.post.side_effect = httpx.ReadTimeout("private detail")
    with pytest.raises(AIError) as caught:
        run_json()
    assert caught.value.code == "AI_CONNECTION_ERROR"
    assert "private detail" not in str(caught.value)


def test_truncated_output_is_not_accepted_even_if_json_parses(mock_provider, sample):
    mock_provider.post.return_value = response(json.dumps(sample), finish="MAX_TOKENS")
    with pytest.raises(AIError) as caught:
        run_json()
    assert caught.value.code == "AI_OUTPUT_TRUNCATED"
    assert mock_provider.post.await_count == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"promptFeedback": {"blockReason": "SAFETY"}},
        {"candidates": [{"finishReason": "SAFETY"}]},
    ],
)
def test_blocked_output_is_distinct(mock_provider, payload):
    mock_provider.post.return_value = httpx.Response(200, json=payload)
    with pytest.raises(AIError) as caught:
        run_json()
    assert caught.value.code == "AI_BLOCKED"
    assert mock_provider.post.await_count == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"candidates": []},
        {"candidates": [None]},
        [],
        {
            "candidates": [
                {"content": {"parts": [{"thought": True, "text": "hidden thinking"}]}}
            ]
        },
    ],
)
def test_empty_or_malformed_envelope_is_controlled(mock_provider, payload):
    mock_provider.post.return_value = httpx.Response(200, json=payload)
    with pytest.raises(AIError) as caught:
        run_json()
    assert caught.value.code == "AI_EMPTY_RESPONSE"
    assert mock_provider.post.await_count == 3


def test_invalid_boolean_still_rejected_and_repair_targeted(
    mock_provider, sample, caplog
):
    bad = copy.deepcopy(sample)
    bad["true_false"][0]["answer"] = "private-text-not-a-boolean"
    mock_provider.post.side_effect = [
        response(json.dumps(bad)),
        response(json.dumps(sample)),
    ]
    assert run_json().true_false[0].answer is False
    repair = mock_provider.post.call_args_list[1].kwargs["json"]["contents"][0][
        "parts"
    ][0]["text"]
    assert "true_false.0.answer" in repair
    assert "bool_type" in repair
    assert "private-text-not-a-boolean" not in caplog.text
    assert "private source text" not in caplog.text


def test_quota_error_api_envelope(monkeypatch):
    calls.clear()
    monkeypatch.setattr(
        "main.generate",
        AsyncMock(side_effect=AIError("Gemini quota reached.", "AI_RATE_LIMIT", 429)),
    )
    with TestClient(app) as client:
        result = client.post(
            "/api/generate",
            json={
                "files": [
                    {
                        "filename": "notes.pdf",
                        "source_type": "pdf",
                        "sections": [
                            {"page": 1, "title": "Cells", "content": "Cells."}
                        ],
                    }
                ],
                "material_types": ["reviewer"],
            },
        )
    assert result.status_code == 429
    assert result.json() == {
        "success": False,
        "error": {"code": "AI_RATE_LIMIT", "message": "Gemini quota reached."},
    }


def make_request(sample, kinds, count=20):
    return GenerateRequest.model_validate(
        {
            "files": [
                {
                    "source_type": "pdf",
                    "filename": sample["source_files"][0],
                    "sections": [
                        {
                            "page": i,
                            "title": f"Section {i}",
                            "content": "Cells are the basic units of life.",
                        }
                        for i in [1, 2, 3]
                    ],
                }
            ],
            "material_types": kinds,
            "question_count": count,
        }
    )


def fake_success(sample, schema, offset=0):
    result = {"title": sample["title"], "warnings": []}
    for key in schema.model_fields:
        if key in {"title", "warnings"}:
            continue
        if key in generator.QUESTION_TYPES:
            count = schema.model_json_schema()["properties"][key]["maxItems"]
            result[key] = []
            for i in range(count):
                item = copy.deepcopy(sample[key][0])
                item["statement" if key == "true_false" else "question"] = (
                    f"Test question {offset + i}"
                )
                result[key].append(item)
        else:
            result[key] = sample[key]
    return schema.model_validate(result)


def test_focused_schema_is_strict_and_small():
    schema = generator.output_schema(["flashcards"], 10)
    assert set(schema.model_fields) == {"title", "warnings", "flashcards"}
    assert schema.model_json_schema()["properties"]["flashcards"]["maxItems"] == 10
    with pytest.raises(ValueError):
        schema.model_validate(
            {"title": "Cells", "warnings": [], "flashcards": [], "quiz": []}
        )


def test_default_request_stays_one_call(monkeypatch, sample):
    async def success(prompt, schema):
        return fake_success(sample, schema)

    mock = AsyncMock(side_effect=success)
    monkeypatch.setattr(generator, "generate_json", mock)
    request = make_request(sample, ["reviewer", "flashcards", "quiz"])
    result = asyncio.run(generator.generate(request))
    assert mock.await_count == 1
    assert len(result.flashcards) == len(result.quiz) == 20
    assert result.study_guide is None and result.identification == []
    assert result.source_files == sample["source_files"]


def test_large_question_sets_are_bounded_and_merge(monkeypatch, sample):
    seen_prompts = []

    async def success(prompt, schema):
        seen_prompts.append(prompt)
        return fake_success(sample, schema, len(seen_prompts) * 20)

    monkeypatch.setattr(generator, "generate_json", success)
    result = asyncio.run(generator.generate(make_request(sample, ["quiz"], 50)))
    assert len(seen_prompts) == 3
    assert len(result.quiz) == 50
    assert "Test question 20" in seen_prompts[1]
    assert any("smaller batches" in w for w in result.warnings)


def test_combined_truncation_splits_by_type(monkeypatch, sample):
    seen = []

    async def success(prompt, schema):
        seen.append(set(schema.model_fields))
        if len(seen) == 1:
            raise AIError("Too long", "AI_OUTPUT_TRUNCATED")
        return fake_success(sample, schema)

    monkeypatch.setattr(generator, "generate_json", success)
    result = asyncio.run(
        generator.generate(make_request(sample, ["reviewer", "flashcards", "quiz"]))
    )
    assert len(seen) == 4
    assert result.topics and len(result.quiz) == 20


def test_single_question_batch_truncation_splits_once(monkeypatch, sample):
    calls = []

    async def success(prompt, schema):
        count = schema.model_json_schema()["properties"]["quiz"]["maxItems"]
        calls.append(count)
        if count > 10:
            raise AIError("Too long", "AI_OUTPUT_TRUNCATED")
        return fake_success(sample, schema, len(calls) * 10)

    monkeypatch.setattr(generator, "generate_json", success)
    result = asyncio.run(generator.generate(make_request(sample, ["quiz"], 20)))
    assert calls == [20, 10, 10]
    assert len(result.quiz) == 20


def test_quota_does_not_fan_out(monkeypatch, sample):
    mock = AsyncMock(side_effect=AIError("Quota", "AI_RATE_LIMIT", 429))
    monkeypatch.setattr(generator, "generate_json", mock)
    with pytest.raises(AIError) as caught:
        asyncio.run(
            generator.generate(make_request(sample, ["reviewer", "flashcards", "quiz"]))
        )
    assert caught.value.code == "AI_RATE_LIMIT"
    assert mock.await_count == 1


def test_invalid_output_fallback_is_bounded(monkeypatch, sample):
    mock = AsyncMock(side_effect=AIError("Invalid", "AI_INVALID_OUTPUT"))
    monkeypatch.setattr(generator, "generate_json", mock)
    with pytest.raises(AIError):
        asyncio.run(generator.generate(make_request(sample, ["flashcards"], 20)))
    # 20 fails, then 10 fails; there is no infinite recursion or schema relaxation.
    assert mock.await_count == 2


def test_cross_batch_duplicates_removed_with_shortfall_warning(monkeypatch, sample):
    async def same_question(prompt, schema):
        return schema.model_validate(
            {
                "title": sample["title"],
                "warnings": [],
                "flashcards": sample["flashcards"][:1],
            }
        )

    monkeypatch.setattr(generator, "generate_json", same_question)
    result = asyncio.run(generator.generate(make_request(sample, ["flashcards"], 50)))
    assert len(result.flashcards) == 1
    assert any("1 of 50" in w for w in result.warnings)


def test_invalid_citation_not_silently_repaired(monkeypatch, sample):
    async def invalid_ref(prompt, schema):
        result = fake_success(sample, schema)
        result.flashcards[0].source_reference.file = "invented-file.pdf"
        return result

    monkeypatch.setattr(generator, "generate_json", invalid_ref)
    with pytest.raises(AIError) as caught:
        asyncio.run(generator.generate(make_request(sample, ["flashcards"])))
    assert caught.value.code == "AI_SOURCE_REFERENCE"


def test_empty_selected_resource_not_fabricated(monkeypatch, sample):
    async def empty(prompt, schema):
        return schema.model_validate(
            {
                "title": sample["title"],
                "warnings": ["Insufficient material."],
                "flashcards": [],
            }
        )

    monkeypatch.setattr(generator, "generate_json", empty)
    with pytest.raises(AIError) as caught:
        asyncio.run(generator.generate(make_request(sample, ["flashcards"])))
    assert caught.value.code == "AI_INSUFFICIENT_SOURCE"


def test_short_slide_deck_does_not_inflate_into_multiple_chunks():
    # Layout-mode PDF extraction can include many short/blank lines per slide.
    # Repeating source headers per line used to turn a short deck into multiple AI calls.
    from utils.validation import Document

    doc = Document.model_validate(
        {
            "source_type": "pdf",
            "filename": "lecture-topic.pdf",
            "sections": [
                {
                    "page": i,
                    "title": "Microcontroller-Based Interfaces",
                    "content": (
                        "    A short line of educational source text.\n\n\n" * 12
                    ),
                }
                for i in range(1, 13)
            ],
        }
    )
    parts = generator.chunks([doc])
    assert len(parts) == 1
    assert parts[0].count("SOURCE lecture-topic.pdf") == 12
    for section in doc.sections:
        assert section.content in parts[0]
        assert f"page/slide/section {section.page} |" in parts[0]


def test_oversized_section_splits_without_losing_source_text():
    from utils.validation import Document

    content = "Formula: V = I * R\n\nExplanation with meaningful spacing.\n" * 1000
    doc = Document.model_validate(
        {
            "source_type": "pdf",
            "filename": "physics.pdf",
            "sections": [{"page": 7, "title": "Ohm law", "content": content}],
        }
    )
    prefix = "\nSOURCE physics.pdf | page/slide/section 7 | Ohm law\n"
    parts = generator.chunks([doc])
    assert len(parts) > 1
    assert all(len(part) <= 18000 and part.startswith(prefix) for part in parts)
    assert "".join(part[len(prefix) :] for part in parts) == content


def test_short_pages_stay_whole_when_a_chunk_fills():
    from utils.validation import Document

    sections = [
        {"page": i, "title": f"Page {i}", "content": str(i) * 9000} for i in [1, 2]
    ]
    doc = Document.model_validate(
        {"source_type": "pdf", "filename": "notes.pdf", "sections": sections}
    )
    parts = generator.chunks([doc])
    assert len(parts) == 2
    assert sections[0]["content"] in parts[0]
    assert sections[1]["content"] in parts[1]


def test_chunk_size_cannot_be_smaller_than_the_reference():
    from utils.validation import Document

    doc = Document.model_validate(
        {
            "source_type": "pdf",
            "filename": "notes.pdf",
            "sections": [{"page": 1, "title": "Cells", "content": "Text"}],
        }
    )
    with pytest.raises(ValueError, match="Chunk size"):
        generator.chunks([doc], size=10)


@pytest.mark.parametrize(
    "message,category",
    [
        ("API key not valid. Please pass a valid API key.", "api_key_invalid"),
        ("User location is not supported for the API use.", "region_unsupported"),
        ("The schema has too many states for serving.", "schema_too_complex"),
        ("Response schema is too deeply nested.", "schema_too_complex"),
        (
            'Invalid JSON payload. Unknown name "responseJsonSchema".',
            "request_field_unsupported",
        ),
        ("Unknown field in request", "request_field_unsupported"),
        ("Invalid response_schema: unsupported constraint", "schema_rejected"),
        ("responseMimeType not supported", "schema_rejected"),
        ("This model is not supported for generateContent", "model_unsupported"),
        ("Unexpected private content", "unclassified"),
    ],
)
def test_safe_diagnostic_in_log_and_public_error(
    mock_provider, caplog, message, category
):
    secret = "test-secret-never-log private source text private-document.pdf"
    mock_provider.post.return_value = httpx.Response(
        400,
        json={
            "error": {"message": message + " " + secret, "status": secret},
        },
    )
    with pytest.raises(AIError) as caught:
        run_json()
    assert caught.value.code == "AI_REQUEST_REJECTED"
    assert caught.value.status_code == 502
    assert f"Diagnostic: {category}." in str(caught.value)
    assert f"diagnostic={category}" in caplog.text
    assert mock_provider.post.await_count == 1
    for private in [
        message,
        "test-secret-never-log",
        "private source text",
        "private-document.pdf",
    ]:
        assert private not in caplog.text
        assert private not in str(caught.value)


@pytest.mark.parametrize(
    "reason,category",
    [
        ("API_KEY_INVALID", "api_key_invalid"),
        ("API_KEY_EXPIRED", "api_key_invalid"),
        ("API_KEY_SERVICE_BLOCKED", "api_key_restricted"),
        ("API_KEY_HTTP_REFERRER_BLOCKED", "api_key_restricted"),
        ("API_KEY_IP_ADDRESS_BLOCKED", "api_key_restricted"),
        ("API_KEY_ANDROID_APP_BLOCKED", "api_key_restricted"),
        ("API_KEY_IOS_APP_BLOCKED", "api_key_restricted"),
        ("SERVICE_DISABLED", "service_disabled"),
        ("BILLING_DISABLED", "billing_disabled"),
        ("PRIVATE_SECRET_REASON", "unclassified"),
    ],
)
def test_error_info_reason_allowlist(reason, category):
    result = gemini.provider_diagnostic(
        httpx.Response(
            400,
            json={
                "error": {
                    "message": "private source",
                    "details": [
                        {
                            "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                            "reason": reason,
                            "metadata": {"key": "secret"},
                        }
                    ],
                }
            },
        )
    )
    assert result == category
    assert result in gemini.PROVIDER_DIAGNOSTICS


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        "private",
        17,
        {},
        {"error": []},
        {"error": {"message": ["private"], "details": "private"}},
        {"error": {"details": [None, [], {"reason": {"secret": "private"}}]}},
        {"error": {"details": [{"reason": "API_KEY_INVALID"}]}},
    ],
)
def test_malformed_diagnostics_are_safe(payload):
    assert (
        gemini.provider_diagnostic(httpx.Response(400, json=payload)) == "unclassified"
    )


def test_non_json_provider_body_is_not_exposed(mock_provider, caplog):
    mock_provider.post.return_value = httpx.Response(
        400, text="<html>private secret</html>"
    )
    with pytest.raises(AIError) as caught:
        run_json()
    assert "Diagnostic: unclassified." in str(caught.value)
    assert "private secret" not in str(caught.value) + caplog.text


@pytest.mark.parametrize(
    "status,category", [(429, "quota_exceeded"), (503, "service_unavailable")]
)
def test_diagnostic_does_not_change_retries(mock_provider, caplog, status, category):
    mock_provider.post.return_value = response(status=status)
    with pytest.raises(AIError):
        run_json()
    assert mock_provider.post.await_count == 3
    assert f"diagnostic={category}" in caplog.text


@pytest.mark.parametrize(
    "message,category",
    [
        (
            "Your API key was reported as leaked. Please use another API key.",
            "api_key_revoked",
        ),
        ("API key revoked", "api_key_revoked"),
        ("Invalid API key", "api_key_invalid"),
        ("API key not found", "api_key_invalid"),
        ("Credential rejected", "credential_rejected"),
        ("This API key has restrictions", "credential_rejected"),
        ("temperature is not allowed", "generation_setting_rejected"),
        ("Developer instruction is not enabled", "generation_setting_rejected"),
        ("Request payload size exceeds the limit", "payload_too_large"),
    ],
)
def test_additional_safe_diagnostics(message, category):
    assert (
        gemini.provider_diagnostic(
            httpx.Response(
                400,
                json={
                    "error": {"message": message + " PRIVATE_VALUE"},
                },
            )
        )
        == category
    )
    assert category in gemini.PROVIDER_DIAGNOSTICS


@pytest.mark.parametrize(
    "payload,shape,status",
    [
        ([], "json_non_object", "unknown"),
        ({}, "json_without_error_object", "unknown"),
        (
            {"error": {"status": "INVALID_ARGUMENT"}},
            "json_error_object",
            "INVALID_ARGUMENT",
        ),
        ({"error": {"status": "PRIVATE_VALUE"}}, "json_error_object", "unknown"),
        ({"error": {"status": ["PRIVATE_VALUE"]}}, "json_error_object", "unknown"),
    ],
)
def test_provider_metadata_allowlist(payload, shape, status):
    assert gemini.provider_error_metadata(httpx.Response(400, json=payload)) == (
        shape,
        status,
    )


def test_provider_metadata_non_json():
    assert gemini.provider_error_metadata(
        httpx.Response(400, text="PRIVATE_VALUE")
    ) == ("non_json", "unknown")


def test_precondition_diagnostic():
    assert (
        gemini.provider_diagnostic(
            httpx.Response(
                400,
                json={
                    "error": {
                        "status": "FAILED_PRECONDITION",
                        "message": "PRIVATE_VALUE",
                    },
                },
            )
        )
        == "precondition_failed"
    )


def test_provider_schema_removes_only_array_bounds():
    schema = generator.output_schema(["reviewer", "flashcards", "quiz"], 20)
    original = schema.model_json_schema()
    wire = gemini.provider_schema(schema)

    def check(before, after):
        if isinstance(before, dict):
            expected = set(before) - (
                {"minItems", "maxItems"} if before.get("type") == "array" else set()
            )
            assert set(after) == expected
            for key in expected:
                check(before[key], after[key])
        elif isinstance(before, list):
            assert len(before) == len(after)
            for a, b in zip(before, after):
                check(a, b)
        else:
            assert before == after

    check(original, wire)
    assert original == schema.model_json_schema()
    assert original["properties"]["quiz"]["maxItems"] == 20
    assert original["$defs"]["Quiz"]["properties"]["choices"]["minItems"] == 4
    assert "maxItems" not in wire["properties"]["quiz"]
    assert "minItems" not in wire["$defs"]["Quiz"]["properties"]["choices"]
    assert wire["additionalProperties"] is False


def test_array_bound_names_in_properties_are_not_removed():
    class FakeModel:
        @staticmethod
        def model_json_schema():
            return {
                "type": "object",
                "properties": {
                    "minItems": {"type": "integer"},
                    "maxItems": {"type": "integer"},
                },
            }

    assert gemini.provider_schema(FakeModel) == FakeModel.model_json_schema()


def test_wire_schema_used_and_local_counts_remain_strict(mock_provider, sample):
    schema = generator.output_schema(["quiz"], 10)
    valid = fake_success(sample, schema).model_dump()
    invalid = copy.deepcopy(valid)
    invalid["quiz"] = [copy.deepcopy(valid["quiz"][0]) for _ in range(11)]
    with pytest.raises(ValueError):
        schema.model_validate(invalid)
    mock_provider.post.side_effect = [
        response(json.dumps(invalid)),
        response(json.dumps(valid)),
    ]
    result = asyncio.run(gemini.generate_json("synthetic source", schema))
    assert len(result.quiz) <= 10
    assert mock_provider.post.await_count == 2
    request = mock_provider.post.call_args_list[0].kwargs["json"]
    assert request["generationConfig"]["responseJsonSchema"] == gemini.provider_schema(
        schema
    )
    assert (
        "exactly four distinct choices"
        in request["systemInstruction"]["parts"][0]["text"]
    )
    assert (
        "too_long"
        in mock_provider.post.call_args_list[1].kwargs["json"]["contents"][0]["parts"][
            0
        ]["text"]
    )


@pytest.mark.parametrize("choice_count", [3, 5])
def test_quiz_choice_bounds_still_enforced_locally(mock_provider, sample, choice_count):
    schema = generator.output_schema(["quiz"], 10)
    valid = fake_success(sample, schema).model_dump()
    invalid = copy.deepcopy(valid)
    invalid["quiz"][0]["choices"] = [f"Choice {i}" for i in range(choice_count)]
    invalid["quiz"][0]["correct_answer"] = "Choice 0"
    with pytest.raises(ValueError):
        schema.model_validate(invalid)
    mock_provider.post.side_effect = [
        response(json.dumps(invalid)),
        response(json.dumps(valid)),
    ]
    result = asyncio.run(gemini.generate_json("synthetic source", schema))
    assert len(result.quiz[0].choices) == 4
    assert mock_provider.post.await_count == 2


def test_private_probe_route_removed():
    calls.clear()
    with TestClient(app) as client:
        assert client.post("/api/internal/provider-comparison").status_code == 404
        assert "provider-comparison" not in client.get("/openapi.json").text
    calls.clear()
