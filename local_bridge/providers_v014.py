from __future__ import annotations

import platform

from local_bridge.providers import SUPPORTED_PROVIDERS, doctor, run_provider


def print_doctor() -> None:
    system = platform.system()
    locator = "where" if system == "Windows" else "which"
    py = "python" if system == "Windows" else "python3"
    for row in doctor():
        if row["ok"]:
            print(f"{row['label']}: OK {row['version']} [{row['path']}]")
            continue
        executable = "agy" if row["provider"] == "antigravity" else row["provider"]
        error = str(row.get("error", "unknown error"))
        # The legacy provider module's error text mentions Windows; replace the
        # guidance while keeping the underlying cross-platform detection logic.
        if system != "Windows":
            error = error.replace(f"where {executable}", f"which {executable}").replace(" on Windows.", ".")
        print(f"{row['label']}: not detected ({error})")
        print(f"  확인: {py} project_os.py doctor / {locator} {executable}")


__all__ = ["SUPPORTED_PROVIDERS", "run_provider", "doctor", "print_doctor"]
