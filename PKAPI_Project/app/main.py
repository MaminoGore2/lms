from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import threading

from app.api import courses, attempts, health
from app.services.course_loader import start_course_watcher
from app.config import settings

# Настройка логирования
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Создание FastAPI приложения
app = FastAPI(
    title="LMS Backend API",
    description="Programmable Learning Management System",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене заменить на конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(courses.router)
app.include_router(attempts.router)
app.include_router(health.router)


@app.on_event("startup")
async def startup_event():
    """
    Действия при запуске приложения.
    """
    logger.info("Starting LMS Backend...")

    # Запуск наблюдателя за конфигами курсов в фоновом потоке
    def start_watcher():
        observer = start_course_watcher(settings.COURSES_CONFIG_PATH)
        import time
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

    # Запускаем в отдельном потоке, чтобы не блокировать FastAPI
    watcher_thread = threading.Thread(target=start_watcher, daemon=True)
    watcher_thread.start()

    logger.info(f"LMS Backend started. Watching {settings.COURSES_CONFIG_PATH}")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Действия при остановке приложения.
    """
    logger.info("Shutting down LMS Backend...")


@app.get("/")
async def root():
    return {
        "message": "LMS Backend API",
        "docs": "/docs",
        "health": "/health/ready"
    }