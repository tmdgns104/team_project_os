from pathlib import Path

p = Path('local_bridge/project_cli.py')
s = p.read_text(encoding='utf-8')

s = s.replace(
'''WELCOME = (\n    "AI Design Session을 시작합니다. 아직 Project OS 프로젝트는 생성되지 않습니다.\\n"\n    "막연한 아이디어부터 AI와 충분히 대화해서 구체화하세요.\\n"\n    "명령: /status 세션 상태, /preview 프로젝트 미리보기, /apply 정식 생성, /quit 종료"\n)''',
'''WELCOME = (\n    "AI Design Session을 시작합니다. 아직 Project OS 프로젝트는 생성되지 않습니다.\\n"\n    "막연한 아이디어부터 AI와 충분히 대화해서 구체화하세요.\\n"\n    "모르겠는 세부사항은 '알아서 임시로 정해줘'라고 하면 Autofill Mode로 채울 수 있습니다.\\n"\n    "명령: /status, /autofill on|off, /preview, /apply, /quit"\n)'''
)

old = '''def build_design_chat_prompt(messages: list[dict]) -> str:\n    transcript = "\\n\\n".join(\n        f"{'USER' if m['role'] == 'user' else 'ASSISTANT'}:\\n{m['content']}"\n        for m in messages\n    )\n    return f"""You are the user's project design partner inside Team Project OS.\n'''
new = '''def _requests_autofill(text: str) -> bool:\n    compact = "".join(str(text or "").lower().split())\n    phrases = (\n        "알아서해줘", "알아서정해", "알아서임시", "임시로다정", "임시로정해",\n        "네가정해", "너가정해", "적당히정해", "세부적인건알아서", "세부사항은알아서",\n        "알아서채워", "맡길게", "autofill",\n    )\n    return any(phrase in compact for phrase in phrases)\n\n\ndef build_design_chat_prompt(messages: list[dict], autofill_mode: bool = False) -> str:\n    transcript = "\\n\\n".join(\n        f"{'USER' if m['role'] == 'user' else 'ASSISTANT'}:\\n{m['content']}"\n        for m in messages\n    )\n    mode_rules = (\n        "AUTOFILL MODE IS ON. When the user does not know a low-risk implementation detail, "\n        "choose a sensible reversible default instead of repeatedly asking. Clearly call it an 'AI 임시 결정' "\n        "and briefly explain why. Never treat it as user-confirmed. Still ask before irreversible/high-impact choices "\n        "such as real spending, purchases, credentials/permissions, personal data policy, legal/regulatory commitments, "\n        "or external production changes."\n        if autofill_mode else\n        "AUTOFILL MODE IS OFF. Recommend options, but do not choose unknown details for the user unless the user explicitly delegates that choice."\n    )\n    return f"""You are the user's project design partner inside Team Project OS.\n'''
if old not in s:
    raise RuntimeError('chat prompt marker not found')
s = s.replace(old, new, 1)

s = s.replace(
'''- Never silently turn an unknown budget, deadline, KPI, technology, device, protocol, policy, or requirement into a confirmed fact.\n- If the project is too large, proactively suggest a smaller V1.''',
'''- Never silently turn an unknown item into a USER-confirmed fact.\n- {mode_rules}\n- If the project is too large, proactively suggest a smaller V1.''',
1,
)

s = s.replace(
'''def build_distiller_prompt(messages: list[dict]) -> str:\n    transcript = "\\n\\n".join(''',
'''def build_distiller_prompt(messages: list[dict], autofill_mode: bool = False) -> str:\n    transcript = "\\n\\n".join(''',
1,
)

needle = '''    )\n    return f"""You are the Project Distiller for Team Project OS.\nThe user has finished or paused a free-form project design conversation with an AI.\n'''
replacement = '''    )\n    autofill_rules = (\n        "AUTOFILL MODE IS ON. Fill unresolved LOW-RISK, REVERSIBLE design/implementation details with practical V1 defaults. "\n        "Every such AI-selected value MUST also create a decision with status='provisional', and the body must state why it was chosen and when it should be revisited. "\n        "Examples: local DB choice, web framework, basic screen set, folder/module split, simulator-first approach, development order, local deployment. "\n        "Do NOT autofill real spending/purchases, secrets or permission expansion, personal-data/legal/regulatory policy, contractual commitments, destructive production actions, or safety-critical thresholds; keep those in pending."\n        if autofill_mode else\n        "AUTOFILL MODE IS OFF. Do not fill unresolved facts unless the transcript contains an explicit user decision."\n    )\n    return f"""You are the Project Distiller for Team Project OS.\nThe user has finished or paused a free-form project design conversation with an AI.\n'''
if needle not in s:
    raise RuntimeError('distiller intro marker not found')
s = s.replace(needle, replacement, 1)

s = s.replace(
'''- Do not invent budget, deadline, KPI target values, users, hardware, protocols, databases, cloud providers, policies, or requirements.\n- Unknown or unresolved facts go into pending.''',
'''- Never label AI-selected defaults as user-confirmed.\n- {autofill_rules}\n- Unknown or unresolved items that are not safely autofilled go into pending.''',
1,
)

s = s.replace(
'''- Decisions should contain only confirmed decisions. Unaccepted alternatives belong in pending, not decisions.\n- Create process/architecture/dataflow only when supported by the conversation. Do not fabricate missing components.''',
'''- Decisions may contain USER-confirmed decisions with status='accepted' and AI-filled reversible defaults with status='provisional'.\n- Provisional decisions are allowed to support a complete V1 process/architecture/dataflow when Autofill Mode is on.\n- Create process/architecture/dataflow from confirmed facts plus clearly provisional defaults; do not hide which choices are provisional.''',
1,
)

s = s.replace(
'''    {{"title":"...","body":"...","status":"accepted"}}''',
'''    {{"title":"...","body":"...","status":"accepted|provisional"}}''',
1,
)

s = s.replace(
'''    custom_command: str | None = None,\n) -> tuple[dict, dict]:''',
'''    custom_command: str | None = None,\n    autofill_mode: bool = False,\n) -> tuple[dict, dict]:''',
1,
)
s = s.replace('''        build_distiller_prompt(messages),''', '''        build_distiller_prompt(messages, autofill_mode=autofill_mode),''', 1)

old_preview = '''    lines = [\n        "",\n        "=" * 62,\n        "Project OS 생성 미리보기",\n        "=" * 62,\n        f"프로젝트: {brief.get('name') or '(이름 미정)'}",\n        f"목표: {brief.get('goal') or '(목표 미정)'}",\n        f"유형: {brief.get('project_type') or 'generic'}",\n        f"정의 품질: {quality['score']}/100 ({quality['level']})",\n        f"요구사항: {len(pending.get('requirements', []))}개",\n        f"확정 Decision: {len(pending.get('decisions', []))}개",\n        f"문서 업데이트: {len(pending.get('document_updates', []))}개",\n        f"Canvas 설계: {len(pending.get('design_updates', []))}개",\n    ]'''
new_preview = '''    decisions = pending.get("decisions", [])\n    accepted_count = sum(1 for d in decisions if str(d.get("status", "")).lower() in {"accepted", "confirmed"})\n    provisional = [d for d in decisions if str(d.get("status", "")).lower() == "provisional"]\n    lines = [\n        "",\n        "=" * 62,\n        "Project OS 생성 미리보기",\n        "=" * 62,\n        f"프로젝트: {brief.get('name') or '(이름 미정)'}",\n        f"목표: {brief.get('goal') or '(목표 미정)'}",\n        f"유형: {brief.get('project_type') or 'generic'}",\n        f"정의 품질: {quality['score']}/100 ({quality['level']})",\n        f"요구사항: {len(pending.get('requirements', []))}개",\n        f"사람 확정 Decision: {accepted_count}개",\n        f"AI 임시 Decision: {len(provisional)}개",\n        f"문서 업데이트: {len(pending.get('document_updates', []))}개",\n        f"Canvas 설계: {len(pending.get('design_updates', []))}개",\n    ]\n    if provisional:\n        lines.append("AI 임시 결정(PROVISIONAL):")\n        lines.extend(f"  - {item.get('title', '')}: {item.get('body', '')}" for item in provisional[:12])'''
if old_preview not in s:
    raise RuntimeError('preview marker not found')
s = s.replace(old_preview, new_preview, 1)

s = s.replace(
'''def save_session(path: Path, *, provider: str, member: str, messages: list[dict], applied_project: dict | None = None) -> None:''',
'''def save_session(path: Path, *, provider: str, member: str, messages: list[dict], applied_project: dict | None = None, autofill_mode: bool = False) -> None:''',
1,
)
s = s.replace(
'''        "applied_project": applied_project,\n        "updated_at": datetime.now().isoformat(timespec="seconds"),''',
'''        "applied_project": applied_project,\n        "autofill_mode": autofill_mode,\n        "updated_at": datetime.now().isoformat(timespec="seconds"),''',
1,
)

s = s.replace(
'''def print_session_status(path: Path, provider: str, messages: list[dict]) -> None:''',
'''def print_session_status(path: Path, provider: str, messages: list[dict], autofill_mode: bool = False) -> None:''',
1,
)
s = s.replace(
'''    print(f"세션 저장: {path}")\n    print("/preview 또는 /apply 시점에만 전체 대화를 프로젝트 구조로 변환합니다.")''',
'''    print(f"세션 저장: {path}")\n    print(f"Autofill Mode: {'ON - 모르는 저위험 세부사항은 AI 임시 결정' if autofill_mode else 'OFF'}")\n    print("/preview 또는 /apply 시점에만 전체 대화를 프로젝트 구조로 변환합니다.")''',
1,
)

s = s.replace(
'''    preview_cache: tuple[int, dict, dict] | None = None\n\n    print(WELCOME)''',
'''    preview_cache: tuple[int, dict, dict] | None = None\n    autofill_mode = bool(getattr(args, "autofill", False))\n\n    print(WELCOME)''',
1,
)
s = s.replace(
'''    print(f"AI: {provider} / 세션: {session_file}")''',
'''    print(f"AI: {provider} / 세션: {session_file}")\n    if autofill_mode:\n        print("Autofill Mode: ON (AI 임시 결정 허용)")''',
1,
)

# Save-session calls inside interactive flow.
s = s.replace(
'''save_session(session_file, provider=provider, member=args.member, messages=messages)''',
'''save_session(session_file, provider=provider, member=args.member, messages=messages, autofill_mode=autofill_mode)'''
)
s = s.replace(
'''                applied_project=project,\n            )''',
'''                applied_project=project,\n                autofill_mode=autofill_mode,\n            )''',
1,
)

s = s.replace(
'''        if command == "/status":\n            print_session_status(session_file, provider, messages)\n            continue\n        if command in {"/preview", "/apply"}:''',
'''        if command == "/status":\n            print_session_status(session_file, provider, messages, autofill_mode)\n            continue\n        if command.startswith("/autofill"):\n            parts = command.split()\n            if len(parts) == 1:\n                print(f"Autofill Mode: {'ON' if autofill_mode else 'OFF'}")\n            elif parts[1] in {"on", "1", "true"}:\n                autofill_mode = True\n                preview_cache = None\n                print("Autofill Mode ON: 모르는 저위험 세부사항은 AI가 PROVISIONAL로 임시 결정합니다.")\n            elif parts[1] in {"off", "0", "false"}:\n                autofill_mode = False\n                preview_cache = None\n                print("Autofill Mode OFF: 모르는 사항은 다시 질문하거나 TBD로 남깁니다.")\n            else:\n                print("사용법: /autofill on 또는 /autofill off")\n            continue\n        if command in {"/preview", "/apply"}:''',
1,
)

s = s.replace(
'''                        custom_command=args.command or None,\n                    )''',
'''                        custom_command=args.command or None,\n                        autofill_mode=autofill_mode,\n                    )''',
1,
)

s = s.replace(
'''        messages.append({"role": "user", "content": user_text})\n        preview_cache = None''',
'''        if _requests_autofill(user_text) and not autofill_mode:\n            autofill_mode = True\n            print("Autofill Mode ON: '알아서/임시로 정해줘' 요청을 감지했습니다.")\n        messages.append({"role": "user", "content": user_text})\n        preview_cache = None''',
1,
)
s = s.replace(
'''                build_design_chat_prompt(messages),''',
'''                build_design_chat_prompt(messages, autofill_mode=autofill_mode),''',
1,
)

s = s.replace(
'''    parser.add_argument("--session-file", default="", help="Design Session 저장 파일 경로")''',
'''    parser.add_argument("--session-file", default="", help="Design Session 저장 파일 경로")\n    parser.add_argument("--autofill", action="store_true", help="모르는 저위험 세부사항을 AI가 PROVISIONAL로 임시 결정")''',
1,
)

p.write_text(s, encoding='utf-8')

# project_os.py wrapper
p = Path('project_os.py')
s = p.read_text(encoding='utf-8')
s = s.replace(
'''    parser.add_argument("--session-file", default="")''',
'''    parser.add_argument("--session-file", default="")\n    parser.add_argument("--autofill", action="store_true")''',
1,
)
s = s.replace(
'''    if args.session_file:\n        cli_args += ["--session-file", args.session_file]\n    return project_cli_main(cli_args)''',
'''    if args.session_file:\n        cli_args += ["--session-file", args.session_file]\n    if args.autofill:\n        cli_args += ["--autofill"]\n    return project_cli_main(cli_args)''',
1,
)
p.write_text(s, encoding='utf-8')
