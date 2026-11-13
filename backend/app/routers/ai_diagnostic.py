"""Temporary faculty-protected Nebius connectivity diagnostic."""

import logging
import os

from fastapi import APIRouter, Depends

from ..deps import require_faculty
from ..services.ai_glue import get_client

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/internal/ai-diagnostic", include_in_schema=False)
def test_ai_connection(
    _user: dict = Depends(require_faculty),
):
    model = (os.getenv("MODEL_TAGGING") or "").strip()

    if not model:
        return {"status": "not_configured"}

    try:
        client = get_client()

        if client is None:
            return {"status": "not_configured"}

        with client:
            result = client.chat(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": "Reply with exactly OK.",
                    }
                ],
                max_tokens=16,
            )

        return {
            "status": "connected",
            "response_received": bool(result.content),
        }

    except Exception:
        logger.exception("AI diagnostic failed")
        return {"status": "failed"}
