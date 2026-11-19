"""Exercise launch/failure ordering without starting Docker or requiring a GPU."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which("sh"), "Requires a POSIX shell; does not execute Windows batch files")
class LauncherTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="arol launchers ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ("avvia.sh", "avvia-gpu.sh"):
            shutil.copy2(ROOT / name, self.root / name)
        (self.root / "data/manuals").mkdir(parents=True)
        (self.root / "data/manuals/test.pdf").touch()
        binary = self.root / "bin"
        binary.mkdir()
        # Use a shell wrapper so interpreter paths containing spaces remain valid.
        python_path = "'" + sys.executable.replace("'", "'\\''") + "'"
        stub = binary / "docker"
        stub.write_text(f'#!/bin/sh\nexec {python_path} "$AROL_STUB" "$@"\n')
        stub.chmod(0o755)
        handler = self.root / "docker_stub.py"
        handler.write_text('''import json, os, sys
args = sys.argv[1:]
with open(os.environ["AROL_CALLS"], "a") as f:
    f.write(json.dumps(args) + "\\n")
if "run" in args and os.environ.get("AROL_FAIL_GPU") == "1": sys.exit(1)
if "up" in args and os.environ.get("AROL_FAIL_SETUP") == "1": sys.exit(1)
''')
        self.calls_path = self.root / "calls.jsonl"
        self.env = {
            **os.environ, "PATH": str(binary) + os.pathsep + os.environ.get("PATH", ""),
            "AROL_STUB": str(handler), "AROL_CALLS": str(self.calls_path),
        }

    def run_launcher(self, *args, script="avvia.sh", **overrides):
        result = subprocess.run(
            ["sh", str(self.root / script), *args], cwd=self.root.parent,
            env={**self.env, **overrides}, capture_output=True, text=True,
        )
        calls = [json.loads(line) for line in self.calls_path.read_text().splitlines()] if self.calls_path.exists() else []
        return result, calls

    def test_cpu_does_not_request_gpu_and_stops_readers_before_setup(self):
        result, calls = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any("run" in call or "compose.delivery.gpu.yml" in call for call in calls))
        self.assertLess(next(i for i,c in enumerate(calls) if "stop" in c), next(i for i,c in enumerate(calls) if "up" in c))

    def test_gpu_wrapper_uses_override_for_check_stop_and_start(self):
        result, calls = self.run_launcher(script="avvia-gpu.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        operations = [c for c in calls if any(op in c for op in ("run", "stop", "up"))]
        self.assertEqual(len(operations), 3)
        self.assertTrue(all("compose.delivery.gpu.yml" in c for c in operations))
        self.assertIn("nvidia-smi", operations[0])
        self.assertIn("--no-deps", operations[0])
        self.assertIn("stop", operations[1])
        self.assertIn("up", operations[2])
        self.assertIn("Ready:", result.stdout)

    def test_missing_nvidia_stops_before_disrupting_running_application(self):
        result, calls = self.run_launcher("--gpu", AROL_FAIL_GPU="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any("stop" in c or "up" in c for c in calls))
        self.assertNotIn("Ready:", result.stdout)
        self.assertIn("SETUP.md", result.stderr)

    def test_failed_gpu_setup_shows_logs_and_never_reports_ready(self):
        result, calls = self.run_launcher("--gpu", AROL_FAIL_SETUP="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Ready:", result.stdout)
        self.assertIn("logs", calls[-1])
        self.assertIn("compose.delivery.gpu.yml", calls[-1])

    def test_invalid_options_do_not_start_docker(self):
        result, calls = self.run_launcher("--unknown")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
