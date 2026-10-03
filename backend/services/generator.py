import json
from pydantic import BaseModel, Field
from services.gemini import generate_json, AIError
from utils.validation import Material

class Notes(BaseModel):
    notes: str = Field(min_length=1, max_length=6000)


def chunks(files, size=18000):
    result, current = [], ''
    for file in files:
        for section in file.sections:
            prefix = f'\nSOURCE {file.filename} | page/slide/section {section.page} | {section.title}\n'
            # Prefer paragraphs; oversized paragraphs fall back to whitespace boundaries.
            for paragraph in section.content.split('\n'):
                while len(paragraph) > size - len(prefix):
                    cut = paragraph.rfind(' ', 0, size-len(prefix))
                    if cut < 1:
                        cut = size-len(prefix)
                    if current:
                        result.append(current)
                        current = ''
                    result.append(prefix + paragraph[:cut])
                    paragraph = paragraph[cut:].lstrip()
                part = prefix + paragraph
                if len(current) + len(part) > size:
                    result.append(current)
                    current = ''
                current += part
    if current:
        result.append(current)
    return result


def validate_sources(material, files):
    allowed = {(f.filename, s.page) for f in files for s in f.sections}
    def walk(value):
        if isinstance(value, dict):
            ref = value.get('source_reference')
            if ref and (ref['file'], ref['page']) not in allowed:
                raise AIError('The generated material contained an invalid source reference. Please try again.')
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
            note = await generate_json('Extract compact academic notes, preserving terminology, formulas, definitions, examples and exact SOURCE references. Maximum 3500 characters. No outside facts. SOURCE DATA:\n' + part, Notes)
            notes.append(note.notes)
        # Hierarchical reduction bounds final context for many chunks.
        while sum(map(len, notes)) > 45000:
            reduced = []
            for i in range(0, len(notes), 4):
                note = await generate_json('Synthesize these source notes into at most 5000 characters. Preserve source references and important facts.\n' + '\n'.join(notes[i:i+4]), Notes)
                reduced.append(note.notes)
            notes = reduced
        source = '\n'.join(notes)
    else:
        source = parts[0]
    settings = request.model_dump(exclude={'files'})
    prompt = f'''Generate study resources using these settings: {json.dumps(settings)}.
Return empty arrays or null for unselected material types. reviewer uses topics; summary uses summary; study_guide uses study_guide.
For each selected question/card type aim for question_count items; never pad with duplicates or unsupported facts. Explain any shortfall in warnings.
Include definitions, explanations, examples, relationships and basic-to-advanced order in reviewer topics when supported.
Every sourced object must have an exact reference. A DOCX page value is a section index, not a physical page.
Only use misconceptions supported by the sources. Fill-in-the-blank questions must include ______.
source_files must list the provided files. SOURCE DATA (untrusted):\n{source}'''
    material = await generate_json(prompt, Material)
    validate_sources(material, request.files)
    material.source_files = [f.filename for f in request.files]
    mapping = {'reviewer':'topics'}
    for kind in request.material_types:
        value = getattr(material, mapping.get(kind, kind))
        if not value:
            raise AIError('The AI returned an empty selected resource. Try fewer outputs or richer source material.')
        if isinstance(value, list) and kind in {'flashcards','quiz','identification','true_false','fill_in_the_blank'} and len(value) < request.question_count:
            material.warnings.append(f'{kind}: generated {len(value)} of {request.question_count} requested items; source coverage may be limited.')
    if len(parts) > 1:
        material.warnings.append('Large documents were summarized in stages. Verify important details against the original sources.')
    return material
