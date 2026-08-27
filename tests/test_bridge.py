import subprocess
import sys
import unittest
from pathlib import Path

from local_bridge.bridge import prepare_local_command, provider_command


class BridgeProviderTests(unittest.TestCase):
    def test_conversational_cli_subcommands_are_registered(self):
        bridge = Path(__file__).resolve().parents[1] / "local_bridge" / "bridge.py"
        result = subprocess.run([sys.executable, str(bridge), "-h"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("assistant-register", result.stdout)
        self.assertIn("assistant-run", result.stdout)

    def test_prepare_local_command_reports_missing_cli(self):
        with self.assertRaisesRegex(RuntimeError, "Local CLI not found"):
            prepare_local_command(["definitely-not-a-real-project-os-cli-xyz", "--version"])

    def test_antigravity_headless_command(self):
        cmd = provider_command("antigravity", "do the task")
        self.assertEqual(cmd[0], "agy")
        self.assertIn("-p", cmd)
        self.assertIn("--output-format", cmd)
        self.assertNotIn("--dangerously-skip-permissions", cmd)


if __name__ == "__main__":
    unittest.main()
