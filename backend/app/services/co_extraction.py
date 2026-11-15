"""Extract course outcomes from searchable syllabus PDFs."""

from __future__ import annotations

import io
import re

from pypdf import PdfReader

CO_ROW = re.compile(
    r"^\s*(?:\d{1,2}\s*[.)]\s*)?CO\s*[-:]?\s*([1-6])\b"
    r"\s*[:.\-]?\s*",
    re.IGNORECASE,
)

SECTION_START = re.compile(
    r"^\s*Course\s+Outcomes\s*:",
    re.IGNORECASE,
)

SECTION_END = re.compile(
    r"^\s*(?:CO\s*[-–]\s*PO(?:/PSO)?\s+Mapping|"
    r"MODULE\s+[IVX\d]+|COURSE\s+CONTENT|"
    r"TEXT\s*BOOKS?|REFERENCES)\b",
    re.IGNORECASE,
)

BLOOM = {
    "remembering": 1,
    "understanding": 2,
    "applying": 3,
    "analyzing": 4,
    "evaluating": 5,
    "creating": 6,
}

BLOOM_PATTERN = re.compile(
    r"\b(Remembering|Understanding|Applying|Analyzing|"
    r"Evaluating|Creating)\s*(?:\(\s*[1-6]\s*\))?",
    re.IGNORECASE,
)


def _parse_row(number: int, content: str) -> dict | None:
    """Parse a CO row and its explicitly stated Bloom level."""
    bloom_match = BLOOM_PATTERN.search(content)

    bloom_name = None
    bloom_level = None

    if bloom_match:
        bloom_name = bloom_match.group(1).capitalize()
        bloom_level = BLOOM[bloom_name.lower()]
        content = (
            content[:bloom_match.start()]
            + " "
            + content[bloom_match.end():]
        )

    description = re.sub(r"\s+", " ", content).strip(" .|:-")
    description = description.rstrip(".")

    # Reject numeric CO-PO mapping rows and malformed descriptions.
    if len(description) < 15:
        return None

    if len(re.findall(r"[A-Za-z]+", description)) < 4:
        return None

    return {
        "number": number,
        "description": description,
        "bloom_level": bloom_level,
        "bloom_name": bloom_name,
        "threshold_pct": 60,
        "target_attainment_pct": 60,
    }


def extract_cos_from_text(text: str) -> list[dict]:
    """Extract CO descriptions, prioritizing explicit CO sections."""
    lines = text.splitlines()
    results = {}

    inside_section = False
    saw_section = False
    current_number = None
    current_parts = []

    def finish_row():
        nonlocal current_number, current_parts

        if current_number is not None:
            parsed = _parse_row(
                current_number, " ".join(current_parts)
            )
            if parsed is not None:
                results[current_number] = parsed

        current_number = None
        current_parts = []

    for line in lines:
        stripped = line.strip()

        if SECTION_START.match(stripped):
            finish_row()
            inside_section = True
            saw_section = True
            continue

        if inside_section and SECTION_END.match(stripped):
            finish_row()
            inside_section = False
            continue

        if not inside_section:
            continue

        match = CO_ROW.match(stripped)

        if match:
            finish_row()
            current_number = int(match.group(1))
            remainder = stripped[match.end():].strip()
            if remainder:
                current_parts.append(remainder)
            continue

        if current_number is not None and stripped:
            current_parts.append(stripped)

    finish_row()

    # Do not fall back to unrelated CO mapping tables.
    if not saw_section:
        return []

    return [results[n] for n in sorted(results)]


def extract_cos_from_pdf(file_bytes: bytes) -> list[dict]:
    """Extract outcomes from a PDF with selectable text."""
    reader = PdfReader(io.BytesIO(file_bytes))

    if reader.is_encrypted:
        raise ValueError("Password-protected PDFs are not supported.")

    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    if not text.strip():
        raise ValueError(
            "No selectable text found. This PDF may require OCR."
        )

    return extract_cos_from_text(text)
