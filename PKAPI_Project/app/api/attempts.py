from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from app.models.database import get_db
from app.models.attempt import Attempt
from app.models.enrollment import Enrollment
from app.services.course_loader import course_registry
from app.services.rules_engine import RulesEngine
from app.services.progress import ProgressService
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging

router = APIRouter(prefix="/api/v1", tags=["attempts"])
logger = logging.getLogger(__name__)


class AttemptSubmit(BaseModel):
    user_id: str
    answers: Dict[str, List[str]]  # question_id -> [answer_ids]


class AttemptResponse(BaseModel):
    attempt_id: str
    score: float
    passed: bool
    max_score: float
    completed_at: datetime


@router.post("/courses/{course_id}/modules/{module_id}/attempt")
async def start_attempt(
        course_id: str,
        module_id: str,
        user_id: str = Query(...),
        db: Session = Depends(get_db)
):
    """
    Начать новую попытку прохождения теста.
    """
    course = course_registry.get(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Находим модуль с тестом
    target_module = None
    for module in course.modules:
        if module.module_id == module_id:
            target_module = module
            break

    if not target_module or not target_module.test:
        raise HTTPException(status_code=404, detail="Test not found in this module")

    # Получаем зачисление
    enrollment = db.query(Enrollment).filter(
        Enrollment.user_id == user_id,
        Enrollment.course_id == course_id
    ).first()

    if not enrollment:
        enrollment = ProgressService.get_or_create_enrollment(db, user_id, course_id)

    # Проверяем количество попыток
    attempts_count = db.query(Attempt).filter(
        Attempt.enrollment_id == enrollment.id,
        Attempt.module_id == module_id,
        Attempt.status == "completed"
    ).count()

    max_attempts = target_module.test.attempts_allowed
    if attempts_count >= max_attempts:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum attempts ({max_attempts}) reached"
        )

    # Создаем новую попытку
    attempt = Attempt(
        id=uuid.uuid4(),
        user_id=user_id,
        enrollment_id=enrollment.id,
        course_id=course_id,
        module_id=module_id,
        snapshot=target_module.test.dict(),  # Сохраняем конфиг теста
        answers={},  # Пустые ответы пока
        status="in_progress"
    )

    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    # Отдаем вопросы без правильных ответов
    test_data = target_module.test.dict()
    for q in test_data['questions']:
        q.pop('correct_answers', None)  # Убираем правильные ответы

    return {
        "attempt_id": str(attempt.id),
        "test": test_data,
        "time_limit_minutes": target_module.test.time_limit_minutes
    }


@router.post("/attempts/{attempt_id}/submit")
async def submit_attempt(
        attempt_id: str,
        attempt_data: AttemptSubmit,
        db: Session = Depends(get_db)
):
    """
    Отправить ответы на тест и получить результат.
    """
    # Получаем попытку
    attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    if attempt.status != "in_progress":
        raise HTTPException(status_code=400, detail="Attempt already completed")

    # Вычисляем баллы
    score = RulesEngine.calculate_test_score(attempt_data.answers, attempt.snapshot)
    max_score = sum(q.get('points', 1.0) for q in attempt.snapshot.get('questions', []))

    # Обновляем попытку
    attempt.answers = attempt_data.answers
    attempt.score = score
    attempt.max_score = max_score
    attempt.status = "completed"
    attempt.completed_at = datetime.utcnow()

    db.commit()

    # Проверяем, пройден ли тест
    passed = score >= attempt.snapshot.get('passing_score', 60.0)

    # Обновляем прогресс пользователя
    ProgressService.update_progress(db, attempt.enrollment_id)

    # Проверяем условия для сертификата
    if passed:
        ProgressService.check_and_issue_certificate(db, attempt.enrollment_id)

    return AttemptResponse(
        attempt_id=str(attempt.id),
        score=score,
        passed=passed,
        max_score=max_score,
        completed_at=attempt.completed_at
    )


@router.get("/attempts/{attempt_id}")
async def get_attempt_result(
        attempt_id: str,
        db: Session = Depends(get_db)
):
    """
    Получить результат попытки.
    """
    attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    return {
        "attempt_id": str(attempt.id),
        "score": attempt.score,
        "max_score": attempt.max_score,
        "status": attempt.status,
        "completed_at": attempt.completed_at,
        "answers": attempt.answers
    }