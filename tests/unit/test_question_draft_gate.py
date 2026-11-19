"""Offline tests: exercise the real tool dispatch and HTTP route, never a provider or PG."""
import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from ai.agent import AgentLoop
from backend.app import agent_tools
from backend.app.services.agent_runtime import build_agent_tool_registry


@pytest.fixture
def deck(monkeypatch):
    # A fresh, memory-only connection; let the actual ownership query run.
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        mid, sid, uid = (str(uuid4()) for _ in range(3))
        conn.execute(text("CREATE TABLE subjects(id TEXT, name TEXT, code TEXT, faculty_user_id TEXT)"))
        conn.execute(text("CREATE TABLE modules(id TEXT, subject_id TEXT, title TEXT, processing_status TEXT)"))
        conn.execute(text("INSERT INTO subjects VALUES (:s, 'Database Management Systems', 'DBMS', :u)"), {"s": sid, "u": uid})
        conn.execute(text("INSERT INTO modules VALUES (:m, :s, 'Query Optimisation', 'done')"), {"m": mid, "s": sid})
        slides = [{"slide_number": 1, "text": "Software Testing: verification and validation"},
                  {"slide_number": 2, "text": "Regression testing, test cases and defect tracking"}]
        monkeypatch.setattr(agent_tools, "module_chunks_with_co", lambda *_: slides)
        monkeypatch.setattr(agent_tools, "subject_cos", lambda *_: [])
        client = Mock()
        monkeypatch.setattr(agent_tools, "TokenFactoryClient", client)
        monkeypatch.setattr(agent_tools, "_ai_generate_quiz", Mock(return_value=[]))
        for key in ("MODEL_GENERATION", "TOKEN_FACTORY_API_KEY", "TOKEN_FACTORY_BASE_URL"):
            monkeypatch.setenv(key, "test-only")
        yield SimpleNamespace(conn=conn, mid=mid, sid=sid, user={"role": "faculty", "user_id": uid},
                              slides=slides, client=client, options={"difficulty": "easy", "count": 1})
    engine.dispose()


def dispatch(deck, **extra):
    registry = build_agent_tool_registry(deck.conn)
    model = Mock()
    model.chat.side_effect = [SimpleNamespace(content=None, tool_calls=[{
        "id": "call1", "type": "function", "function": {"name": "generate_quiz", "arguments": json.dumps(
            {"module_id": deck.mid, **deck.options, **extra})}}]), SimpleNamespace(content="Finished", tool_calls=[])]
    result = AgentLoop(model, model="fake", tools=registry).run(deck.user, "Generate drafts")
    tool_result = next(m for m in result.history if m["role"] == "tool")
    return result, json.loads(tool_result["content"]), registry.get("generate_quiz").parameters


def test_agent_dispatch_refuses_mismatch_without_offering_a_token(deck):
    result, payload, schema = dispatch(deck)
    assert result.tool_calls == [{"name": "generate_quiz", "status": "error"}]
    assert not result.drafts
    assert payload["error"]["code"] == "MODULE_CONTENT_MISMATCH"
    assert "review form" in payload["error"]["message"].lower()
    assert set(payload["error"]) == {"code", "message"}
    assert set(schema["properties"]) == {"module_id", "difficulty", "count"}
    deck.client.assert_not_called()
