"""Agent tools owned by Aparna (docs/api-contract.md section 11).

These are plain functions called by the agent loop.  The caller (the chat
handler) must inject:
  * ``current_user`` – the authenticated user dict coming from the server
    session (never from tool arguments).  It has keys: ``user_id``,
    ``role``, ``student_id``, ``usn``.
  * ``store`` / ``conn`` – a data store (for analytics) or a SQLAlchemy
    connection (for writes).

Access-control rule: the **current user and role come from the server
session**.  Tool arguments never carry a user id or role.  When a student
passes a USN argument, it must be their own – any other USN raises a
403-style ``AppError``.

Every argument is validated with a pydantic model defined in this module.

CO math uses the existing ``engine/co_math.py`` – no LLM ever touches a score.

The ``ai.quiz_generation.generate_quiz`` function (owned by Danwin) makes the
LLM call; this module only validates, persists, and enforces access control.
"""
from __future__ import annotations

import json
import os
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .errors import AppError
from .pg.chunks import module_chunks_with_co, subject_cos
from .pg.common import as_uuid
from .services.question_draft_review import suspect_deck
from .engine.co_math import AttemptScore, COConfig, StudentInfo
from .services.co_analytics import (
    AnalyticsStore,
    get_class_summary_data,
    get_weak_cos_data,
    get_student_progress_data,
    export_co_sheet_excel,
)
from .services.quizzes import ForbiddenError, NotFoundError  # noqa: F401 (re-exported for callers)

# Danwin's generation function and client
from ai.quiz_generation import generate_quiz as _ai_generate_quiz, QuizGenerationError
from ai.token_factory import TokenFactoryClient
from sqlalchemy import text



# ---------------------------------------------------------------------------
# Argument validation helpers
# ---------------------------------------------------------------------------

def _require_env(key: str) -> str:
    """Read a required env var, raising AppError if missing (no stack trace)."""
    val = os.getenv(key)
    if not val or not val.strip():
        raise AppError(500, "CONFIGURATION_ERROR",
                       f"Server is not configured for AI generation (missing {key}).")
    return val


# ---------------------------------------------------------------------------
# Pydantic argument schemas
# ---------------------------------------------------------------------------

class GetCOAttainmentArgs(BaseModel):
    """Arguments for get_co_attainment."""

    subject_id: str = Field(..., description="UUID of the subject")
    section: str | None = Field(default=None, description="Optional section filter")


class FindWeakCOsArgs(BaseModel):
    """Arguments for find_weak_COs."""

    subject_id: str = Field(..., description="UUID of the subject")
    section: str | None = Field(default=None, description="Optional section filter")


class GetStudentProgressArgs(BaseModel):
    """Arguments for get_student_progress."""

    subject_id: str = Field(..., description="UUID of the subject")
    usn: str | None = Field(default=None, description="USN to look up – students may only use their own")


class ExportSheetArgs(BaseModel):
    """Arguments for export_sheet."""

    subject_id: str = Field(..., description="UUID of the subject")
    scope: str | None = Field(default="semester", description="semester or module")
    module_id: str | None = Field(default=None, description="Required when scope='module'")


class GenerateQuizArgs(BaseModel):
    """Arguments for generate_quiz."""

    model_config = ConfigDict(extra="forbid")

    module_id: str = Field(min_length=1, description="UUID of the module")
    difficulty: Literal["easy", "medium", "hard"]
    count: int = Field(strict=True, ge=1, le=20, description="Number of questions to generate")


# ---------------------------------------------------------------------------
# Tool: get_co_attainment
# ---------------------------------------------------------------------------

def get_co_attainment(
    args: GetCOAttainmentArgs,
    current_user: dict[str, Any],
    store: AnalyticsStore,
) -> list[dict[str, Any]]:
    """Return class-level CO attainment summary for a subject.

    Faculty only.  Wraps ``co_analytics.get_class_summary_data`` which uses
    ``engine/co_math.class_summary`` – pure numeric, no LLM.
    """
    if current_user.get("role") != "faculty":
        raise AppError(403, "FORBIDDEN", "Only faculty can view CO attainment data.")

    return get_class_summary_data(store, subject_id=args.subject_id,
                                  section=args.section)


# ---------------------------------------------------------------------------
# Tool: find_weak_COs
# ---------------------------------------------------------------------------

def find_weak_COs(
    args: FindWeakCOsArgs,
    current_user: dict[str, Any],
    store: AnalyticsStore,
) -> list[dict[str, Any]]:
    """Return COs whose class attainment fell below target.

    Faculty only.  Wraps ``co_analytics.get_weak_cos_data`` which uses
    ``engine/co_math.weak_cos`` – pure numeric, no LLM.
    """
    if current_user.get("role") != "faculty":
        raise AppError(403, "FORBIDDEN", "Only faculty can view weak COs.")

    return get_weak_cos_data(store, subject_id=args.subject_id,
                             section=args.section)


# ---------------------------------------------------------------------------
# Tool: get_student_progress
# ---------------------------------------------------------------------------

def get_student_progress(
    args: GetStudentProgressArgs,
    current_user: dict[str, Any],
    store: AnalyticsStore,
) -> dict[str, Any]:
    """Return one student's CO progress for a subject.

    Faculty may look up any student.  A student may only look up their own
    USN – any other USN raises a 403-style AppError before the store is
    touched.
    """
    role = current_user.get("role")

    if role == "student":
        caller_usn = (current_user.get("usn") or "").strip().upper()
        target_usn = (args.usn or "").strip().upper()

        if target_usn and target_usn != caller_usn:
            raise AppError(403, "FORBIDDEN",
                           f"Students can only view their own progress (USN {caller_usn}).")

        resolved_usn = caller_usn
    else:
        resolved_usn = (args.usn or "").strip().upper()
        if not resolved_usn:
            raise AppError(400, "BAD_REQUEST",
                           "Faculty must specify a USN when viewing student progress.")

    # Delegate to the analytics service which also enforces the rule as
    # defence-in-depth.
    return get_student_progress_data(
        store,
        current_user=current_user,
        usn=resolved_usn,
        subject_id=args.subject_id,
    )


# ---------------------------------------------------------------------------
# Tool: export_sheet
# ---------------------------------------------------------------------------

def export_sheet(
    args: ExportSheetArgs,
    current_user: dict[str, Any],
    store: AnalyticsStore,
) -> bytes:
    """Return Excel bytes of the CO sheet for a subject.

    Faculty only.  Wraps ``co_analytics.export_co_sheet_excel``.
    """
    if current_user.get("role") != "faculty":
        raise AppError(403, "FORBIDDEN", "Only faculty can export the CO sheet.")

    return export_co_sheet_excel(
        store,
        subject_id=args.subject_id,
        scope=args.scope or "semester",
        module_id=args.module_id,
    )


# ---------------------------------------------------------------------------
# Tool: generate_quiz
# ---------------------------------------------------------------------------

def _usage_recorder(conn: Any, faculty_user_id: str | None, role: str | None):
    """Return a callable that logs token usage to the agent_logs table."""
    def record(usage: dict[str, Any]) -> None:
        conn.execute(
            text(
                "INSERT INTO agent_logs "
                "(user_id, role, kind, step, model, "
                "prompt_tokens, completion_tokens, total_tokens, args) "
                "VALUES "
                "(:uid, :role, 'tool_call', :step, :model, "
                ":pt, :ct, :tt, :args)"
            ),
            {
                "uid": faculty_user_id,
                "role": role,
                "step": usage.get("step", "quiz_generation"),
                "model": usage.get("model"),
                "pt": usage.get("prompt_tokens"),
                "ct": usage.get("completion_tokens"),
                "tt": usage.get("total_tokens"),
                "args": json.dumps({}),
            },
        )
    return record


def generate_quiz(
    args: GenerateQuizArgs,
    current_user: dict[str, Any],
    conn: Any,
) -> list[str]:
    """Generate AI questions from a faculty-owned module and save them as drafts.

    Faculty only. Reads the module's slides and subject's CO definitions, builds a
    TokenFactoryClient from env vars, and calls Danwin's
    ``ai.quiz_generation.generate_quiz``.  Generated questions are
    inserted with ``status='draft'`` and ``source='AI'`` so they will NOT
    pass the approval trigger until a faculty member approves them.

    ``QuizGenerationError`` and missing env vars are mapped to clean
    ``AppError`` responses with no stack trace leaked to the user.

    The DB layer uses SQLAlchemy Core with raw ``text()`` queries.
    """
    if current_user.get("role") != "faculty":
        raise AppError(403, "FORBIDDEN",
                       "Only faculty can generate quiz questions.")

    faculty_user_id = current_user["user_id"]

    module = conn.execute(
        text("SELECT m.id, m.title, m.subject_id, m.processing_status, s.name AS subject_name, "
             "s.code AS subject_code FROM modules m JOIN subjects s ON s.id = m.subject_id "
             "WHERE m.id = :mid AND s.faculty_user_id = :fid"),
        {"mid": as_uuid(args.module_id, "Module"), "fid": faculty_user_id},
    ).mappings().fetchone()
    if module is None:
        raise AppError(404, "NOT_FOUND", "Module not found")
    module_id = str(module["id"])
    if module["processing_status"] != "done":
        raise AppError(422, "NO_PROCESSED_CONTENT", "Process the module's PPTX before generating questions.")

    slides = [
        {"slide_number": chunk["slide_number"], "text": chunk["text"]}
        for chunk in module_chunks_with_co(conn, module_id) if chunk["text"].strip()
    ]
    if not slides:
        raise AppError(422, "NO_PROCESSED_CONTENT", "The module has no extracted slide text to generate questions from.")
    if suspect_deck(module["title"], module["subject_name"], slides):
        raise AppError(409, "MODULE_CONTENT_MISMATCH",
                       "The slides may belong to a different module. Check them in the faculty review form.")
    outcomes = subject_cos(conn, str(module["subject_id"]))

    # Read configuration from env, mapping missing values to clean errors
    api_key = _require_env("TOKEN_FACTORY_API_KEY")
    base_url = _require_env("TOKEN_FACTORY_BASE_URL")
    model = _require_env("MODEL_GENERATION")

    # Build the Token Factory client
    try:
        client = TokenFactoryClient(api_key=api_key, base_url=base_url)
    except ValueError as exc:
        raise AppError(500, "CONFIGURATION_ERROR",
                       "Token Factory client is misconfigured.") from exc

    # Call Danwin's generation function
    usage_recorder = _usage_recorder(
        conn, faculty_user_id, current_user.get("role")
    )
    try:
        generated = _ai_generate_quiz(
            module={"id": module_id, "title": module["title"], "slides": slides},
            course_outcomes=outcomes,
            difficulty=args.difficulty,
            count=args.count,
            client=client,
            model=model,
            usage_recorder=usage_recorder,
        )
    except QuizGenerationError as exc:
        raise AppError(502, "GENERATION_FAILED",
                       f"AI generation failed: {exc}") from exc
    except Exception as exc:
        raise AppError(502, "GENERATION_FAILED",
                       "AI generation service returned an error.") from exc
    finally:
        client.close()

    # Persist each generated question as a draft.  We hardcode status='draft'
    # and source='AI' in the SQL so no AI response can ever set them to
    # 'approved' or anything else.
    created_ids: list[str] = []
    for q in generated:
        result = conn.execute(
            text(
                "INSERT INTO questions "
                "(module_id, co_id, stem, options, correct_option, explanation, "
                "marks, difficulty, bloom_level, status, source, created_by, source_slide_number, source_quote) "
                "VALUES "
                "(:mid, :cid, :stem, CAST(:opts AS jsonb), :co, :expl, "
                ":marks, :diff, :bloom, 'draft', 'AI', :cb, :slide, :quote) "
                "RETURNING id"
            ),
            {
                "mid": module_id,
                "cid": q["co_id"],
                "slide": q["source_slide_number"],
                "quote": q["source_quote"],
                "stem": q["stem"],
                "opts": json.dumps(q["options"]),
                "co": q["correct_option"],
                "expl": q.get("explanation"),
                "marks": q.get("marks", 1.0),
                "diff": args.difficulty,
                "bloom": q.get("bloom_level") or "understand",
                "cb": faculty_user_id,
            },
        )
        created_ids.append(str(result.mappings().fetchone()["id"]))

    return created_ids
