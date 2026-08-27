from __future__ import annotations

import builtins
import platform
import shutil
import subprocess

from app.live_state import sanitize_live_state
from local_bridge import project_cli as base

_ORIGINAL_EXTRACT = base.extract_live_delta


def read_clipboard_text() -> str:
    """Read the native clipboard so legacy CMD users do not need terminal Ctrl+V."""
    system = platform.system()
    if system == "Windows":
        commands = [
            ["powershell.exe", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            ["pwsh", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
        ]
    elif system == "Darwin":
        commands = [["pbpaste"]]
    else:
        commands = [
            ["wl-paste", "--no-newline"],
            ["xclip", "-selection", "clipboard", "-o"],
            ["xsel", "--clipboard", "--output"],
        ]
    for cmd in commands:
        if not shutil.which(cmd[0]):
            continue
        try:
            p = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5
            )
            if p.returncode == 0 and (p.stdout or "").strip():
                return (p.stdout or "").strip()
        except Exception:
            pass
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        value = root.clipboard_get()
        root.destroy()
        return str(value or "").strip()
    except Exception as exc:
        raise RuntimeError(
            "클립보드를 읽을 수 없습니다. Windows Terminal/macOS Terminal에서 다시 시도하세요."
        ) from exc


def _safe_extract(output: str):
    answer, delta = _ORIGINAL_EXTRACT(output)
    if not delta:
        return answer, {}
    safe = sanitize_live_state(delta)
    if not any(bool(v) for v in safe.values()):
        return answer, {}
    return answer, safe


def _paste_aware_input(original_input):
    def wrapped(prompt: str = "") -> str:
        value = original_input(prompt)
        if str(value).strip().lower() != "/paste":
            return value
        try:
            text = read_clipboard_text()
        except Exception as exc:
            print(f"[Clipboard] 읽기 실패: {exc}")
            return ""
        if not text:
            print("[Clipboard] 클립보드가 비어 있습니다.")
            return ""
        print(f"[Clipboard] {text.count(chr(10)) + 1}줄을 하나의 메시지로 불러왔습니다.")
        return text
    return wrapped


def main(argv=None) -> int:
    base.extract_live_delta = _safe_extract
    if "/paste" not in base.WELCOME:
        base.WELCOME = base.WELCOME.replace(
            "명령: ",
            "명령: /paste(클립보드 여러 줄 입력), ",
        )
    original_input = builtins.input
    builtins.input = _paste_aware_input(original_input)
    try:
        return base.main(argv)
    finally:
        builtins.input = original_input
        base.extract_live_delta = _ORIGINAL_EXTRACT


if __name__ == "__main__":
    raise SystemExit(main())
