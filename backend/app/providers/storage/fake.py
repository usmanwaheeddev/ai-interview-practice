class FakeStorageProvider:
    """In-memory — used by tests. See skills.md `generate-synthetic-candidate`
    and plan.md §3.7 on why tests never hit real infrastructure."""

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}

    async def put_object(self, key: str, data: bytes, *, content_type: str) -> None:
        self._objects[key] = (data, content_type)

    async def get_object(self, key: str) -> bytes:
        return self._objects[key][0]

    async def delete_object(self, key: str) -> None:
        self._objects.pop(key, None)

    async def get_presigned_url(self, key: str, *, expires_in: int = 3600) -> str:
        return f"fake://{key}?expires_in={expires_in}"

    async def get_presigned_put_url(
        self, key: str, *, content_type: str, expires_in: int = 3600
    ) -> str:
        return f"fake://{key}?expires_in={expires_in}&content_type={content_type}&method=PUT"

    async def health(self) -> bool:
        return True
