"""Signal-aware cleanup for local evaluation process groups (POSIX)."""

import contextlib
import os
import signal
import subprocess


@contextlib.contextmanager
def termination_guard():
    """Make SIGTERM unwind Python contexts like interactive cancellation."""
    previous = signal.getsignal(signal.SIGTERM)

    def interrupt(signum, frame):
        raise KeyboardInterrupt("evaluation terminated")

    signal.signal(signal.SIGTERM, interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def stop_process_group(process, grace_seconds=0):
    """Stop a process group and return its final captured output."""
    try:
        os.killpg(process.pid, signal.SIGTERM if grace_seconds else signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        return process.communicate(timeout=grace_seconds or 5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return process.communicate(timeout=5)
