"""CSV tracking: one file per run, one tracker per product."""
import csv
from datetime import datetime
from .settings import LOG_FOLDER, VACUUM
from .modbus_io import read_register
from .crane_motion import read_crane_position


def create_log_file(label):
    """Create a unique run file and write the assignment's five-column header."""
    LOG_FOLDER.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = LOG_FOLDER / f"{label}_{timestamp}.csv"
    file = path.open("w", newline="", encoding="utf-8")
    writer = csv.writer(file)
    writer.writerow(["product_id", "timestamp", "x", "y", "vacuum"])
    file.flush()
    return path, file, writer


class ProductTracker:
    """Follow one product, ignoring movement of an empty crane."""
    def __init__(self, writer, file, product_id):
        self.writer = writer
        self.file = file
        self.product_id = product_id
        self.carrying = False
        self.last_record = None

    def write_product_position(self):
        """Read actual coordinates and vacuum, then flush one CSV row."""
        position = read_crane_position()
        vacuum = read_register(VACUUM)
        current = (position["x"], position["y"], vacuum)
        if current == self.last_record:
            return  # No new location or vacuum state to report.
        self.writer.writerow([
            self.product_id,
            datetime.now().astimezone().isoformat(timespec="milliseconds"),
            position["x"], position["y"], vacuum,
        ])
        self.file.flush()
        self.last_record = current

    def log_completed_action(self, action):
        """Callback: log pickups, loaded movements, and releases."""
        if "vacuum" in action:
            if action["vacuum"] == 1:
                self.carrying = True
                self.write_product_position()
            elif self.carrying:
                self.write_product_position()
                self.carrying = False
        elif ("setX" in action or "setY" in action) and self.carrying:
            self.write_product_position()
