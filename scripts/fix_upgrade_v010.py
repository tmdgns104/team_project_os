from pathlib import Path

p = Path('scripts/upgrade_live_draft_v010.py')
s = p.read_text(encoding='utf-8')
start = s.index("answer_old = '''")
end = s.index("\nargs_marker =", start)
replacement = '''answer_start = s.index('        answer = result.stdout.strip()')\nanswer_end = s.index('\\n\\n\\ninteractive_create =', answer_start)\nanswer_new = \'\'\'        answer, live_delta = extract_live_delta(result.stdout)\n        if not answer:\n            messages.pop()\n            print("\\nAI 응답이 비어 있습니다.")\n            continue\n        messages.append({"role": "assistant", "content": answer})\n        if live_delta:\n            live_state = merge_live_state(live_state, live_delta)\n            if draft_project:\n                try:\n                    synced = sync_live_draft(args.server, args.access_key, draft_project["id"], args.member, live_state)\n                    draft_project = synced.get("project") or draft_project\n                    print(f"\\n[Live Draft] 웹 자동 업데이트 · Project #{draft_project[\'id\']}")\n                except Exception as exc:\n                    print(f"\\n[Live Draft] 동기화 실패: {exc}")\n        save_session(session_file, provider=provider, member=args.member, messages=messages, autofill_mode=autofill_mode, draft_project=draft_project, live_state=live_state)\n        print(f"\\n{provider}> {answer}")\n\'\'\'\ns = s[:answer_start] + answer_new + s[answer_end:]\n'''
s = s[:start] + replacement + s[end:]
p.write_text(s, encoding='utf-8')
print('upgrade patch made resilient')
