import os
import shutil
import tempfile
import logging
from abc import ABC, abstractmethod
from typing import Optional
from app.config import settings
from app.utils.audio_utils import sanitize_filename

logger = logging.getLogger(__name__)


class StorageProvider(ABC):
    @abstractmethod
    def save_file(self, note_id: str, filename: str, content: bytes) -> str:
        """Saves content and returns storage_key."""
        pass

    @abstractmethod
    def get_file_bytes(self, storage_key: str) -> bytes:
        """Retrieves file bytes by storage_key."""
        pass

    @abstractmethod
    def get_local_file_path(self, storage_key: str) -> str:
        """Returns a valid local file path (or temp file path) for the audio."""
        pass

    @abstractmethod
    def delete_file(self, storage_key: str) -> bool:
        """Deletes file by storage_key."""
        pass

    @abstractmethod
    def check_health(self) -> str:
        """Returns a public, non-secret health description."""
        pass


class LocalStorageProvider(StorageProvider):
    def __init__(self, base_dir: str = "storage"):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def _get_abs_path(self, storage_key: str) -> str:
        # Prevent path traversal
        norm_key = os.path.normpath(storage_key).lstrip("/\\")
        return os.path.join(self.base_dir, norm_key)

    def save_file(self, note_id: str, filename: str, content: bytes) -> str:
        clean_name = sanitize_filename(filename)
        storage_key = f"audio/{note_id}/{clean_name}"
        abs_path = self._get_abs_path(storage_key)

        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "wb") as f:
            f.write(content)

        logger.info(f"Saved file locally to {abs_path} (key: {storage_key})")
        return storage_key

    def get_file_bytes(self, storage_key: str) -> bytes:
        abs_path = self._get_abs_path(storage_key)
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"Storage file not found: {storage_key}")
        with open(abs_path, "rb") as f:
            return f.read()

    def get_local_file_path(self, storage_key: str) -> str:
        abs_path = self._get_abs_path(storage_key)
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"Storage file not found: {storage_key}")
        return abs_path

    def delete_file(self, storage_key: str) -> bool:
        abs_path = self._get_abs_path(storage_key)
        if os.path.isfile(abs_path):
            os.remove(abs_path)
            # Remove parent directory if empty
            parent = os.path.dirname(abs_path)
            if os.path.exists(parent) and not os.listdir(parent):
                os.rmdir(parent)
            return True
        return False

    def check_health(self) -> str:
        try:
            os.makedirs(self.base_dir, exist_ok=True)
            if os.path.isdir(self.base_dir) and os.access(self.base_dir, os.W_OK):
                return "healthy (persistent filesystem)"
        except Exception:
            pass
        return "unhealthy"


class S3StorageProvider(StorageProvider):
    def __init__(
        self,
        bucket: str,
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: str = "us-east-1",
    ):
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )

    def save_file(self, note_id: str, filename: str, content: bytes) -> str:
        clean_name = sanitize_filename(filename)
        storage_key = f"audio/{note_id}/{clean_name}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=storage_key,
            Body=content,
        )
        logger.info(f"Saved file to S3 bucket {self.bucket} with key {storage_key}")
        return storage_key

    def get_file_bytes(self, storage_key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=storage_key)
        return response["Body"].read()

    def get_local_file_path(self, storage_key: str) -> str:
        # Download object to a temp file
        content = self.get_file_bytes(storage_key)
        suffix = os.path.splitext(storage_key)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            return tmp.name

    def delete_file(self, storage_key: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=storage_key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete S3 object {storage_key}: {e}")
            return False

    def check_health(self) -> str:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return "healthy (s3)"
        except Exception:
            return "unhealthy"


def get_storage_service() -> StorageProvider:
    if settings.STORAGE_PROVIDER == "s3":
        if not settings.STORAGE_ACCESS_KEY or not settings.STORAGE_SECRET_KEY:
            raise RuntimeError("STORAGE_PROVIDER=s3 requires STORAGE_ACCESS_KEY and STORAGE_SECRET_KEY.")
        return S3StorageProvider(
            bucket=settings.STORAGE_BUCKET,
            endpoint_url=settings.STORAGE_ENDPOINT,
            access_key=settings.STORAGE_ACCESS_KEY,
            secret_key=settings.STORAGE_SECRET_KEY,
            region=settings.STORAGE_REGION,
        )
    if settings.STORAGE_PROVIDER == "local":
        return LocalStorageProvider(base_dir=settings.STORAGE_LOCAL_DIR)
    raise RuntimeError(f"Unsupported STORAGE_PROVIDER: {settings.STORAGE_PROVIDER}")


storage_service = get_storage_service()
