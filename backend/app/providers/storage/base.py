from typing import Protocol


class StorageProvider(Protocol):
    """See architecture.md §7 — no vendor SDK outside app/providers/."""

    async def put_object(self, key: str, data: bytes, *, content_type: str) -> None: ...

    async def get_object(self, key: str) -> bytes: ...

    async def delete_object(self, key: str) -> None:
        """GDPR erasure / retention (Phase 6) — best-effort: callers should
        tolerate a missing key (already gone) rather than treat it as an
        error."""
        ...

    async def get_presigned_url(self, key: str, *, expires_in: int = 3600) -> str: ...

    async def get_presigned_put_url(
        self, key: str, *, content_type: str, expires_in: int = 3600
    ) -> str:
        """Direct browser-to-storage upload — architecture.md §8: media
        (interview recordings) uses presigned PUT, unlike resumes (Phase 1),
        which are small enough to proxy through the backend for magic-byte
        validation. See memory.md ADR-013 for that distinction."""
        ...

    async def health(self) -> bool: ...
