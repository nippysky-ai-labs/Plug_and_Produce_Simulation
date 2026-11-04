"""Machine start and completion logic, shared by recipes and production."""
import time
from . import settings
from .modbus_io import read_register, write_register, wait_for_register


def start_process(process_number):
    """Verify a part, start the machine, confirm running, then return."""
    signals = settings.PROCESS_SIGNALS[process_number]
    if read_register(signals["sensor"]) != 1:
        raise RuntimeError(f"Process {process_number} has no part.")
    if read_register(signals["running"]) != 0:
        raise RuntimeError(f"Process {process_number} is already running.")
    write_register(signals["start"], 1)
    wait_for_register(signals["running"], 1, timeout=5)
    return time.monotonic()


def process_has_finished(process_number, started_at):
    """Check without blocking so the scheduler can do other work."""
    signals = settings.PROCESS_SIGNALS[process_number]
    if read_register(signals["sensor"]) != 1:
        raise RuntimeError(f"Part disappeared from Process {process_number}.")
    if read_register(signals["running"]) == 0:
        return True
    if time.monotonic() - started_at > settings.PROCESS_TIMEOUT:
        raise TimeoutError(f"Process {process_number} exceeded its time limit.")
    return False


def run_process_and_wait(process_number, stop_event=None):
    """Sequential recipes stay here until this machine reports completion."""
    start_process(process_number)
    signals = settings.PROCESS_SIGNALS[process_number]
    wait_for_register(signals["running"], 0,
                      timeout=settings.PROCESS_TIMEOUT, stop_event=stop_event)
