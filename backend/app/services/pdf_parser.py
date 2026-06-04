from pathlib import Path


def extract_pdf_text(path: Path) -> str:
    try:
        import fitz
    except Exception as exc:
        raise RuntimeError("PyMuPDF is not installed. Run pip install -r backend/requirements.txt") from exc

    parts: list[str] = []
    with fitz.open(path) as doc:
        for page in doc:
            parts.append(page.get_text("text"))
    text = "\n".join(parts).strip()
    if not text:
        raise ValueError("No selectable text was found in this PDF.")
    return text
