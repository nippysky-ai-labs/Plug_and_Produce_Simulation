"""Small command-line demonstrations of the cumulative E, D, C and B requirements."""
from .settings import RECIPE_FOLDER
from .modbus_io import connect_to_simulation, disconnect_from_simulation
from .recipe_engine import load_recipe, execute_recipe_actions
from .product_logging import create_log_file, ProductTracker
from .production_scheduler import run_full_production, require_empty_machines


def run_grade(grade):
    """Select grade-specific behavior, while reusing the same tested operations."""
    log_file = None
    try:
        name = 'production' if grade == 'B' else ('grade_e' if grade == 'E' else 'grade_d')
        recipe = load_recipe(RECIPE_FOLDER / f'{name}.json')
        count = 1
        if grade in ('D', 'C'):
            count = int(input('How many Source 1 parts? '))
            if count < 1:
                raise ValueError('Enter a positive whole number.')
        connect_to_simulation()
        require_empty_machines()
        if grade in ('C', 'B'):
            path, log_file, writer = create_log_file(f'grade_{grade.lower()}')
            print(f'CSV: {path}')
        if grade == 'B':
            run_full_production(recipe, writer, log_file)
        else:
            for product_id in range(1, count + 1):
                callback = None
                if grade == 'C':
                    tracker = ProductTracker(writer, log_file, product_id)
                    callback = tracker.log_completed_action
                execute_recipe_actions(recipe['actions'], after_action=callback)
        print('Run finished. Check delivered, scrap and collision counters.')
    except (Exception, KeyboardInterrupt) as error:
        print(f'Stopped: {error}')
    finally:
        if log_file is not None:
            log_file.close()
        disconnect_from_simulation()
