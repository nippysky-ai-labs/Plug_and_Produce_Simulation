"""Grade A operator panel: widgets, button callbacks and background work.

Follow the numbered sections below. Physical operations live in other modules.
Only handle_worker_messages updates Tk widgets in response to worker messages.
"""
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import webbrowser

from . import settings
from .modbus_io import connect_to_simulation, disconnect_from_simulation, read_register
from .crane_motion import read_crane_position, set_gripper_vacuum
from .recipe_engine import (load_recipe, save_recipe, validate_recipe,
                            build_safe_move_actions, execute_recipe_actions, integer)
from .product_logging import create_log_file, ProductTracker
from .production_scheduler import run_full_production

FOLDER = settings.RECIPE_FOLDER
NAMES = settings.STATION_NAMES
# Appearance is explicit, so it is easy to explain and change.
BACKGROUND_COLOR = '#eef2f6'
PANEL_COLOR = '#ffffff'
TEXT_COLOR = '#152536'
FONT_FAMILY = 'Segoe UI'

class CraneControlPanel:
    def __init__(self, root):
        """Create the panel state, load its recipe, build widgets, and schedule message handling."""
        self.root = root
        self.messages = queue.Queue()
        self.busy = False
        self.stop_requested = threading.Event()
        self.buttons = []
        self.path = FOLDER / 'grade_a.json'
        self.document = load_recipe(self.path)
        self.x = tk.StringVar(value='55')
        self.y = tk.StringVar(value='82')
        self.position = tk.StringVar(value='Current crane position: click Read position')
        self.status = tk.StringVar(value='Ready. Reset the simulation before a fresh run.')
        self.build_interface()
        self.refresh_position_table_and_action_list()
        self.root.after(100, self.handle_worker_messages)
        self.root.protocol('WM_DELETE_WINDOW', self.close_window)

    def add_button(self, parent, label, command):
        """Create a guarded button and remember it so commands can be disabled while busy."""
        def guarded():
            """Run a button callback only when idle and show input errors in a dialog."""
            if self.busy:
                return
            try:
                command()
            except Exception as error:
                messagebox.showerror('Check this', str(error), parent=self.root)
        button = ttk.Button(parent, text=label, command=guarded)
        button.pack(side='left', padx=3, pady=4)
        self.buttons.append(button)
        return button

    def build_interface(self):
        """Construct the appearance, immediate controls, station table, recipe editor and run buttons."""
        self.root.title('PFA600 - Grade A Crane Control')
        self.root.geometry('1160x850')
        self.root.minsize(1000, 740)
        # SECTION 1: appearance. ttk widgets get colours from a style.
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('.', font=(FONT_FAMILY, 10))
        style.configure('TFrame', background=BACKGROUND_COLOR)
        style.configure('TLabel', background=BACKGROUND_COLOR, foreground=TEXT_COLOR)
        style.configure('TLabelframe', background=BACKGROUND_COLOR)
        style.configure('TLabelframe.Label', background=BACKGROUND_COLOR, foreground=TEXT_COLOR)
        style.configure('Treeview', background=PANEL_COLOR, fieldbackground=PANEL_COLOR,
                        foreground=TEXT_COLOR, rowheight=23)
        self.root.configure(background=BACKGROUND_COLOR)
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='Crane control and recipe editor',
                  font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(outer, textvariable=self.position).pack(anchor='w', pady=6)
        self.sensors = tk.StringVar(value='Sensors: click Read position + sensors to refresh.')
        ttk.Label(outer, textvariable=self.sensors).pack(anchor='w')
        # SECTION 2: immediate machine controls.
        row = ttk.Frame(outer)
        row.pack(fill='x')
        self.add_button(row, 'Read position + sensors', lambda: self.start_background_operation(self.publish_crane_readings))
        ttk.Label(row, text='Target X').pack(side='left', padx=(15, 3))
        ttk.Entry(row, textvariable=self.x, width=8).pack(side='left')
        ttk.Label(row, text='Target Y').pack(side='left', padx=(10, 3))
        ttk.Entry(row, textvariable=self.y, width=8).pack(side='left')
        self.add_button(row, 'Move crane NOW', self.move_to_entered_position)
        self.add_button(row, 'Vacuum ON now', lambda: self.operate_vacuum_now(1))
        self.add_button(row, 'Vacuum OFF now', lambda: self.operate_vacuum_now(0))

        # SECTION 3: saved station positions and teaching controls.
        box = ttk.LabelFrame(outer, text='Saved positions - select a row', padding=7)
        box.pack(fill='x', pady=8)
        self.table = ttk.Treeview(box, columns=('x', 'y'), height=5)
        self.table.heading('#0', text='Station')
        self.table.heading('x', text='X')
        self.table.heading('y', text='Y')
        self.table.column('#0', width=250)
        self.table.column('x', width=120)
        self.table.column('y', width=120)
        self.table.pack(fill='x')
        self.table.bind('<<TreeviewSelect>>', self.select_saved_position)
        row = ttk.Frame(box)
        row.pack(fill='x')
        self.add_button(row, 'Teach selected from crane', self.teach_selected_station)
        self.add_button(row, 'Add target movement to recipe', self.add_safe_move_to_recipe)
        self.add_button(row, 'Add current crane point', self.add_current_point_to_recipe)
        ttk.Label(box, text='Teach updates the saved station only. Existing numeric actions stay unchanged.').pack(anchor='w')

        # SECTION 4: editable recipe action list.
        box = ttk.LabelFrame(outer, text='Sequence - actions execute from top to bottom', padding=7)
        box.pack(fill='both', expand=True)
        self.action_list = tk.Listbox(box, font=('Consolas', 10), height=10, bg=PANEL_COLOR, fg=TEXT_COLOR,
                                     exportselection=False)
        scroll = ttk.Scrollbar(box, command=self.action_list.yview)
        scroll.pack(side='right', fill='y')
        self.action_list.configure(yscrollcommand=scroll.set)
        self.action_list.pack(fill='both', expand=True)
        row = ttk.Frame(outer)
        row.pack(fill='x')
        for label, action in (
            ('Add vacuum ON', {'vacuum': 1}),
            ('Add vacuum OFF', {'vacuum': 0}),
            ('Add Process 1', {'run_process': 1}),
            ('Add Process 2', {'run_process': 2}),
            ('Add wait Source 1', {'wait_sensor': 17, 'value': 1}),
            ('Add wait Source 2', {'wait_sensor': 18, 'value': 1}),
        ):
            self.add_button(row, label, lambda a=action: self.append_recipe_action(a))
        row = ttk.Frame(outer)
        row.pack(fill='x')
        self.add_button(row, 'Delete selected action', self.delete_selected_action)
        self.add_button(row, 'Move action up', lambda: self.reorder_selected_action(-1))
        self.add_button(row, 'Move action down', lambda: self.reorder_selected_action(1))
        self.add_button(row, 'Clear sequence', self.clear_recipe_actions)
        row = ttk.Frame(outer)
        row.pack(fill='x')
        self.add_button(row, 'Load JSON', self.load_recipe_dialog)
        self.add_button(row, 'Save JSON', self.save_recipe_dialog)
        self.add_button(row, 'Run saved sequence', self.run_saved_sequence)
        self.add_button(row, 'Run FULL PRODUCTION (Grade A)', self.run_full_production_from_hmi)
        self.stop_button = ttk.Button(row, text='Stop after action',
                                      command=self.stop_requested.set, state='disabled')
        self.stop_button.pack(side='left', padx=3)
        ttk.Label(outer, textvariable=self.status, wraplength=1000).pack(anchor='w', pady=8)
        ttk.Label(outer, text='Recipe mode executes the action list. Full production uses the two-route scheduler and saves CSV logs.').pack(anchor='w')

    def refresh_position_table_and_action_list(self):
        """Redraw both views from the in-memory recipe without commanding the machine."""
        selected = self.table.selection()
        self.table.delete(*self.table.get_children())
        for name in NAMES:
            point = self.document['positions'][name]
            self.table.insert('', 'end', iid=name, text=name,
                              values=(point['x'], point['y']))
        if selected:
            self.table.selection_set(selected[0])
        self.action_list.delete(0, 'end')
        for number, action in enumerate(self.document['actions'], 1):
            self.action_list.insert('end', f'{number:02d}  {json.dumps(action)}')

    def select_saved_position(self, event=None):
        """Copy the selected station coordinates into the Target X and Target Y entry fields."""
        selected = self.table.selection()
        if selected:
            point = self.document['positions'][selected[0]]
            self.x.set(str(point['x']))
            self.y.set(str(point['y']))

    def read_target_entries(self):
        """Convert entry text into whole-number coordinates and validate the allowed range."""
        x, y = int(self.x.get()), int(self.y.get())
        integer(x, 0, 1050, 'X')
        integer(y, 0, 320, 'Y')
        return x, y

    def publish_crane_readings(self):
        """Worker reads the machine; a queue carries the readings to the UI."""
        point = read_crane_position()
        self.messages.put(('position', point))
        snapshot = {name: read_register(address)
                    for name, address in settings.STATION_SENSORS.items()}
        snapshot['p1_running'] = read_register(settings.PROCESS_1_RUNNING)
        snapshot['p2_running'] = read_register(settings.PROCESS_2_RUNNING)
        snapshot['vacuum'] = read_register(settings.VACUUM)
        self.messages.put(('sensors', snapshot))
        return point

    def move_to_entered_position(self):
        """Build lift-travel-lower waypoints and execute them as an immediate command."""
        x, y = self.read_target_entries()
        actions = build_safe_move_actions(x, y, self.document['safe_y'])
        self.start_background_operation(lambda: self.execute_sequence(actions), sequence=True)

    def operate_vacuum_now(self, value):
        """Immediate command, unlike the Add vacuum buttons which edit JSON data."""
        self.start_background_operation(lambda: set_gripper_vacuum(value))

    def teach_selected_station(self):
        """Read the physical crane position and ask the UI thread to assign it to the selected station."""
        selected = self.table.selection()
        if not selected:
            raise ValueError('Select a station row first.')
        name = selected[0]
        def work():
            self.messages.put(('teach', (name, self.publish_crane_readings())))
        self.start_background_operation(work)

    def add_current_point_to_recipe(self):
        """Record one measured crane waypoint in the recipe without moving the crane."""
        def work():
            point = self.publish_crane_readings()
            self.messages.put(('append', {'setX': point['x'], 'setY': point['y']}))
        self.start_background_operation(work)

    def add_safe_move_to_recipe(self):
        """Append lift-travel-lower instructions for the target entries without executing them."""
        x, y = self.read_target_entries()
        self.document['actions'].extend(build_safe_move_actions(x, y, self.document['safe_y']))
        self.refresh_position_table_and_action_list()
        self.status.set('Three waypoints added: lift, travel, approach. Save JSON to keep them.')

    def append_recipe_action(self, action):
        """Append a copy of a vacuum, process or wait instruction to the recipe."""
        self.document['actions'].append(dict(action))
        self.refresh_position_table_and_action_list()
        self.status.set('Action added. Save JSON to keep changes.')

    def delete_selected_action(self):
        """Remove only the selected action from the in-memory list."""
        selected = self.action_list.curselection()
        if selected:
            del self.document['actions'][selected[0]]
            self.refresh_position_table_and_action_list()

    def reorder_selected_action(self, direction):
        """Swap the selected instruction with its neighbour while keeping it selected."""
        selected = self.action_list.curselection()
        if selected:
            index = selected[0]
            other = index + direction
            actions = self.document['actions']
            if 0 <= other < len(actions):
                actions[index], actions[other] = actions[other], actions[index]
                self.refresh_position_table_and_action_list()
                self.action_list.selection_set(other)

    def clear_recipe_actions(self):
        """Clear actions after confirmation; saved station coordinates remain available."""
        if messagebox.askyesno('Clear sequence', 'Remove all actions from the editor?'):
            self.document['actions'] = []
            self.refresh_position_table_and_action_list()

    def save_recipe_dialog(self):
        """Ask for a path, then delegate JSON writing to recipe_engine.py."""
        validate_recipe(self.document)
        path = filedialog.asksaveasfilename(
            initialdir=FOLDER, initialfile=self.path.name,
            defaultextension='.json', filetypes=[('JSON recipes', '*.json')])
        if not path:
            return False
        self.path = Path(path)
        save_recipe(self.path, self.document)
        self.status.set(f'Saved {self.path.name}')
        return True

    def load_recipe_dialog(self):
        """Load a full recipe and redraw the station and action views."""
        path = filedialog.askopenfilename(initialdir=FOLDER,
                                          filetypes=[('JSON recipes', '*.json')])
        if path:
            self.document = load_recipe(path)
            self.path = Path(path)
            self.refresh_position_table_and_action_list()
            self.status.set(f'Loaded {self.path.name}')

    def open_code_walkthrough(self):
        """Open the local searchable, line-numbered source explanation."""
        webbrowser.open((settings.PROJECT_FOLDER / 'docs' / 'CODE_WALKTHROUGH.html').as_uri())

    def execute_sequence(self, actions, after_action=None):
        """Use the same interpreter as the other grades; report completed actions."""
        def completed(action):
            if after_action is not None:
                after_action(action)
            self.publish_crane_readings()
        execute_recipe_actions(actions, after_action=completed,
                               stop_event=self.stop_requested,
                               report=lambda text: self.messages.put(('status', text)))

    def run_saved_sequence(self):
        """Save and replay a single-product taught recipe with CSV evidence."""
        if not self.document['actions']:
            raise ValueError('Add actions or load a sequence first.')
        if not self.save_recipe_dialog():
            return
        data = load_recipe(self.path)
        def work():
            path, log_file, writer = create_log_file('grade_a_sequence')
            try:
                tracker = ProductTracker(writer, log_file, product_id=1)
                self.execute_sequence(data['actions'], tracker.log_completed_action)
                self.messages.put(('status', f'Sequence complete. CSV: {path.name}'))
            finally:
                log_file.close()
        self.start_background_operation(work, sequence=True)

    def run_full_production_from_hmi(self):
        """Grade A uses the Grade B scheduler plus teaching and recipe features."""
        if not self.save_recipe_dialog():
            return
        data = load_recipe(self.path)
        def work():
            path, log_file, writer = create_log_file('grade_a_production')
            def report(text):
                print(text)
                self.messages.put(('status', text))
                self.publish_crane_readings()
            try:
                run_full_production(data, writer, log_file, report, self.stop_requested)
                self.messages.put(('status', f'Batch complete. CSV: {path.name}'))
            finally:
                log_file.close()
        self.start_background_operation(work, sequence=True)

    def start_background_operation(self, function, sequence=False):
        """One worker owns Modbus; only the main thread touches Tk widgets."""
        if self.busy:
            return
        self.busy = True
        self.stop_requested.clear()
        for button in self.buttons:
            button.configure(state='disabled')
        self.stop_button.configure(state='normal' if sequence else 'disabled')
        self.status.set('Working...')
        def worker():
            """Own the Modbus connection during one task and always disconnect afterwards."""
            try:
                connect_to_simulation()
                function()
                self.publish_crane_readings()
            except Exception as error:
                self.messages.put(('error', str(error)))
            finally:
                disconnect_from_simulation()
                self.messages.put(('done', None))
        threading.Thread(target=worker, daemon=True).start()

    def handle_worker_messages(self):
        """Drain the thread-safe queue and apply position, teaching, status and completion updates."""
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == 'position':
                    self.position.set(f"Last crane reading: X={value['x']}   Y={value['y']}")
                elif kind == 'sensors':
                    self.sensors.set('Last sensor readings: ' + ' | '.join(f'{k}={v}' for k, v in value.items()))
                elif kind == 'teach':
                    name, point = value
                    self.document['positions'][name] = point
                    self.refresh_position_table_and_action_list()
                    self.status.set(f'Taught {name}: {point}. Save JSON to keep it.')
                elif kind == 'append':
                    self.append_recipe_action(value)
                elif kind == 'status':
                    self.status.set(value)
                elif kind == 'error':
                    self.status.set(value)
                    messagebox.showerror('Operation stopped', value, parent=self.root)
                elif kind == 'done':
                    self.busy = False
                    for button in self.buttons:
                        button.configure(state='normal')
                    self.stop_button.configure(state='disabled')
                    text = self.status.get()
                    self.status.set('Ready.' if text == 'Working...' else 'Ready. ' + text)
        except queue.Empty:
            pass
        self.root.after(100, self.handle_worker_messages)

    def close_window(self):
        """Prevent closing during work and ask before discarding unsaved editor changes."""
        if self.busy:
            messagebox.showinfo('Operation active',
                'Click Stop after action and wait for the operation to end, then close. '
                'A running process may finish independently; reset before starting again.')
            return
        if messagebox.askyesno('Close', 'Close the interface? Save JSON first if you need to keep editor changes.'):
            self.root.destroy()


def main():
    """Create the Tk application, construct the panel and start its event loop."""
    root = tk.Tk()
    try:
        CraneControlPanel(root)
    except Exception as error:
        messagebox.showerror('Could not open Grade A', str(error), parent=root)
        root.destroy()
        return
    root.mainloop()


if __name__ == '__main__':
    main()
