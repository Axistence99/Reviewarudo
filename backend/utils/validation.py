from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

class Section(Strict):
    page: int = Field(ge=1)
    title: str = Field(max_length=500)
    content: str = Field(max_length=500000)

class Document(Strict):
    source_type: Literal['pdf', 'docx', 'pptx']
    filename: str = Field(min_length=1, max_length=200)
    sections: list[Section] = Field(min_length=1, max_length=2000)

MaterialType = Literal['reviewer','flashcards','quiz','identification','true_false','fill_in_the_blank','key_terms','summary','study_guide']
class GenerateRequest(Strict):
    files: list[Document] = Field(min_length=1, max_length=8)
    material_types: list[MaterialType] = Field(min_length=1, max_length=9)
    difficulty: Literal['beginner','intermediate','advanced','college'] = 'college'
    question_difficulty: Literal['easy','mixed','challenging'] = 'mixed'
    question_count: Literal[10,20,30,50,100] = 20
    language: str = Field(default='English', min_length=1, max_length=60)
    learning_style: Literal['Quick Review','Detailed Study','Exam Preparation','Memorization','Concept Understanding'] = 'Exam Preparation'

    @model_validator(mode='after')
    def limit_content(self):
        if sum(len(s.content) for f in self.files for s in f.sections) > 400000:
            raise ValueError('Combined extracted text exceeds 400,000 characters. Split the documents.')
        names = [f.filename for f in self.files]
        if len(names) != len(set(names)):
            raise ValueError('Source filenames must be unique.')
        for file in self.files:
            pages = [s.page for s in file.sections]
            if len(pages) != len(set(pages)) or not any(s.content.strip() for s in file.sections):
                raise ValueError('Sections must have unique references and readable content.')
        return self

class Reference(Strict):
    file: str
    page: int = Field(ge=1)

class Sourced(Strict):
    source_reference: Reference

class Term(Sourced):
    term: str
    definition: str

class QA(Sourced):
    question: str
    answer: str

class Quiz(Sourced):
    question: str
    choices: list[str] = Field(min_length=4, max_length=4)
    correct_answer: str
    explanation: str

    @model_validator(mode='after')
    def valid_answer(self):
        if len(set(self.choices)) != 4 or self.correct_answer not in self.choices:
            raise ValueError('Choices must be distinct and contain the correct answer.')
        return self

class TF(Sourced):
    statement: str
    answer: bool
    explanation: str

class Topic(Sourced):
    title: str
    summary: str
    key_points: list[str]
    key_terms: list[Term]
    examples: list[str]
    relationships: list[str]

class Summary(Sourced):
    overview: str
    section_summaries: list[str]
    key_takeaways: list[str]
    final_review: str

class Guide(Sourced):
    main_topics: list[str]
    learning_objectives: list[str]
    important_concepts: list[str]
    key_terminology: list[str]
    common_misconceptions: list[str]
    examples: list[str]
    review_questions: list[str]
    final_summary: str

class Material(Strict):
    title: str
    source_files: list[str]
    summary: Summary | None
    topics: list[Topic]
    flashcards: list[QA]
    quiz: list[Quiz]
    identification: list[QA]
    true_false: list[TF]
    fill_in_the_blank: list[QA]
    key_terms: list[Term]
    study_guide: Guide | None
    warnings: list[str]
