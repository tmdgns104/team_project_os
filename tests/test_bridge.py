import subprocess
import sys
import unittest
from pathlib import Path


class BridgeCliTests(unittest.TestCase):
    def test_conversational_cli_subcommands_are_registered(self):
        bridge = Path(__file__).resolve().parents[1] / "local_bridge" / "bridge.py"
        result = subprocess.run([sys.executable, str(bridge), "-h"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("assistant-register", result.stdout)
        self.assertIn("assistant-run", result.stdout)


if __name__ == "__main__":
    unittest.main()
