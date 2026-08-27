from __future__ import annotations

from typing import Any

from app import main as base
from app.delivery_documents import DOCUMENT_ORDER, build_delivery_documents, build_requirements_register
from app.live_state import sanitize_live_state

# Keep the proven V0.13 API/DB implementation and replace only the document/live-state
# policy layer. Existing endpoint functions resolve these globals at call time.
base.app.version = "0.14.0"
base.build_initial_documents = build_delivery_documents

_BASE_DOCS = build_delivery_documents({})
base.DOCUMENT_TEMPLATES = [
    (doc_type, title, _BASE_DOCS[doc_type])
    for doc_type, title in DOCUMENT_ORDER
]

_original_build_live_draft_documents = base.build_live_draft_documents
_original_apply_live_draft_state = base.apply_live_draft_state


def build_live_draft_documents(brief: dict[str, Any], state: dict[str, Any]) -> dict[str, str]:
    safe_state = sanitize_live_state(state)
    docs = _original_build_live_draft_documents(brief, safe_state)
    # The base function already keeps all 13 docs and adds live graph snapshots.
    # Replace only the requirements register with the richer ISO-29148-inspired view.
    if safe_state.get("requirements"):
        docs["requirements"] = build_requirements_register(brief, safe_state["requirements"])
    return docs


def apply_live_draft_state(conn, project_id: int, member_name: str, state: dict[str, Any], *, lifecycle: str = "draft"):
    # A malformed AI delta must never poison all subsequent design turns.
    return _original_apply_live_draft_state(
        conn,
        project_id,
        member_name,
        sanitize_live_state(state),
        lifecycle=lifecycle,
    )


base.build_live_draft_documents = build_live_draft_documents
base.apply_live_draft_state = apply_live_draft_state

# Export the same FastAPI application with the V0.14 policy layer installed.
app = base.app
