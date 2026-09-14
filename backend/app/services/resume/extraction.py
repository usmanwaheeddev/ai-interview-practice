"""Resume file validation and text extraction — no LLM here, see
app/services/resume/parsing.py for the structured-extraction step that calls
the LLM provider. Kept separate so text extraction can be unit tested without
a provider in the loop."""

import io

from docx import Document
from pypdf import PdfReader

PDF_MAGIC = b"%PDF"
DOCX_MAGIC = b"PK\x03\x04"  # DOCX is a zip archive

ALLOWED_CONTENT_TYPES = {
    "application/pdf": PDF_MAGIC,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DOCX_MAGIC,
}

MAX_RESUME_BYTES = 10 * 1024 * 1024  # 10 MB — architecture.md §8


class ResumeValidationError(ValueError):
    pass


def validate_resume_file(data: bytes, *, content_type: str) -> None:
    """Trust bytes, not the client's declared content_type or filename
    extension — architecture.md §8: "magic-byte sniffing (not extension
    trust)"."""
    if len(data) == 0:
        raise ResumeValidationError("Empty file")
    if len(data) > MAX_RESUME_BYTES:
        raise ResumeValidationError(f"File exceeds {MAX_RESUME_BYTES // (1024 * 1024)} MB limit")

    expected_magic = ALLOWED_CONTENT_TYPES.get(content_type)
    if expected_magic is None:
        raise ResumeValidationError("Only PDF and DOCX resumes are accepted")

    if not data.startswith(expected_magic):
        raise ResumeValidationError(
            "File content does not match its declared type — possible spoofed upload"
        )


def extract_text(data: bytes, *, content_type: str) -> str:
    if content_type == "application/pdf":
        return _extract_pdf_text(data)
    return _extract_docx_text(data)


def _extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx_text(data: bytes) -> str:
    document = Document(io.BytesIO(data))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)
