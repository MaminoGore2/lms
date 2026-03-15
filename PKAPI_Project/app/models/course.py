from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from enum import Enum


class LessonType(str, Enum):
    VIDEO = "video"
    TEXT = "text"
    QUIZ = "quiz"


class QuestionType(str, Enum):
    SINGLE = "single_choice"
    MULTIPLE = "multiple_choice"
    TEXT = "text"


class CertificateRule(BaseModel):
    expression: str  # например: "completed_all and avg_score >= 80"
    description: Optional[str] = None


class Lesson(BaseModel):
    lesson_id: str
    title: str
    type: LessonType
    content: Optional[Dict[str, Any]]  # для текста - сам текст, для видео - ссылка на файл
    duration_minutes: Optional[int] = 5
    order: int


class TestQuestion(BaseModel):
    question_id: str
    text: str
    type: QuestionType
    options: Optional[List[str]] = None  # для multiple/single choice
    correct_answers: List[str]  # ID правильных ответов
    points: float = 1.0


class Test(BaseModel):
    test_id: str
    title: str
    description: Optional[str] = None
    questions: List[TestQuestion]
    passing_score: float = 60.0  # процент правильных ответов
    time_limit_minutes: Optional[int] = None
    attempts_allowed: int = 1


class Module(BaseModel):
    module_id: str
    title: str
    description: Optional[str] = None
    lessons: List[Lesson]
    test: Optional[Test] = None
    order: int


class Course(BaseModel):
    course_id: str
    title: str
    description: str
    modules: List[Module]
    certificate_rule: Optional[CertificateRule] = None
    enforce_sequence: bool = False
    start_date: Optional[str] = None
    release_schedule: Optional[str] = None  # "weekly", "all_at_once"

    @validator('modules')
    def modules_must_have_unique_ids(cls, v):
        module_ids = [m.module_id for m in v]
        if len(module_ids) != len(set(module_ids)):
            raise ValueError('Module IDs must be unique')
        return v

    @validator('modules')
    def lessons_must_have_order(cls, v):
        for module in v:
            orders = [l.order for l in module.lessons]
            if sorted(orders) != list(range(1, len(orders) + 1)):
                raise ValueError(f'Lessons in module {module.module_id} must have consecutive orders starting from 1')
        return v