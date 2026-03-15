import json
import jsonschema
from typing import Tuple, Any, Optional

# JSON Schema для конфигурации курса
COURSE_SCHEMA = {
    "type": "object",
    "required": ["course_id", "title", "modules"],
    "properties": {
        "course_id": {"type": "string", "pattern": "^[a-zA-Z0-9_-]+$"},
        "title": {"type": "string", "minLength": 3, "maxLength": 200},
        "description": {"type": "string"},
        "enforce_sequence": {"type": "boolean"},
        "start_date": {"type": "string", "format": "date"},
        "release_schedule": {"type": "string", "enum": ["weekly", "all_at_once"]},
        "certificate_rule": {
            "type": "object",
            "properties": {
                "expression": {"type": "string"},
                "description": {"type": "string"}
            }
        },
        "modules": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["module_id", "title", "lessons", "order"],
                "properties": {
                    "module_id": {"type": "string", "pattern": "^[a-zA-Z0-9_-]+$"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "order": {"type": "integer", "minimum": 1},
                    "lessons": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["lesson_id", "title", "type", "order"],
                            "properties": {
                                "lesson_id": {"type": "string"},
                                "title": {"type": "string"},
                                "type": {"type": "string", "enum": ["video", "text", "quiz"]},
                                "content": {"type": "object"},
                                "duration_minutes": {"type": "integer", "minimum": 1},
                                "order": {"type": "integer", "minimum": 1}
                            }
                        }
                    },
                    "test": {
                        "type": "object",
                        "properties": {
                            "test_id": {"type": "string"},
                            "title": {"type": "string"},
                            "passing_score": {"type": "number", "minimum": 0, "maximum": 100},
                            "attempts_allowed": {"type": "integer", "minimum": 1},
                            "questions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["question_id", "text", "type", "correct_answers"],
                                    "properties": {
                                        "question_id": {"type": "string"},
                                        "text": {"type": "string"},
                                        "type": {"type": "string",
                                                 "enum": ["single_choice", "multiple_choice", "text"]},
                                        "options": {"type": "array", "items": {"type": "string"}},
                                        "correct_answers": {"type": "array", "items": {"type": "string"}},
                                        "points": {"type": "number", "minimum": 0.1}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}


def validate_course_json(data: dict) -> Tuple[bool, Optional[str]]:
    """
    Проверяет JSON конфигурацию курса на соответствие схеме.
    Возвращает (True, None) если валидно, иначе (False, сообщение об ошибке)
    """
    try:
        jsonschema.validate(instance=data, schema=COURSE_SCHEMA)

        # Дополнительные проверки
        # 1. Уроки должны иметь уникальные ID в рамках курса
        lesson_ids = set()
        for module in data.get('modules', []):
            for lesson in module.get('lessons', []):
                lesson_id = lesson.get('lesson_id')
                if lesson_id in lesson_ids:
                    return False, f"Duplicate lesson_id: {lesson_id}"
                lesson_ids.add(lesson_id)

        # 2. Проверка корректности порядка уроков
        for module in data.get('modules', []):
            orders = [l.get('order', 0) for l in module.get('lessons', [])]
            expected = list(range(1, len(orders) + 1))
            if sorted(orders) != expected:
                return False, f"Lesson orders must be consecutive starting from 1 in module {module.get('module_id')}"

        return True, None
    except jsonschema.exceptions.ValidationError as e:
        return False, str(e)


def validate_certificate_rule(expression: str) -> bool:
    """
    Простая проверка синтаксиса правила сертификации.
    """
    allowed_keywords = ['completed_all', 'avg_score', 'final_exam_score', 'total_attempts', 'days_enrolled']
    allowed_ops = ['and', 'or', 'not', '>=', '<=', '>', '<', '==', '!=']

    # Базовая проверка на опасные конструкции
    forbidden = ['__', 'import', 'exec', 'eval', 'open', 'system']
    for word in forbidden:
        if word in expression:
            return False

    return True