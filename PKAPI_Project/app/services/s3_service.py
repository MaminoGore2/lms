import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from app.config import settings
import logging
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class S3Service:
    def __init__(self):
        self.client = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            config=Config(signature_version='s3v4'),
            region_name=settings.S3_REGION
        )
        self.bucket = settings.S3_BUCKET
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Проверяет существование бакета и создает его при необходимости"""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            # Бакет не существует, создаем
            try:
                self.client.create_bucket(Bucket=self.bucket)
                logger.info(f"Bucket {self.bucket} created successfully")
            except ClientError as e:
                logger.error(f"Failed to create bucket {self.bucket}: {e}")

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> Optional[str]:
        """
        Генерирует временную подписанную ссылку на объект в S3.

        Args:
            key: путь к файлу в бакете (например, "courses/123/lesson1/video.mp4")
            expires_in: время жизни ссылки в секундах

        Returns:
            URL для доступа к файлу или None в случае ошибки
        """
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': key},
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {key}: {e}")
            return None

    def upload_file(self, file_content: bytes, key: str, content_type: str = None) -> bool:
        """
        Загружает файл в S3.

        Args:
            file_content: содержимое файла в байтах
            key: путь для сохранения
            content_type: MIME тип файла

        Returns:
            True при успешной загрузке
        """
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type

            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=file_content,
                **extra_args
            )
            logger.info(f"File uploaded successfully: {key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload file {key}: {e}")
            return False

    def get_video_url(self, course_id: str, lesson_id: str, filename: str) -> Optional[str]:
        """
        Удобный метод для получения ссылки на видео урока.
        """
        key = f"courses/{course_id}/lessons/{lesson_id}/{filename}"
        return self.generate_presigned_url(key)

    def get_certificate_url(self, user_id: str, course_id: str) -> Optional[str]:
        """
        Получает ссылку на сертификат пользователя.
        """
        key = f"certificates/{course_id}/{user_id}.pdf"
        return self.generate_presigned_url(key, expires_in=604800)  # неделя


# Глобальный экземпляр сервиса
s3_service = S3Service()