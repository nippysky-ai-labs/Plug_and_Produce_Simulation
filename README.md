# Plug & Produce Crane Controller

A Python controller for a simulated manufacturing cell. It communicates with the simulator over Modbus TCP, moves a crane between stations, and tracks parts in CSV files. The Tkinter operator interface lets you teach station coordinates and build, save, and replay JSON recipes.

Developed for the PFA600 crane simulation project. The two product routes share one crane and one processing station.

| Product | Route |
| --- | --- |
| Type 1 | Source 1 → Process 1 → Sink |
| Type 2 | Source 2 → Process 2 → Process 1 → Sink |

## Quick start

You’ll need Git, Python with Tkinter, and a graphical desktop session. The Windows demo used Python 3.14. The repository pins PyModbus in `requirements.txt`.

Copy the HTTPS URL from **Code** on this repository’s GitHub page, then run the following with your actual URL and repository folder name.

```sh
git clone <REPOSITORY_URL>
cd <REPOSITORY_FOLDER>
```

Run the commands below from the folder containing `grade_a.py` and `requirements.txt`. The simulator script must be available at `simulator/plug_and_produce_simulation.py`. If the repository does not include it, obtain an authorized copy from the course or its provider and place it at that path.

### Windows (PowerShell)

In the first terminal, create the environment, install the dependency, and start the simulator.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe simulator/plug_and_produce_simulation.py
```

Keep the simulator open. In a second terminal at the same project folder, start the HMI.

```powershell
.\.venv\Scripts\python.exe grade_a.py
```

### macOS and Linux

In the first terminal:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python simulator/plug_and_produce_simulation.py
```

In the second terminal:

```sh
.venv/bin/python grade_a.py
```

The controller defaults to `127.0.0.1:502`. Use the port displayed by the simulator. If it shows `5020` or another port, update `PORT` in [core/settings.py](core/settings.py) and restart the controller. Run one controller at a time.

## Try automatic production

1. Click **Reset** in the simulator.
2. Click **Generate** once under each source.
3. In the HMI, load [recipes/production.json](recipes/production.json), then click **Run FULL PRODUCTION (Grade A)**. Choose a filename when prompted to save the configuration.
4. Watch the crane handle both routes. With exactly two generated parts and a successful run, the simulator should show **2 delivered, 0 scrap, and 0 collisions**.
5. Open the new CSV in `logs/`. Each row includes the controller’s product ID, timestamp, actual X and Y, and vacuum state. The simulator event log shows which processing route each delivered part followed.

You can generate additional parts at either source when it becomes free while production is running. A batch ends once both sources and both tracked process jobs are empty.

## Teach and replay a recipe

With the simulator reset and empty, select a station in the HMI and enter its target coordinates. For Source 1, use **X = 55** and **Y = 82**. Click **Move crane NOW**, wait for arrival, then click **Teach selected from crane**. The HMI reads the actual coordinates and updates the selected station’s saved position.

Use **Add target movement to recipe** to append lift, travel, and lower steps. Use the vacuum, process, and sensor-wait buttons to append operations. **Save JSON** writes the positions and action list to disk. **Load JSON** opens the saved recipe, and **Run saved sequence** saves and executes its action list.

For a ready-to-run example, load [recipes/grade_d.json](recipes/grade_d.json), reset the simulator, and generate one part at Source 1. Click **Run saved sequence** and save a copy when prompted. The part should go through Process 1 and reach the sink.

**Run saved sequence** follows the visible `actions` list. **Run FULL PRODUCTION** uses the saved positions and `transfer` template. Its scheduler picks the next eligible move using source sensors, process signals, and station availability. An empty `actions` list is valid for automatic production.

## How the controller works

- **Movement.** The controller lifts to a travel height before moving sideways. It reads actual position registers to check arrival at each waypoint.
- **Processing.** The controller starts a station and checks its running signal. In automatic production, it can use the crane for another eligible transfer while a station processes a part.
- **Logging.** The CSV tracker records pickup, carried movement, and release. A product keeps its controller ID throughout the route, even if that ID differs from the simulator’s generation ID.

## Project layout

| File or folder | Purpose |
| --- | --- |
| `grade_a.py` | Launch the Tkinter operator interface |
| `grade_b.py` through `grade_e.py` | Command-line demos for the earlier project stages |
| `core/settings.py`, `core/modbus_io.py` | Connection settings, register map, and Modbus reads and writes |
| `core/crane_motion.py`, `core/process_control.py` | Movement, vacuum commands, and process completion |
| `core/recipe_engine.py`, `core/production_scheduler.py` | JSON execution and automatic scheduling |
| `core/hmi.py`, `core/product_logging.py` | Operator controls and CSV tracking |
| `recipes/` | Example recipes and the automatic production configuration |
| `simulator/`, `logs/` | Simulator script and generated run logs |

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| The HMI cannot connect | Start the simulator first and match the port in `core/settings.py` to the simulator’s display. |
| Python cannot import `tkinter` | Use a Python installation with Tk support. On Linux, install the Tk package for your distribution and Python version. |
| The crane is still while a recipe is running | Check the HMI’s current instruction. A source-wait action needs a part at the named source. |
| The sequence list is empty | Load a recipe with an `actions` list, such as `recipes/grade_d.json`. The production configuration uses the automatic scheduler. |

## Credits

The Plug & Produce simulator was supplied for the PFA600 course. The controller, recipe tools, and operator interface are the project’s implementation.
