"""Extract course outcomes from course-plan text and searchable PDFs."""

from __future__ import annotations

import io
import re

from pypdf import PdfReader


CO_START = re.compile(
    r"(?<![A-Za-z0-9])CO\s*[-:]?\s*([1-9]\d?)\s*[:.\-]?\s*",
    re.IGNORECASE,
)

STOP_LINE = re.compile(
    r"^(?:MODULE\s+[IVX\d]+|COURSE\s+CONTENT|"
    r"CO\s*[-–]\s*PO|TEXT\s*BOOKS?|REFERENCES|"
    r"ASSESSMENT\s+PATTERN)",
    re.IGNORECASE,
)


def extract_cos_from_text(text: str) -> list[dict]:
    """Extract CO1-CO6, including multiline descriptions."""
    results: dict[int, dict] = {}
    lines = text.splitlines()

    for index, line in enumerate(lines):
        stripped = line.strip()
        match = CO_START.match(stripped)

        if not match:
            continue

        number = int(match.group(1))
        if number > 6 or number in results:
            continue

        parts = []
        first = stripped[match.end():].strip(" :-–|")
        if first:
            parts.append(first)

        for next_line in lines[index + 1:]:
            candidate = next_line.strip()

            if not candidate:
                if parts:
                    break
                continue

            if CO_START.match(candidate) or STOP_LINE.match(candidate):
                break

            parts.append(candidate)

        description = " ".join(parts).strip()

        if description:
            results[number] = {
                "number": number,
                "description": description,
                "threshold_pct": 60,
                "target_attainment_pct": 60,
            }

    return [results[n] for n in sorted(results)]


def extract_cos_from_pdf(file_bytes: bytes) -> list[dict]:
    """Extract outcomes from a searchable PDF."""
    reader = PdfReader(io.BytesIO(file_bytes))

    if reader.is_encrypted:
        raise ValueError("Password-protected PDFs are not supported.")

    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    if not text.strip():
        raise ValueError(
            "No selectable text found. This PDF may require OCR."
        )

    return extract_cos_from_text(text)
