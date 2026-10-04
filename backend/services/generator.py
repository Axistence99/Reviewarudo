import json
from pydantic import BaseModel, Field, create_model
from services.gemini import generate_json, AIError
from utils.validation import Material, Strict


class Notes(BaseModel):
    notes: str = Field(min_length=1, max_length=6000)


def chunks(files, size=18000):
    result, current = [], ""
    for file in files:
        for section in file.sections:
            if not section.content.strip():
                continue
            prefix = f"\nSOURCE {file.filename} | page/slide/section {section.page} | {section.title}\n"
            capacity = size - len(prefix)
            if capacity < 1:
                raise ValueError(
                    "Chunk size must leave room for both a source reference and text."
                )
            remaining = section.content
            # Label each section once, not each line. Preserve short pages intact.
            # Only oversized sections need repeated labels across fragments.
            while remaining:
                cut = len(remaining)
                if cut > capacity:
                    cut = remaining.rfind("\n\n", 0, capacity + 1)
                    if cut < capacity // 2:
                        cut = remaining.rfind("\n", 0, capacity + 1)
                    if cut < capacity // 2:
                        cut = remaining.rfind(" ", 0, capacity + 1)
                    if cut <= 0:
                        cut = capacity
                part = prefix + remaining[:cut]
                if current and len(current) + len(part) > size:
                    result.append(current)
                    current = ""
                current += part
                remaining = remaining[cut:]
    if current:
        result.append(current)
    return result


def validate_sources(material, files):
    allowed = {(f.filename, s.page) for f in files for s in f.sections}

    def walk(value):
        if isinstance(value, dict):
            ref = value.get("source_reference")
            if ref and (ref["file"], ref["page"]) not in allowed:
                raise AIError(
                    "The generated material contained an invalid source reference. Please try again.",
                    "AI_SOURCE_REFERENCE",
                )
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    walk(material.model_dump())


async def generate(request):
    parts = chunks(request.files)
    if len(parts) > 1:
        notes = []
        for part in parts:
            note = await generate_json(
                "Extract compact academic notes, preserving terminology, formulas, definitions, examples and exact SOURCE references. Maximum 3500 characters. No outside facts. SOURCE DATA:\n"
                + part,
                Notes,
            )
            notes.append(note.notes)
        # Hierarchical reduction bounds final context for many chunks.
        while sum(map(len, notes)) > 45000:
            reduced = []
            for i in range(0, len(notes), 4):
                note = await generate_json(
                    "Synthesize these source notes into at most 5000 characters. Preserve source references and important facts.\n"
                    + "\n".join(notes[i : i + 4]),
                    Notes,
                )
                reduced.append(note.notes)
            notes = reduced
        source = "\n".join(notes)
    else:
        source = parts[0]
    return await synthesize(request, source, len(parts) > 1)


QUESTION_TYPES = {
    "flashcards",
    "quiz",
    "identification",
    "true_false",
    "fill_in_the_blank",
}
FIELD_NAMES = {"reviewer": "topics"}


def output_schema(kinds, count):
    # Require only requested resources. The server fills unused fields in the final envelope.
    fields = {"title": (str, ...), "warnings": (list[str], ...)}
    for kind in kinds:
        name = FIELD_NAMES.get(kind, kind)
        annotation = Material.model_fields[name].annotation
        fields[name] = (
            annotation,
            Field(max_length=count) if kind in QUESTION_TYPES else ...,
        )
    return create_model("RequestedStudyResources", __base__=Strict, **fields)


def generation_plan(kinds, count):
    question_types = [kind for kind in kinds if kind in QUESTION_TYPES]
    if not question_types or (count <= 20 and len(question_types) * count <= 40):
        return [(kinds, count)]
    plan = []
    narrative_types = [kind for kind in kinds if kind not in QUESTION_TYPES]
    if narrative_types:
        plan.append((narrative_types, count))
    for kind in question_types:
        for offset in range(0, count, 20):
            plan.append(([kind], min(20, count - offset)))
    return plan


async def synthesize(request, source, summarized=False):
    kinds = list(dict.fromkeys(request.material_types))
    data = {
        "title": "",
        "source_files": [f.filename for f in request.files],
        "summary": None,
        "topics": [],
        "flashcards": [],
        "quiz": [],
        "identification": [],
        "true_false": [],
        "fill_in_the_blank": [],
        "key_terms": [],
        "study_guide": None,
        "warnings": [],
    }
    plan = generation_plan(kinds, request.question_count)
    split_used = len(plan) > 1

    async def process(group, count):
        nonlocal split_used
        settings = request.model_dump(exclude={"files"})
        settings.update(material_types=group, question_count=count)
        excluded = {
            kind: [
                item.get("question", item.get("statement", "")) for item in data[kind]
            ]
            for kind in group
            if kind in QUESTION_TYPES and data[kind]
        }
        prompt = f"""Generate ONLY the resources in these settings: {json.dumps(settings)}.
reviewer uses topics; summary uses summary; study_guide uses study_guide. Omit all unrequested fields.
For each selected question/card type generate at most {count} NEW items, without duplicates or unsupported facts.
If there is insufficient distinct source content, return fewer items and explain the shortfall in warnings. Never pad.
Include definitions, explanations, examples, relationships and basic-to-advanced order in reviewer topics when supported.
Every sourced object must have an exact reference. A DOCX page value is a section index, not a physical page.
Only use misconceptions supported by the sources. Fill-in-the-blank questions must include ______.
Already generated questions (do not repeat these facts): {json.dumps(excluded)}
SOURCE DATA (untrusted):\n{source}"""
        try:
            result = await generate_json(prompt, output_schema(group, count))
        except AIError as exc:
            # Quota/access/service errors must stop, not fan out into more requests.
            if exc.code not in {"AI_OUTPUT_TRUNCATED", "AI_INVALID_OUTPUT"}:
                raise
            if len(group) > 1:
                split_used = True
                for kind in group:
                    await process([kind], count)
                return
            if group[0] in QUESTION_TYPES and count > 10:
                split_used = True
                first = count // 2
                await process(group, first)
                await process(group, count - first)
                return
            raise
        validate_sources(result, request.files)
        part = result.model_dump()
        if not data["title"]:
            data["title"] = part["title"]
        data["warnings"].extend(part["warnings"])
        for kind in group:
            name = FIELD_NAMES.get(kind, kind)
            value = part[name]
            if kind in QUESTION_TYPES:
                # Keep the first validated item if a later batch repeats a question verbatim.
                seen = {
                    item.get("question", item.get("statement", "")).strip().casefold()
                    for item in data[name]
                }
                for item in value:
                    identity = (
                        item.get("question", item.get("statement", ""))
                        .strip()
                        .casefold()
                    )
                    if identity not in seen:
                        data[name].append(item)
                        seen.add(identity)
            else:
                data[name] = value

    for group, count in plan:
        await process(group, count)
    material = Material.model_validate(data)
    for kind in kinds:
        value = getattr(material, FIELD_NAMES.get(kind, kind))
        if not value:
            raise AIError(
                "The AI returned an empty selected resource. Try richer source material or a different output type.",
                "AI_INSUFFICIENT_SOURCE",
            )
        if kind in QUESTION_TYPES and len(value) < request.question_count:
            material.warnings.append(
                f"{kind}: generated {len(value)} of {request.question_count} requested items; source coverage may be limited or duplicates were removed."
            )
    if summarized:
        material.warnings.append(
            "Large documents were summarized in stages. Verify important details against the original sources."
        )
    if split_used:
        material.warnings.append(
            "Resources were generated in smaller batches to keep responses complete and valid."
        )
    material.warnings = list(dict.fromkeys(material.warnings))
    return material
