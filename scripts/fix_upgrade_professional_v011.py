from pathlib import Path

p = Path('scripts/upgrade_professional_documents_v011.py')
s = p.read_text(encoding='utf-8')
old = 'end = "]\\n\\n\\n\\n@contextmanager\\ndef db():\\n"'
new = 'end = "\\n\\n\\n\\n@contextmanager\\ndef db():\\n"'
if old not in s:
    raise RuntimeError('V0.11 template boundary marker not found')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
print('V0.11 upgrade boundary repaired')
