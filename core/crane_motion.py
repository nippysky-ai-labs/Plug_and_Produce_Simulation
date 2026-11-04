"""Physical crane operations: current position, arrival, movement and vacuum."""
import time
from . import settings
from .modbus_io import read_register, write_register


def read_crane_position():
    """Return the measured position, not the commanded target."""
    return {"x": read_register(settings.ACTUAL_X),
            "y": read_register(settings.ACTUAL_Y)}


def wait_for_crane_arrival(x, y, timeout=settings.MOVEMENT_TIMEOUT):
    """Advance only after position feedback agrees with the destination."""
    started = time.monotonic()
    while True:
        actual = read_crane_position()
        if actual["x"] == x and actual["y"] == y:
            # The simulation rounds positions to integers. One short settling
            # interval avoids gripping before the final fraction of a unit.
            time.sleep(settings.POLL_SECONDS)
            if read_crane_position() == actual:
                return
        if time.monotonic() - started > timeout:
            raise TimeoutError(f"Cannot reach ({x}, {y}); last position: {actual}.")
        time.sleep(settings.POLL_SECONDS)


def move_crane_to(x, y):
    """Command one waypoint. Horizontal travel must be above the walls."""
    if type(x) is not int or type(y) is not int:
        raise ValueError("X and Y must be whole numbers.")
    if not (0 <= x <= 1050 and 0 <= y <= 320):
        raise ValueError("Position is outside the simulation's movement range.")
    current = read_crane_position()
    if x != current["x"] and min(current["y"], y) < settings.MIN_TRAVEL_HEIGHT:
        raise ValueError("Lift to the travel height before moving sideways.")
    write_register(settings.TARGET_X, x)
    write_register(settings.TARGET_Y, y)
    wait_for_crane_arrival(x, y)


def set_gripper_vacuum(value):
    """1 enables suction; 0 releases the part. This is a command, not a grip sensor."""
    if type(value) is not int or value not in (0, 1):
        raise ValueError("Vacuum must be 0 or 1.")
    write_register(settings.VACUUM, value)
