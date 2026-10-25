import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "termfluid.py")
ALLOWED = set(" .:-=+%#@")


def run(*args):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


class CliTests(unittest.TestCase):
    def test_version(self):
        result = run("--version")
        self.assertEqual(result.returncode, 0)
        self.assertIn("termfluid", result.stdout)

    def test_headless_initial_frame(self):
        result = run("--headless", "0", "--width", "60", "--height", "20")
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 20)
        for line in lines:
            self.assertEqual(len(line), 60)
            self.assertTrue(set(line) <= ALLOWED)
        self.assertGreater(sum(1 for line in lines[:3] for c in line if c != " "), 0)
        self.assertEqual(sum(1 for line in lines[-3:] for c in line if c != " "), 0)
        self.assertIn("particles=", result.stderr)

    def test_headless_settles(self):
        result = run("--headless", "150", "--width", "60", "--height", "20")
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 20)
        top = sum(1 for line in lines[:3] for c in line if c != " ")
        bottom = sum(1 for line in lines[-3:] for c in line if c != " ")
        self.assertGreater(bottom, top)
        self.assertGreater(bottom, 0.8 * 3 * 60)
        self.assertIn("mean_y=", result.stderr)

    def test_headless_demo(self):
        result = run("--headless", "120", "--demo", "--width", "80", "--height", "24")
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 24)
        self.assertTrue(all(set(line) <= ALLOWED for line in lines))

    def test_headless_default_size(self):
        result = run("--headless", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 30)
        self.assertEqual({len(line) for line in lines}, {100})

    def test_headless_rejects_zero_size(self):
        for flag in ("--width", "--height"):
            with self.subTest(flag=flag):
                result = run("--headless", "0", flag, "0")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("at least 1", result.stderr)

    def test_headless_rejects_negative_size(self):
        for flag in ("--width", "--height"):
            with self.subTest(flag=flag):
                result = run("--headless", "0", flag, "-5")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("at least 1", result.stderr)

    def test_interactive_requires_terminal(self):
        result = subprocess.run(
            [sys.executable, SCRIPT],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("must be a terminal", result.stderr)

    def test_bad_option(self):
        result = run("--nonsense")
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
