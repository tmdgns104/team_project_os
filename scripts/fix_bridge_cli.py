from pathlib import Path

bridge = Path("local_bridge/bridge.py")
s = bridge.read_text(encoding="utf-8")
old = '''    runp.set_defaults(func=run)\n    d = sub.add_parser("doctor", help="Detect installed AI CLIs")\n'''
new = '''    runp.set_defaults(func=run)\n\n    ar = sub.add_parser("assistant-register", help="Pair this machine/provider for conversational project setup")\n    ar.add_argument("--server", required=True)\n    ar.add_argument("--member", required=True)\n    ar.add_argument("--provider", required=True, choices=["codex", "claude", "opencode", "antigravity", "dry-run"])\n    ar.add_argument("--access-key", default="")\n    ar.add_argument("--command", default="", help="Optional custom CLI template; {prompt} may be used")\n    ar.set_defaults(func=assistant_register)\n\n    arp = sub.add_parser("assistant-run", help="Fetch and execute conversational Project Assistant jobs")\n    arp.add_argument("--cwd", default="")\n    arp.add_argument("--once", action="store_true")\n    arp.add_argument("--poll", type=int, default=10)\n    arp.add_argument("--command", default="")\n    arp.set_defaults(func=assistant_run)\n\n    d = sub.add_parser("doctor", help="Detect installed AI CLIs")\n'''
if "sub.add_parser(\"assistant-register\"" not in s:
    if old not in s:
        raise RuntimeError("bridge parser marker not found")
    s = s.replace(old, new, 1)
bridge.write_text(s, encoding="utf-8")

test = Path("tests/test_bridge.py")
t = test.read_text(encoding="utf-8")
if "test_conversational_cli_subcommands_are_registered" not in t:
    t = t.replace(
        "import unittest\n\nfrom local_bridge.bridge import provider_command\n",
        "import subprocess\nimport sys\nimport unittest\nfrom pathlib import Path\n\nfrom local_bridge.bridge import provider_command\n",
        1,
    )
    marker = "    def test_antigravity_headless_command(self):\n"
    addition = '''    def test_conversational_cli_subcommands_are_registered(self):\n        bridge = Path(__file__).resolve().parents[1] / "local_bridge" / "bridge.py"\n        result = subprocess.run([sys.executable, str(bridge), "-h"], capture_output=True, text=True)\n        self.assertEqual(result.returncode, 0, result.stderr)\n        self.assertIn("assistant-register", result.stdout)\n        self.assertIn("assistant-run", result.stdout)\n\n'''
    if marker not in t:
        raise RuntimeError("test marker not found")
    t = t.replace(marker, addition + marker, 1)
test.write_text(t, encoding="utf-8")
