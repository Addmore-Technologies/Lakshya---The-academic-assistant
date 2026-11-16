"""Integration test for legacy PPT upload background processing."""

from unittest.mock import MagicMock

from backend.app.routers import upload


def test_legacy_ppt_reaches_pptx_pipeline(monkeypatch):
    converted = b"PK-converted-presentation"
    original = bytes.fromhex("D0CF11E0A1B11AE1") + b"legacy-data"

    engine = MagicMock()
    connection = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection

    monkeypatch.setattr(upload, "get_engine", lambda: engine)
    monkeypatch.setattr(
        upload, "convert_ppt_to_pptx", lambda data: converted
    )
    monkeypatch.setattr(
        upload, "PostgresChunkStore", lambda *args, **kwargs: MagicMock()
    )
    monkeypatch.setattr(upload, "UsageRecorder", lambda *args: MagicMock())
    monkeypatch.setattr(upload, "get_client", lambda: None)
    monkeypatch.setattr(upload, "make_tagger", lambda *args: MagicMock())
    monkeypatch.setattr(upload, "_co_infos", lambda *args: [])

    captured = {}

    def fake_pipeline(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(upload, "process_module_upload", fake_pipeline)

    upload.run_upload_pipeline(
        module_id="module-test",
        subject_id="subject-test",
        data=original,
        user={"user_id": "faculty-test", "role": "faculty"},
        document_type="ppt",
    )

    assert captured["document_type"] == "pptx"
    assert captured["source"].read() == converted
    connection.commit.assert_called_once()


def test_ppt_conversion_failure_marks_module_failed(monkeypatch):
    engine = MagicMock()
    connection = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection

    store = MagicMock()

    monkeypatch.setattr(upload, "get_engine", lambda: engine)
    monkeypatch.setattr(
        upload, "PostgresChunkStore", lambda *args, **kwargs: store
    )

    def fail_conversion(data):
        raise ValueError("Conversion failed")

    monkeypatch.setattr(upload, "convert_ppt_to_pptx", fail_conversion)

    upload.run_upload_pipeline(
        module_id="module-test",
        subject_id="subject-test",
        data=b"invalid-ppt",
        user={"user_id": "faculty-test", "role": "faculty"},
        document_type="ppt",
    )

    connection.rollback.assert_called_once()
    store.set_module_status.assert_called_once()
    assert store.set_module_status.call_args.args[1] == "failed"
