"""Load, save, validate and execute recipes. JSON stores data, Python executes it."""
import json
from pathlib import Path
from .settings import STATION_NAMES as NAMES
from .modbus_io import read_register, wait_for_register, check_stop_request
from .crane_motion import read_crane_position, move_crane_to, set_gripper_vacuum
from .process_control import run_process_and_wait

def integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{label} must be a whole number from {low} to {high}.')
    return value


def validate_recipe(data):
    """Reject invalid settings before saving or moving the crane."""
    if not isinstance(data, dict):
        raise ValueError('The JSON must contain an object.')
    for name in NAMES:
        point = data['positions'][name]
        integer(point['x'], 0, 1050, f'{name} X')
        integer(point['y'], 0, 320, f'{name} Y')
    integer(data['safe_y'], 150, 320, 'Travel height')
    if not isinstance(data['actions'], list):
        raise ValueError('actions must be a list.')
    for action in data['actions']:
        if not isinstance(action, dict) or not action:
            raise ValueError('Each action must be a nonempty object.')
        keys = set(action)
        if keys <= {'setX', 'setY'}:
            if 'setX' in action:
                integer(action['setX'], 0, 1050, 'Action X')
            if 'setY' in action:
                integer(action['setY'], 0, 320, 'Action Y')
        elif keys == {'vacuum'}:
            integer(action['vacuum'], 0, 1, 'Vacuum')
        elif keys == {'run_process'}:
            integer(action['run_process'], 1, 2, 'Process')
        elif keys == {'wait_sensor', 'value'}:
            if action['wait_sensor'] not in (17, 18, 21, 22):
                raise ValueError('Use source or process part sensors: 17, 18, 21, 22.')
            integer(action['value'], 0, 1, 'Sensor value')
        else:
            raise ValueError(f'Unsupported action: {action}')
    return data


def build_safe_move_actions(x, y, height):
    """Lift first, travel horizontally, then approach the target vertically."""
    integer(x, 0, 1050, 'X')
    integer(y, 0, 320, 'Y')
    travel = max(height, y)
    return [{'setY': travel}, {'setX': x, 'setY': travel},
            {'setX': x, 'setY': y}]


def load_recipe(path):
    """Deserialize JSON, then check values before using them."""
    with Path(path).open(encoding="utf-8") as file:
        recipe = json.load(file)
    return validate_recipe(recipe)


def save_recipe(path, recipe):
    """Serialize the current recipe to readable, indented JSON."""
    validate_recipe(recipe)
    with Path(path).open("w", encoding="utf-8") as file:
        json.dump(recipe, file, indent=2)
        file.write("\n")


def execute_recipe_actions(actions, after_action=None, stop_event=None, report=print):
    """Interpret each action and call the appropriate operation."""
    for number, action in enumerate(actions, 1):
        check_stop_request(stop_event)
        report(f"Action {number}/{len(actions)}: {action}")
        if "wait_sensor" in action:
            wait_for_register(action["wait_sensor"], action["value"], stop_event=stop_event)
        if "setX" in action or "setY" in action:
            position = read_crane_position()
            move_crane_to(action.get("setX", position["x"]),
                          action.get("setY", position["y"]))
        if "vacuum" in action:
            set_gripper_vacuum(action["vacuum"])
        if "run_process" in action:
            run_process_and_wait(action["run_process"], stop_event)
        if after_action is not None:
            after_action(action)
    check_stop_request(stop_event)
