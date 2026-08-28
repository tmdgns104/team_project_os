from __future__ import annotations

import builtins

from app.live_state_v015 import sanitize_live_state_v015
from local_bridge import project_cli as base
from local_bridge import project_cli_v014 as v014

_ORIGINAL_EXTRACT = base.extract_live_delta
_ORIGINAL_DISTILL = base.build_distiller_prompt
_ORIGINAL_NORMALIZE = base.normalize_ai_result


def _extract(output: str):
    answer, delta = _ORIGINAL_EXTRACT(output)
    return answer, sanitize_live_state_v015(delta) if delta else {}


def _normalize(output: str):
    result = v014.professional_normalize(output)
    try:
        from app.conversation import extract_json_object
        raw = extract_json_object(output)
        safe = sanitize_live_state_v015(raw)
        for key, value in safe.items():
            if value:
                result[key] = value
    except Exception:
        pass
    return result


def _prompt(messages, autofill_mode=False):
    prompt = v014.professional_distiller_prompt(messages, autofill_mode=autofill_mode)
    extra = """
V0.15 STRUCTURED DELIVERABLE CATALOGS
When the transcript supports them, include these compact top-level arrays in the final JSON and Live Delta. Do not invent high-impact facts; reversible AI defaults must remain provisional.
- milestones: id, phase, task, start_week, end_week, owner, status, deliverable, exit_criteria, requirement_refs
- backlog_items: id, epic, title, detail, priority, estimate, owner, status, requirement_refs, dependencies, definition_of_ready, definition_of_done
- functions: id, name, actor, trigger, preconditions, inputs, business_rules, normal_flow, exception_flow, outputs, acceptance_criteria, requirement_refs
- screens: id, name, purpose, users, entry_conditions, components, actions, validation, states, api_refs, requirement_refs
- interfaces: id, kind, method, path, name, purpose, auth, request, response, errors, timeout_retry, idempotency, versioning, requirement_refs
- tests: id, requirement_refs, priority, preconditions, steps, expected, evidence, pass_fail, status
- policies: id, category, policy, target, monitoring, response, owner, status, requirement_refs
- data_items: id, name, source, producer, fields, validation, processing, destination, protocol, retention, failure_handling, requirement_refs
Use stable IDs so REQ → Design/Data/API → Backlog/Task → TC → Evidence remains traceable.
For System Process, Architecture, and Data Flow, emit complete graphs in design_updates whenever meaningfully changed.
"""
    marker = "\nTRANSCRIPT\n"
    return prompt.replace(marker, "\n" + extra.strip() + marker, 1) if marker in prompt else prompt + "\n" + extra


def main(argv=None) -> int:
    base.extract_live_delta = _extract
    base.normalize_ai_result = _normalize
    base.build_distiller_prompt = _prompt
    original_input = builtins.input
    builtins.input = v014._paste_aware_input(original_input)
    if "/paste" not in base.WELCOME:
        base.WELCOME = base.WELCOME.replace("명령: ", "명령: /paste(클립보드 여러 줄 입력), ")
    try:
        return base.main(argv)
    finally:
        builtins.input = original_input
        base.extract_live_delta = _ORIGINAL_EXTRACT
        base.normalize_ai_result = _ORIGINAL_NORMALIZE
        base.build_distiller_prompt = _ORIGINAL_DISTILL


if __name__ == "__main__":
    raise SystemExit(main())
