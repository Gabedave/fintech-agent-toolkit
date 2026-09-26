import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import evaluate_behavior


class EvaluationCancellation(unittest.TestCase):
    def test_behavior_timeout_stops_model_process_group(self):
        with tempfile.TemporaryDirectory() as directory:
            pid_file = Path(directory) / "model.pid"
            sleeper = (
                "import os,time; from pathlib import Path; "
                f"Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(30)"
            )
            with self.assertRaises(evaluate_behavior.BehaviorTimeout):
                evaluate_behavior.run_command(
                    [sys.executable, "-B", "-c", sleeper],
                    "",
                    timeout_seconds=0.5,
                )
            model_pid = int(pid_file.read_text())
            with self.assertRaises(ProcessLookupError):
                os.kill(model_pid, 0)

    def test_sigterm_through_wrapper_stops_nested_model_and_cleans_context(self):
        self.check_termination(wrapper=True)

    def test_sigterm_directly_to_evaluator_stops_model(self):
        self.check_termination(wrapper=False)

    def check_termination(self, wrapper):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pid_file = root / "model.pid"
            state_file = root / "state.path"
            sleeper = ("import os,time; from pathlib import Path; "
                       f"Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(30)")
            evaluator = (
                f"import sys; sys.path.insert(0, {str(SCRIPTS)!r}); "
                "import evaluate_review_quality as quality; "
                f"quality.run_command([{sys.executable!r}, '-c', {sleeper!r}], timeout=25)"
            )
            if wrapper:
                program = (
                    "import os,sys,tempfile\nfrom pathlib import Path\n"
                    f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
                    "import release_smoke\nfrom process_control import termination_guard\n"
                    "with termination_guard(), tempfile.TemporaryDirectory() as state:\n"
                    f"    Path({str(state_file)!r}).write_text(state)\n"
                    f"    release_smoke.run([{sys.executable!r}, '-B', '-c', {evaluator!r}], os.environ.copy(), 'synthetic evaluator')\n"
                )
            else:
                program = evaluator
            parent = subprocess.Popen([sys.executable, "-B", "-c", program],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      start_new_session=True)
            model_pid = None
            try:
                deadline = time.monotonic() + 5
                while not pid_file.exists() and time.monotonic() < deadline:
                    if parent.poll() is not None:
                        self.fail("synthetic evaluator exited before spawning its model")
                    time.sleep(.01)
                self.assertTrue(pid_file.exists(), "synthetic model did not start")
                model_pid = int(pid_file.read_text())
                parent.terminate()
                parent.communicate(timeout=10)
                self.assertNotEqual(parent.returncode, 0)
                with self.assertRaises(ProcessLookupError):
                    os.kill(model_pid, 0)
                if wrapper:
                    self.assertFalse(Path(state_file.read_text()).exists())
            finally:
                if parent.poll() is None:
                    os.killpg(parent.pid, signal.SIGKILL)
                    parent.communicate(timeout=5)
                if model_pid is not None:
                    try:
                        os.kill(model_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass


if __name__ == "__main__":
    unittest.main()
