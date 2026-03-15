from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.models.database import engine, SessionLocal
from app.services.s3_service import s3_service
from app.services.course_loader import course_registry
import logging

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/live")
async def liveness_probe():
    """
    Проверка, что процесс жив.
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@router.get("/ready")
async def readiness_probe():
    """
    Проверка готовности принимать трафик.
    """
    checks = {}
    all_healthy = True

    # Проверка БД
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = {"status": "healthy"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        all_healthy = False

    # Проверка S3
    try:
        s3_service.client.head_bucket(Bucket=s3_service.bucket)
        checks["s3"] = {"status": "healthy"}
    except Exception as e:
        logger.error(f"S3 health check failed: {e}")
        checks["s3"] = {"status": "unhealthy", "error": str(e)}
        all_healthy = False

    # Проверка загруженных конфигов
    courses_loaded = len(course_registry.get_all()) > 0
    checks["configs"] = {
        "status": "healthy" if courses_loaded else "warning",
        "courses_count": len(course_registry.get_all())
    }

    if all_healthy:
        return {"status": "ready", "checks": checks}
    else:
        raise HTTPException(status_code=503, detail={"status": "not ready", "checks": checks})


@router.get("/info")
async def service_info():
    """
    Информация о сервисе.
    """
    return {
        "service": "LMS Backend",
        "version": "1.0.0",
        "courses_loaded": len(course_registry.get_all()),
        "s3_bucket": s3_service.bucket
    }