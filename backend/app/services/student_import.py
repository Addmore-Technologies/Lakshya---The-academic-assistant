import csv
import io
from openpyxl import load_workbook

MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_STUDENTS = 1000


def parse_student_file(filename: str, content: bytes):
    """Parse CSV/XLSX student lists without modifying the database."""
    extension = filename.lower().rsplit(".", 1)[-1]

    if extension not in {"csv", "xlsx"}:
        raise ValueError("Only CSV and XLSX files are supported")

    if not content:
        raise ValueError("The uploaded file is empty")

    if len(content) > MAX_FILE_SIZE:
        raise ValueError("Maximum file size is 5 MB")

    if extension == "csv":
        try:
            decoded = content.decode("utf-8-sig")
            reader = csv.reader(io.StringIO(decoded))
            rows = list(reader)
        except (UnicodeDecodeError, csv.Error) as exc:
            raise ValueError("Invalid UTF-8 CSV file") from exc
    else:
        try:
            workbook = load_workbook(
                io.BytesIO(content),
                read_only=True,
                data_only=True,
            )
            try:
                rows = list(workbook.active.values)
            finally:
                workbook.close()
        except Exception as exc:
            raise ValueError("Invalid Excel file") from exc

    if not rows:
        raise ValueError("The file contains no rows")

    headers = [
        str(value or "").strip().lower().replace("_", " ")
        for value in rows[0]
    ]

    aliases = {
        "usn": {"usn", "student usn", "registration number"},
        "name": {"name", "student name", "full name"},
    }

    def find_column(options):
        for index, header in enumerate(headers):
            if header in options:
                return index
        return None

    usn_col = find_column(aliases["usn"])
    name_col = find_column(aliases["name"])

    if usn_col is None or name_col is None:
        raise ValueError("File must contain USN and Student Name columns")

    if len(rows) - 1 > MAX_STUDENTS:
        raise ValueError("Maximum 1000 student rows per upload")

    valid = []
    errors = []
    seen = set()

    for row_number, row in enumerate(rows[1:], start=2):
        if not any(value is not None and str(value).strip() for value in row):
            continue

        def cell(index):
            return (
                str(row[index]).strip()
                if index < len(row) and row[index] is not None
                else ""
            )

        usn = cell(usn_col).upper()
        name = cell(name_col)

        if not usn:
            errors.append({
                "row": row_number,
                "usn": "",
                "reason": "Missing USN",
            })
        elif not name:
            errors.append({
                "row": row_number,
                "usn": usn,
                "reason": "Missing student name",
            })
        elif usn in seen:
            errors.append({
                "row": row_number,
                "usn": usn,
                "reason": "Duplicate USN in file",
            })
        else:
            seen.add(usn)
            valid.append({
                "row": row_number,
                "usn": usn,
                "name": name,
            })

    return {
        "total_rows": len(valid) + len(errors),
        "valid": valid,
        "errors": errors,
    }
