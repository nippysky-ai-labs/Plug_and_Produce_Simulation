"""Grade B: decide which product the shared crane should handle next."""
import time
from . import settings
from .modbus_io import read_register, check_stop_request
from .recipe_engine import execute_recipe_actions
from .process_control import start_process, process_has_finished
from .product_logging import ProductTracker


def require_empty_machines():
    """A new run starts without old jobs or a held part."""
    addresses = (settings.VACUUM, settings.PROCESS_1_RUNNING,
                 settings.PROCESS_2_RUNNING, settings.PROCESS_1_SENSOR,
                 settings.PROCESS_2_SENSOR)
    if any(read_register(address) != 0 for address in addresses):
        raise RuntimeError("Reset the simulation before starting a fresh run.")


def build_transfer_actions(recipe, source, destination):
    """Resolve JSON placeholders to numbers for this particular transfer."""
    positions = recipe["positions"]
    values = {"source": positions[source]["x"],
              "source_y": positions[source]["y"],
              "destination": positions[destination]["x"],
              "destination_y": positions[destination]["y"],
              "safe_y": recipe["safe_y"]}
    actions = []
    for template in recipe["transfer"]:
        action = {}
        for key, value in template.items():
            action[key] = values[value] if isinstance(value, str) else value
        actions.append(action)
    return actions


def transfer_product(recipe, source, destination, tracker, report=print, stop_event=None):
    """Check station occupancy, move the part, and verify pickup/placement."""
    sensors = settings.STATION_SENSORS
    if read_register(sensors[source]) != 1:
        raise RuntimeError(f"No part at {source}.")
    if destination in sensors and read_register(sensors[destination]) != 0:
        raise RuntimeError(f"{destination} is occupied.")

    def verify_and_log(action):
        if action.get("vacuum") == 1 and read_register(sensors[source]) != 0:
            raise RuntimeError(f"Pickup failed at {source}.")
        if action.get("vacuum") == 0 and destination in sensors:
            if read_register(sensors[destination]) != 1:
                raise RuntimeError(f"Placement failed at {destination}.")
        tracker.log_completed_action(action)

    report(f"Product {tracker.product_id}: {source} -> {destination}")
    actions = build_transfer_actions(recipe, source, destination)
    execute_recipe_actions(actions, verify_and_log, stop_event, report)


def run_full_production(recipe, writer, log_file, report=print, stop_event=None):
    """Handle both routes until the detected batch is empty; wait for the first part."""
    require_empty_machines()
    process1_job = None
    process2_job = None
    next_product_id = 1
    delivered = 0
    # When both types compete for Process 1, alternate admission to avoid starvation.
    prefer_type1 = True
    report("Waiting for parts at either source.")

    def new_product():
        nonlocal next_product_id
        tracker = ProductTracker(writer, log_file, next_product_id)
        next_product_id += 1
        return tracker

    def start_job(number, tracker):
        started = start_process(number)
        report(f"Process {number} started for product {tracker.product_id}.")
        return {"tracker": tracker, "started": started}

    while True:
        check_stop_request(stop_event)
        p1_done = (process1_job is not None and
                   process_has_finished(1, process1_job["started"]))
        p2_done = (process2_job is not None and
                   process_has_finished(2, process2_job["started"]))
        source1_ready = read_register(settings.SOURCE_1_SENSOR) == 1
        source2_ready = read_register(settings.SOURCE_2_SENSOR) == 1

        if p1_done:
            transfer_product(recipe, "process1", "sink", process1_job["tracker"], report, stop_event)
            process1_job = None
            delivered += 1
            report(f"Completed transfer to sink: {delivered}. Verify the simulator counter.")

        elif process2_job is None and source2_ready:
            tracker = new_product()
            transfer_product(recipe, "source2", "process2", tracker, report, stop_event)
            process2_job = start_job(2, tracker)

        elif process1_job is None and source1_ready and (prefer_type1 or not p2_done):
            tracker = new_product()
            transfer_product(recipe, "source1", "process1", tracker, report, stop_event)
            process1_job = start_job(1, tracker)
            prefer_type1 = False

        elif process1_job is None and p2_done:
            tracker = process2_job["tracker"]
            transfer_product(recipe, "process2", "process1", tracker, report, stop_event)
            process2_job = None
            process1_job = start_job(1, tracker)
            prefer_type1 = True

        elif (delivered > 0 and process1_job is None and process2_job is None
              and not source1_ready and not source2_ready):
            report(f"Batch complete: {delivered} products routed to the sink.")
            return delivered
        else:
            time.sleep(settings.POLL_SECONDS)
