from sqlalchemy import Column, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.database import Base
import uuid
from datetime import datetime


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("enrollments.id"), nullable=False)
    course_id = Column(String, nullable=False)
    module_id = Column(String, nullable=False)

    # Слепок конфигурации теста на момент попытки
    snapshot = Column(JSON, nullable=False)
    # Ответы пользователя
    answers = Column(JSON, nullable=False)
    # Результат
    score = Column(Float)
    max_score = Column(Float)
    status = Column(String, default="in_progress")  # in_progress, completed, failed

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    def __repr__(self):
        return f"<Attempt {self.id} score={self.score}>"