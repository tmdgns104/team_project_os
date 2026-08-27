import unittest

from local_bridge.bridge import provider_command


class BridgeProviderTests(unittest.TestCase):
    def test_antigravity_headless_command(self):
        cmd = provider_command("antigravity", "do the task")
        self.assertEqual(cmd[0], "agy")
        self.assertIn("-p", cmd)
        self.assertIn("--output-format", cmd)
        self.assertNotIn("--dangerously-skip-permissions", cmd)


if __name__ == "__main__":
    unittest.main()
