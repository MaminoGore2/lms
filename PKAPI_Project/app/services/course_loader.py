import json
import os
import logging
from typing import Dict, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from app.models.course import Course
from app.utils.validators import validate_course_json
from threading import Lock
import time

logger = logging.getLogger(__name__)


class CourseRegistry:
    """
    Хранилище загруженных курсов в памяти.
    Потокобезопасное с блокировками для чтения/записи.
    """

    def __init__(self):
        self._courses: Dict[str, Course] = {}
        self._lock = Lock()

    def get(self, course_id: str) -> Optional[Course]:
        with self._lock:
            return self._courses.get(course_id)

    def get_all(self) -> Dict[str, Course]:
        with self._lock:
            return self._courses.copy()

    def add_or_update(self, course_id: str, course: Course):
        with self._lock:
            self._courses[course_id] = course
            logger.info(f"Course {course_id} added/updated successfully")

    def remove(self, course_id: str):
        with self._lock:
            if course_id in self._courses:
                del self._courses[course_id]
                logger.info(f"Course {course_id} removed")


# Глобальный реестр курсов
course_registry = CourseRegistry()


class CourseFileHandler(FileSystemEventHandler):
    """Обработчик изменений файлов курсов"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.last_loaded = {}

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            self._process_file(event.src_path)

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            self._process_file(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            course_id = os.path.splitext(os.path.basename(event.src_path))[0]
            course_registry.remove(course_id)

    def _process_file(self, file_path: str):
        """Загрузка или обновление курса из файла"""
        try:
            # Проверяем, не загружали ли мы этот файл только что
            current_mtime = os.path.getmtime(file_path)
            if self.last_loaded.get(file_path) == current_mtime:
                return

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Валидация
            is_valid, error = validate_course_json(data)
            if not is_valid:
                logger.error(f"Invalid course config {file_path}: {error}")
                return

            # Преобразование в Pydantic модель
            course = Course(**data)

            # Сохраняем
            course_registry.add_or_update(course.course_id, course)
            self.last_loaded[file_path] = current_mtime
            logger.info(f"Successfully loaded course {course.course_id} from {file_path}")

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading {file_path}: {e}")


def start_course_watcher(config_path: str):
    """
    Запуск наблюдателя за файлами конфигурации курсов.
    Должен вызываться при старте приложения.
    """
    os.makedirs(config_path, exist_ok=True)

    # Загружаем существующие файлы при старте
    for filename in os.listdir(config_path):
        if filename.endswith('.json'):
            file_path = os.path.join(config_path, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                is_valid, error = validate_course_json(data)
                if is_valid:
                    course = Course(**data)
                    course_registry.add_or_update(course.course_id, course)
                    logger.info(f"Initial load: {course.course_id}")
                else:
                    logger.error(f"Invalid course in initial load {file_path}: {error}")
            except Exception as e:
                logger.error(f"Failed to load {file_path} during initial load: {e}")

    # Запускаем наблюдатель
    event_handler = CourseFileHandler(config_path)
    observer = Observer()
    observer.schedule(event_handler, config_path, recursive=False)
    observer.start()
    logger.info(f"Course watcher started on {config_path}")
    return observer