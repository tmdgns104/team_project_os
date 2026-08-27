from pathlib import Path

p = Path('scripts/upgrade_live_draft_v010.py')
s = p.read_text(encoding='utf-8')
start = s.index("answer_old = '''")
end = s.index("\nargs_marker =", start)
replacement = r'''answer_start = s.index('        answer = result.stdout.strip()')
answer_end = s.index('\n\n\ninteractive_create =', answer_start)
answer_new = r'''        answer, live_delta = extract_live_delta(result.stdout)
        if not answer:
            messages.pop()
            print("\nAI 응답이 비어 있습니다.")
            continue
        messages.append({"role": "assistant", "content": answer})
        if live_delta:
            live_state = merge_live_state(live_state, live_delta)
            if draft_project:
                try:
                    synced = sync_live_draft(args.server, args.access_key, draft_project["id"], args.member, live_state)
                    draft_project = synced.get("project") or draft_project
                    print(f"\n[Live Draft] 웹 자동 업데이트 · Project #{draft_project['id']}")
                except Exception as exc:
                    print(f"\n[Live Draft] 동기화 실패: {exc}")
        save_session(session_file, provider=provider, member=args.member, messages=messages, autofill_mode=autofill_mode, draft_project=draft_project, live_state=live_state)
        print(f"\n{provider}> {answer}")
'''
s = s[:answer_start] + answer_new + s[answer_end:]
'''
s = s[:start] + replacement + s[end:]
p.write_text(s, encoding='utf-8')
print('upgrade patch made resilient with raw generated source')
