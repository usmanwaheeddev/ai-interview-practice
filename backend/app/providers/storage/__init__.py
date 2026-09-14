from functools import lru_cache

from app.core.config import get_settings
from app.providers.storage.base import StorageProvider
from app.providers.storage.fake import FakeStorageProvider


@lru_cache
def get_storage_provider() -> StorageProvider:
    settings = get_settings()
    if settings.storage_provider == "fake":
        return FakeStorageProvider()

    from app.providers.storage.s3 import S3StorageProvider

    return S3StorageProvider(settings)
