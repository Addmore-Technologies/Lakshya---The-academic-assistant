"""Extract searchable text from PDF pages into the common slide/page chunk shape."""
from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .ppt import ParsedDeck, PptParseError, SlideChunk


def parse_pdf(source: str | Path | BinaryIO) -> ParsedDeck:
    """Return one chunk per PDF page containing extractable text.

    Image-only/scanned pages are reported as skipped; OCR is intentionally not
    attempted by this lightweight parser.
    """
    try:
        reader = PdfReader(source, strict=True)
        if reader.is_encrypted:
            try:
                if not reader.decrypt(""):
                    raise PptParseError("This PDF is password-protected and cannot be processed.")
            except Exception as exc:
                if isinstance(exc, PptParseError):
                    raise
                raise PptParseError("This PDF is password-protected and cannot be processed.") from exc
        chunks: list[SlideChunk] = []
        skipped: list[int] = []
        for number, page in enumerate(reader.pages, start=1):
            text = "\n".join(" ".join(line.split()) for line in (page.extract_text() or "").splitlines() if line.strip())
            if text:
                chunks.append(SlideChunk(slide_number=number, text=text))
            else:
                skipped.append(number)
        return ParsedDeck(tuple(chunks), tuple(skipped), len(reader.pages))
    except PptParseError:
        raise
    except (PdfReadError, ValueError, OSError, KeyError) as exc:
        raise PptParseError(f"Could not read the file as a PDF: {exc}") from exc
