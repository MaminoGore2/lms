from sqlalchemy.orm import Session
from app.models.enrollment import Enrollment, EnrollmentState
from app.models.attempt import Attempt
from app.services.course_loader import course_registry
from app.services.rules_engine import RulesEngine
from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ProgressService:
    """
    Сервис для управления прогрессом пользователя.
    """

    @staticmethod
    def get_or_create_enrollment(db: Session, user_id: str, course_id: str) -> Enrollment:
        """
        Получает существующее зачисление или создает новое.
        """
        enrollment = db.query(Enrollment).filter(
            Enrollment.user_id == user_id,
            Enrollment.course_id == course_id
        ).first()

        if not enrollment:
            enrollment = Enrollment(
                user_id=user_id,
                course_id=course_id,
                state=EnrollmentState.STARTED
            )
            db.add(enrollment)
            db.commit()
            db.refresh(enrollment)
            logger.info(f"Created new enrollment for user {user_id} in course {course_id}")

        return enrollment

    @staticmethod
    def update_progress(db: Session, enrollment_id: str) -> Dict[str, Any]:
        """
        Пересчитывает прогресс пользователя на основе завершенных действий.
        Возвращает обновленный контекст прогресса.
        """
        enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
        if not enrollment:
            return {}

        course = course_registry.get(enrollment.course_id)
        if not course:
            logger.error(f"Course {enrollment.course_id} not found in registry")
            return {}

        # Получаем все попытки тестов
        attempts = db.query(Attempt).filter(
            Attempt.enrollment_id == enrollment_id,
            Attempt.status == "completed"
        ).all()

        # Вычисляем прогресс
        total_lessons = 0
        completed_lessons_count = len(enrollment.completed_lessons or [])

        # Подсчет общего количества уроков в курсе
        for module in course.modules:
            total_lessons += len(module.lessons)

        # Вычисляем средний балл
        scores = [a.score for a in attempts if a.score is not None]
        avg_score = sum(scores) / len(scores) if scores else 0

        # Прогресс в процентах
        if total_lessons > 0:
            progress = (completed_lessons_count / total_lessons) * 100
        else:
            progress = 0

        # Обновляем enrollment
        enrollment.progress_percent = progress

        # Проверяем, завершен ли курс
        completed_all = completed_lessons_count >= total_lessons

        # Если все уроки пройдены, меняем состояние
        if completed_all and enrollment.state not in [EnrollmentState.COURSE_FINISHED, EnrollmentState.CERTIFIED]:
            enrollment.state = EnrollmentState.COURSE_FINISHED
            logger.info(f"Course finished for enrollment {enrollment_id}")

        db.commit()

        # Формируем контекст для проверки правил
        context = {
            'completed_all': completed_all,
            'completed_all_lessons': completed_all,
            'average_score': avg_score,
            'final_exam_score': ProgressService._get_final_exam_score(attempts, course),
            'total_attempts': len(attempts),
            'days_enrolled': (datetime.utcnow() - enrollment.created_at).days
        }

        return context

    @staticmethod
    def _get_final_exam_score(attempts: list, course) -> float:
        """
        Получает балл за финальный экзамен (последний тест курса).
        """
        if not course.modules:
            return 0

        # Ищем последний модуль с тестом
        final_module = max(
            [m for m in course.modules if m.test],
            key=lambda m: m.order,
            default=None
        )

        if not final_module:
            return 0

        # Ищем попытку для этого модуля
        for attempt in attempts:
            if attempt.module_id == final_module.module_id:
                return attempt.score or 0

        return 0

    @staticmethod
    def check_and_issue_certificate(db: Session, enrollment_id: str) -> bool:
        """
        Проверяет условия выдачи сертификата и выдает его при выполнении.
        """
        enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
        if not enrollment:
            return False

        # Если уже сертифицирован, ничего не делаем
        if enrollment.state == EnrollmentState.CERTIFIED:
            return True

        course = course_registry.get(enrollment.course_id)
        if not course:
            return False

        # Получаем актуальный контекст прогресса
        context = ProgressService.update_progress(db, enrollment_id)

        # Проверяем условие выдачи сертификата
        if RulesEngine.check_certificate_eligibility(course.dict(), context):
            enrollment.state = EnrollmentState.CERTIFIED
            db.commit()
            logger.info(f"Certificate issued for enrollment {enrollment_id}")

            # Здесь можно вызвать асинхронную задачу для генерации PDF
            # generate_certificate_pdf.delay(enrollment.user_id, enrollment.course_id)

            return True

        return False

    @staticmethod
    def mark_lesson_completed(db: Session, enrollment_id: str, lesson_id: str) -> bool:
        """
        Отмечает урок как пройденный.
        """
        enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
        if not enrollment:
            return False

        if not enrollment.completed_lessons:
            enrollment.completed_lessons = []

        if lesson_id not in enrollment.completed_lessons:
            enrollment.completed_lessons.append(lesson_id)
            db.commit()
            logger.info(f"Lesson {lesson_id} completed for enrollment {enrollment_id}")

            # Обновляем прогресс
            ProgressService.update_progress(db, enrollment_id)

            return True

        return False