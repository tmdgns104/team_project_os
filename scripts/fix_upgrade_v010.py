from pathlib import Path

p = Path('scripts/upgrade_live_draft_v010.py')
s = p.read_text(encoding='utf-8')

# Preserve backslash escapes when the upgrade script generates Python source.
s = s.replace("answer_new = '''        answer, live_delta", "answer_new = r'''        answer, live_delta", 1)

# The generated project_cli source uses an f-string; literal JSON braces must be doubled.
s = s.replace(
    '<PROJECT_OS_DELTA>{"project_updates":{},"requirements":[],"decisions":[],"document_updates":[],"design_updates":[],"pending":[]}</PROJECT_OS_DELTA>',
    '<PROJECT_OS_DELTA>{{"project_updates":{{}},"requirements":[],"decisions":[],"document_updates":[],"design_updates":[],"pending":[]}}</PROJECT_OS_DELTA>',
    1,
)

old = "if answer_old not in s:\n    raise RuntimeError('answer handling marker not found')\ns = s.replace(answer_old, answer_new, 1)"
new = "if answer_old in s:\n    s = s.replace(answer_old, answer_new, 1)\nelse:\n    answer_start = s.index('        answer = result.stdout.strip()')\n    answer_end = s.index('\\n\\n\\ninteractive_create =', answer_start)\n    s = s[:answer_start] + answer_new + s[answer_end:]"
if old not in s:
    raise RuntimeError('upgrade answer replacement block not found')
s = s.replace(old, new, 1)

p.write_text(s, encoding='utf-8')
print('upgrade patch repaired')
