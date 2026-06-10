import base64
import io


def extract_text(content_base64: str, content_type: str, file_name: str) -> str:
    raw = base64.b64decode(content_base64)
    lower_name = file_name.lower()
    if content_type == "application/pdf" or lower_name.endswith(".pdf"):
        return extract_pdf_text(raw)
    return raw.decode("utf-8", errors="ignore")


def extract_pdf_text(raw: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(page.strip() for page in pages if page.strip())
