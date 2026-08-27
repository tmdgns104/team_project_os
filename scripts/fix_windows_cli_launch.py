from pathlib import Path

p = Path('local_bridge/bridge.py')
s = p.read_text(encoding='utf-8')

if 'import shutil\n' not in s:
    s = s.replace('import platform\n', 'import platform\nimport shutil\n', 1)

marker = '''def save_config(data: dict) -> None:\n    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")\n\n\n'''
helper = '''def save_config(data: dict) -> None:\n    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")\n\n\ndef prepare_local_command(cmd: list[str]) -> list[str]:\n    \"\"\"Resolve local CLI executables and make Windows .cmd/.bat launch reliable.\"\"\"\n    if not cmd:\n        raise RuntimeError("Empty local command")\n    executable = cmd[0]\n    resolved = executable if Path(executable).is_file() else shutil.which(executable)\n    if not resolved:\n        raise RuntimeError(\n            f"Local CLI not found: {executable}. "\n            f"Run 'python local_bridge/bridge.py doctor' and 'where {executable}' on Windows, "\n            "or register again with --command using the full executable path."\n        )\n    resolved_cmd = [resolved, *cmd[1:]]\n    if platform.system() == "Windows" and Path(resolved).suffix.lower() in {".cmd", ".bat"}:\n        comspec = os.environ.get("COMSPEC") or shutil.which("cmd.exe") or "cmd.exe"\n        return [comspec, "/d", "/s", "/c", subprocess.list2cmdline(resolved_cmd)]\n    return resolved_cmd\n\n\n'''
if 'def prepare_local_command(' not in s:
    if marker not in s:
        raise RuntimeError('save_config marker not found')
    s = s.replace(marker, helper, 1)

if 'import os\n' not in s:
    s = s.replace('import json\n', 'import json\nimport os\n', 1)

old = '        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60 * 45)\n'
new = '        launch_cmd = prepare_local_command(cmd)\n        result = subprocess.run(launch_cmd, cwd=cwd, capture_output=True, text=True, timeout=60 * 45)\n'
if old in s:
    s = s.replace(old, new, 1)

old2 = '        result = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=60 * 45)\n'
new2 = '        launch_cmd = prepare_local_command(cmd)\n        result = subprocess.run(launch_cmd, cwd=repo, capture_output=True, text=True, timeout=60 * 45)\n'
if old2 in s:
    s = s.replace(old2, new2, 1)

old_doctor = '''    for name, cmd in [("Codex", ["codex", "--version"]), ("Claude Code", ["claude", "--version"]), ("OpenCode", ["opencode", "--version"]), ("Antigravity CLI", ["agy", "--version"])]:\n        try:\n            p = subprocess.run(cmd, capture_output=True, text=True, timeout=8)\n            text = (p.stdout or p.stderr).strip().splitlines()\n            print(f"{name}: {'OK' if p.returncode == 0 else 'ERROR'} {text[0] if text else ''}")\n        except Exception:\n            print(f"{name}: not detected")\n'''
new_doctor = '''    for name, cmd in [("Codex", ["codex", "--version"]), ("Claude Code", ["claude", "--version"]), ("OpenCode", ["opencode", "--version"]), ("Antigravity CLI", ["agy", "--version"])]:\n        try:\n            launch_cmd = prepare_local_command(cmd)\n            p = subprocess.run(launch_cmd, capture_output=True, text=True, timeout=8)\n            text = (p.stdout or p.stderr).strip().splitlines()\n            resolved = shutil.which(cmd[0]) or cmd[0]\n            print(f"{name}: {'OK' if p.returncode == 0 else 'ERROR'} {text[0] if text else ''} [{resolved}]")\n        except Exception as exc:\n            print(f"{name}: not detected ({exc})")\n'''
if old_doctor in s:
    s = s.replace(old_doctor, new_doctor, 1)

p.write_text(s, encoding='utf-8')

# Regression coverage
tp = Path('tests/test_bridge.py')
t = tp.read_text(encoding='utf-8')
if 'prepare_local_command' not in t:
    t = t.replace('from local_bridge.bridge import provider_command\n', 'from local_bridge.bridge import prepare_local_command, provider_command\n', 1)
if 'test_prepare_local_command_reports_missing_cli' not in t:
    insert = '''    def test_prepare_local_command_reports_missing_cli(self):\n        with self.assertRaisesRegex(RuntimeError, "Local CLI not found"):\n            prepare_local_command(["definitely-not-a-real-project-os-cli-xyz", "--version"])\n\n'''
    t = t.replace('    def test_antigravity_headless_command(self):\n', insert + '    def test_antigravity_headless_command(self):\n', 1)
tp.write_text(t, encoding='utf-8')
