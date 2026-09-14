from httpx import AsyncClient

PDF_BYTES = b"%PDF-1.4\n%fake minimal pdf content for magic-byte testing\n%%EOF"
DOCX_BYTES = b"PK\x03\x04" + b"fake docx zip content"


async def _register_candidate(client: AsyncClient, email: str = "cand@example.com") -> None:
    res = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "full_name": "Cand Person"},
    )
    assert res.status_code == 201, res.text


async def test_valid_pdf_upload_accepted(client: AsyncClient, fake_queue) -> None:
    await _register_candidate(client)

    res = await client.post(
        "/api/resumes",
        files={"file": ("resume.pdf", PDF_BYTES, "application/pdf")},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["filename"] == "resume.pdf"
    assert body["parse_status"] == "pending"

    assert fake_queue.enqueued == [("parse_resume", (body["id"],))]


async def test_valid_docx_upload_accepted(client: AsyncClient) -> None:
    await _register_candidate(client)

    res = await client.post(
        "/api/resumes",
        files={
            "file": (
                "resume.docx",
                DOCX_BYTES,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert res.status_code == 201, res.text


async def test_oversized_file_rejected(client: AsyncClient) -> None:
    await _register_candidate(client)

    oversized = PDF_BYTES + b"0" * (10 * 1024 * 1024)
    res = await client.post(
        "/api/resumes",
        files={"file": ("resume.pdf", oversized, "application/pdf")},
    )
    assert res.status_code == 422
    assert res.json()["code"] == "invalid_resume"


async def test_spoofed_content_type_rejected(client: AsyncClient) -> None:
    """Bytes claim to be a PDF via content-type but don't start with %PDF —
    architecture.md §8: magic-byte sniffing, not extension/content-type trust."""
    await _register_candidate(client)

    res = await client.post(
        "/api/resumes",
        files={"file": ("resume.pdf", b"this is not a pdf at all", "application/pdf")},
    )
    assert res.status_code == 422
    assert res.json()["code"] == "invalid_resume"


async def test_disallowed_content_type_rejected(client: AsyncClient) -> None:
    await _register_candidate(client)

    res = await client.post(
        "/api/resumes",
        files={"file": ("resume.exe", b"MZ\x90\x00", "application/x-msdownload")},
    )
    assert res.status_code == 422
    assert res.json()["code"] == "invalid_resume"


async def test_list_my_resumes_returns_only_own(client_factory) -> None:
    cand_a = await client_factory()
    cand_b = await client_factory()

    await _register_candidate(cand_a, "a2@example.com")
    await _register_candidate(cand_b, "b2@example.com")

    await cand_a.post("/api/resumes", files={"file": ("r1.pdf", PDF_BYTES, "application/pdf")})
    await cand_a.post("/api/resumes", files={"file": ("r2.pdf", PDF_BYTES, "application/pdf")})
    await cand_b.post("/api/resumes", files={"file": ("r3.pdf", PDF_BYTES, "application/pdf")})

    res = await cand_a.get("/api/resumes")
    assert res.status_code == 200
    filenames = {r["filename"] for r in res.json()}
    assert filenames == {"r1.pdf", "r2.pdf"}


async def test_candidate_cannot_fetch_another_candidates_resume(client_factory) -> None:
    cand_a = await client_factory()
    cand_b = await client_factory()

    await _register_candidate(cand_a, "a@example.com")
    await _register_candidate(cand_b, "b@example.com")

    upload = await cand_a.post(
        "/api/resumes",
        files={"file": ("resume.pdf", PDF_BYTES, "application/pdf")},
    )
    resume_id = upload.json()["id"]

    res = await cand_b.get(f"/api/resumes/{resume_id}")
    assert res.status_code == 404
