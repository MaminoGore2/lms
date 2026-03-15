from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from app.models.database import get_db
from app.services.course_loader import course_registry
from app.services.progress import ProgressService
from app.services.s3_service import s3_service
from app.models.enrollment import Enrollment
from datetime import datetime
import logging

router = APIRouter(prefix="/api/v1/courses", tags=["courses"])
logger = logging.getLogger(__name__)


@router.get("")
async def list_courses():
    """
    Получение списка всех доступных курсов.
    """
    courses = course_registry.get_all()
    result = []
    for course_id, course in courses.items():
        result.append({
            "course_id": course.course_id,
            "title": course.title,
            "description": course.description,
            "modules_count": len(course.modules)
        })
    return {"courses": result}


@router.get("/{course_id}")
async def get_course_info(course_id: str):
    """
    Получение информации о курсе.
    """
    course = course_registry.get(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    return {
        "course_id": course.course_id,
        "title": course.title,
        "description": course.description,
        "enforce_sequence": course.enforce_sequence,
        "start_date": course.start_date
    }


@router.get("/{course_id}/structure")
async def get_course_structure(
        course_id: str,
        user_id: str = Query(..., description="ID пользователя"),
        db: Session = Depends(get_db)
):
    """
    Получение структуры курса с учетом прогресса пользователя.
    """
    course = course_registry.get(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Получаем зачисление пользователя
    enrollment = db.query(Enrollment).filter(
        Enrollment.user_id == user_id,
        Enrollment.course_id == course_id
    ).first()

    if not enrollment:
        enrollment = ProgressService.get_or_create_enrollment(db, user_id, course_id)

    # Формируем структуру с учетом прогресса
    completed_lessons = set(enrollment.completed_lessons or [])
    completed_modules = set(enrollment.completed_modules or [])

    structure = {
        "course_id": course.course_id,
        "title": course.title,
        "progress_percent": enrollment.progress_percent,
        "state": enrollment.state.value,
        "modules": []
    }

    for module in course.modules:
        module_data = {
            "module_id": module.module_id,
            "title": module.title,
            "order": module.order,
            "lessons": [],
            "has_test": module.test is not None,
            "is_completed": module.module_id in completed_modules
        }

        # Проверяем доступность модуля (sequence enforcement)
        is_module_locked = False
        if course.enforce_sequence and module.order > 1:
            # Находим предыдущий модуль
            prev_modules = [m for m in course.modules if m.order == module.order - 1]
            if prev_modules:
                prev_module = prev_modules[0]
                if prev_module.module_id not in completed_modules:
                    is_module_locked = True

        module_data["is_locked"] = is_module_locked

        # Добавляем уроки
        for lesson in module.lessons:
            lesson_data = {
                "lesson_id": lesson.lesson_id,
                "title": lesson.title,
                "type": lesson.type.value,
                "order": lesson.order,
                "is_completed": lesson.lesson_id in completed_lessons,
                "duration_minutes": lesson.duration_minutes
            }

            # Если урок видео - генерируем ссылку
            if lesson.type.value == "video" and not is_module_locked:
                # Получаем имя файла из контента
                filename = lesson.content.get("filename", "video.mp4")
                stream_url = s3_service.get_video_url(course_id, lesson.lesson_id, filename)
                lesson_data["stream_url"] = stream_url
            elif lesson.type.value == "text":
                lesson_data["content"] = lesson.content.get("text", "")

            module_data["lessons"].append(lesson_data)

        structure["modules"].append(module_data)

    return structure


@router.post("/{course_id}/lessons/{lesson_id}/complete")
async def complete_lesson(
        course_id: str,
        lesson_id: str,
        user_id: str = Query(...),
        db: Session = Depends(get_db)
):
    """
    Отметить урок как пройденный.
    """
    enrollment = ProgressService.get_or_create_enrollment(db, user_id, course_id)

    success = ProgressService.mark_lesson_completed(db, enrollment.id, lesson_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to mark lesson as completed")

    # Проверяем условия для сертификата
    ProgressService.check_and_issue_certificate(db, enrollment.id)

    return {"status": "completed"}