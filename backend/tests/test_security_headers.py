from httpx import AsyncClient


async def test_response_has_baseline_security_headers(client: AsyncClient) -> None:
    res = await client.get("/health")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "same-origin"
    assert "camera=(self)" in res.headers["Permissions-Policy"]


async def test_hsts_not_sent_outside_production(client: AsyncClient) -> None:
    """Tests run with ENV=development (conftest doesn't override it) — HSTS
    over plain HTTP would just be ignored by the browser anyway, so it's
    cleaner not to claim it."""
    res = await client.get("/health")
    assert "Strict-Transport-Security" not in res.headers
