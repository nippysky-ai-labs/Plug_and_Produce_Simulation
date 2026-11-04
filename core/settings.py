"""Connection, address names and folders: start here for sensor questions."""
from pathlib import Path

PROJECT_FOLDER = Path(__file__).resolve().parent.parent
RECIPE_FOLDER = PROJECT_FOLDER / "recipes"
LOG_FOLDER = PROJECT_FOLDER / "logs"
HOST = "127.0.0.1"
PORT = 502  # Change to 5020 if that is shown by your simulation.
POLL_SECONDS = 0.05
MOVEMENT_TIMEOUT = 20
PROCESS_TIMEOUT = 120
MIN_TRAVEL_HEIGHT = 150

RESET_PROCESSES = 0  # Stops processes; does NOT reset the whole simulation.
TARGET_X = 1
TARGET_Y = 2
VACUUM = 3
START_PROCESS_1 = 4
START_PROCESS_2 = 5
ACTUAL_X = 15
ACTUAL_Y = 16
SOURCE_1_SENSOR = 17
SOURCE_2_SENSOR = 18
PROCESS_1_RUNNING = 19
PROCESS_2_RUNNING = 20
PROCESS_1_SENSOR = 21
PROCESS_2_SENSOR = 22
BUTTON_1 = 23
BUTTON_2 = 24

STATION_SENSORS = {
    "source1": SOURCE_1_SENSOR, "source2": SOURCE_2_SENSOR,
    "process1": PROCESS_1_SENSOR, "process2": PROCESS_2_SENSOR,
}
PROCESS_SIGNALS = {
    1: {"start": START_PROCESS_1, "running": PROCESS_1_RUNNING,
        "sensor": PROCESS_1_SENSOR},
    2: {"start": START_PROCESS_2, "running": PROCESS_2_RUNNING,
        "sensor": PROCESS_2_SENSOR},
}
STATION_NAMES = ("source1", "source2", "process1", "process2", "sink")
