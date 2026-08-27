from pathlib import Path

p = Path('local_bridge/bridge.py')
s = p.read_text(encoding='utf-8')

s = s.replace('''    if provider == "codex":\n        return ["codex", "exec", prompt]\n''', '''    if provider == "codex":\n        # Use Codex's explicit stdin sentinel so long/multiline prompts are not\n        # re-tokenized by Windows cmd.exe or npm .cmd wrappers.\n        return ["codex", "exec", "-"]\n''', 1)

old = '''    provider = cfg["assistant_provider"]\n    cmd = provider_command(provider, prompt, custom_command or cfg.get("assistant_command") or None)\n    print(f"Claimed Project Assistant Job #{job['id']} / {provider}")\n    try:\n        launch_cmd = prepare_local_command(cmd)\n        result = subprocess.run(launch_cmd, cwd=cwd, capture_output=True, text=True, timeout=60 * 45)\n'''
new = '''    provider = cfg["assistant_provider"]\n    custom = custom_command or cfg.get("assistant_command") or None\n    cmd = provider_command(provider, prompt, custom)\n    stdin_text = prompt if provider == "codex" and not custom else None\n    print(f"Claimed Project Assistant Job #{job['id']} / {provider}")\n    try:\n        launch_cmd = prepare_local_command(cmd)\n        result = subprocess.run(launch_cmd, cwd=cwd, capture_output=True, text=True, input=stdin_text, timeout=60 * 45)\n'''
if old not in s:
    raise RuntimeError('assistant run marker not found')
s = s.replace(old, new, 1)

old = '''    provider = cfg["provider"]\n    cmd = provider_command(provider, prompt, custom_command or cfg.get("command") or None)\n    print(f"Claimed AI Job #{job['id']} / Task #{job['task_id']} / {provider}")\n    print(f"Repository: {repo}")\n    try:\n        launch_cmd = prepare_local_command(cmd)\n        result = subprocess.run(launch_cmd, cwd=repo, capture_output=True, text=True, timeout=60 * 45)\n'''
new = '''    provider = cfg["provider"]\n    custom = custom_command or cfg.get("command") or None\n    cmd = provider_command(provider, prompt, custom)\n    stdin_text = prompt if provider == "codex" and not custom else None\n    print(f"Claimed AI Job #{job['id']} / Task #{job['task_id']} / {provider}")\n    print(f"Repository: {repo}")\n    try:\n        launch_cmd = prepare_local_command(cmd)\n        result = subprocess.run(launch_cmd, cwd=repo, capture_output=True, text=True, input=stdin_text, timeout=60 * 45)\n'''
if old not in s:
    raise RuntimeError('task run marker not found')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# Regression tests
tp = Path('tests/test_bridge.py')
t = tp.read_text(encoding='utf-8')
if 'test_codex_uses_stdin_sentinel' not in t:
    marker = '    def test_antigravity_headless_command(self):\n'
    addition = '''    def test_codex_uses_stdin_sentinel(self):\n        cmd = provider_command("codex", "a prompt with many words")\n        self.assertEqual(cmd, ["codex", "exec", "-"])\n\n'''
    if marker not in t:
        raise RuntimeError('bridge test marker not found')
    t = t.replace(marker, addition + marker, 1)
tp.write_text(t, encoding='utf-8')
