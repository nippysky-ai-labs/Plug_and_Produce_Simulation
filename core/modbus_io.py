"""Communication only: connect, read, write, wait and disconnect."""
import time
from pymodbus.client import ModbusTcpClient
from . import settings

# One client object is shared through imports. Only one worker uses it at a time.
client = ModbusTcpClient(settings.HOST, port=settings.PORT, timeout=3)


def connect_to_simulation():
    """Open the Modbus TCP connection, or report a clear error."""
    if not client.connect():
        raise ConnectionError(
            f"Cannot connect to {settings.HOST}:{settings.PORT}. "
            "Start the simulation and check core/settings.py."
        )


def disconnect_from_simulation():
    """Release the connection even after a failed operation."""
    client.close()


def read_register(address):
    """Request one holding register and return its integer value."""
    result = client.read_holding_registers(address=address, count=1)
    if result.isError():
        raise RuntimeError(f"Modbus read failed at address {address}: {result}")
    if not result.registers:
        raise RuntimeError(f"No data returned at address {address}.")
    return result.registers[0]


def write_register(address, value):
    """Write a command, checking the Modbus reply before continuing."""
    if address not in (0, 1, 2, 3, 4, 5):
        raise ValueError("Only command addresses 0 to 5 may be written.")
    result = client.write_register(address=address, value=value)
    if result.isError():
        raise RuntimeError(f"Modbus write failed at address {address}: {result}")
    print(f"WRITE address {address} = {value}")


def check_stop_request(stop_event=None):
    """A cooperative stop is checked at defined boundaries, not an emergency stop."""
    if stop_event is not None and stop_event.is_set():
        raise InterruptedError("Stopped between actions. Reset before a new run.")


def wait_for_register(address, expected, timeout=None, stop_event=None):
    """Poll a sensor until its value matches; timeout=None permits an operator wait."""
    started = time.monotonic()
    while True:
        check_stop_request(stop_event)
        if read_register(address) == expected:
            return
        if timeout is not None and time.monotonic() - started > timeout:
            raise TimeoutError(f"Address {address} did not become {expected}.")
        time.sleep(settings.POLL_SECONDS)
