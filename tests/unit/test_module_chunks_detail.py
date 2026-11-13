from app.pg.chunks import module_chunks_detail


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def fetchall(self):
        return self._rows


class _Connection:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *_args, **_kwargs):
        return _Result(self.rows)


def test_module_chunks_detail_groups_multiple_course_outcomes():
    rows = [
        {
            "id": "chunk-1",
            "slide_number": 2,
            "text": "Relational algebra",
            "tag_status": "tagged",
            "co_number": 1,
            "confidence": 0.91,
        },
        {
            "id": "chunk-1",
            "slide_number": 2,
            "text": "Relational algebra",
            "tag_status": "tagged",
            "co_number": 3,
            "confidence": 0.82,
        },
        {
            "id": "chunk-2",
            "slide_number": 3,
            "text": "Unmatched excerpt",
            "tag_status": "untagged",
            "co_number": None,
            "confidence": None,
        },
    ]
    result = module_chunks_detail(
        _Connection(rows),
        "00000000-0000-0000-0000-000000000001",
    )

    assert len(result) == 2
    assert result[0]["slide_number"] == 2
    assert result[0]["course_outcomes"] == [
        {"co_number": 1, "confidence": 0.91},
        {"co_number": 3, "confidence": 0.82},
    ]
    assert result[1]["course_outcomes"] == []
    assert result[1]["tag_status"] == "untagged"
