# Project Manager

A lightweight, local project-management app for organizing projects, tasks, statuses, dates, and custom attributes. It runs as a desktop window with pywebview, stores its data in SQLite, and can generate PDF task reports and PNG timeline charts.

## Features

- Create and manage multiple projects
- Track tasks with descriptions, start and end dates, and statuses
- Define color-coded statuses and reorder them by priority
- Create custom attribute types and values
- Share attribute types across every project or keep them project-specific
- Export a project's tasks as a formatted PDF report, choosing where to save it
- Export Gantt-style timeline charts grouped by a selected attribute type, at any resolution or aspect ratio you choose (e.g. 16:9, 4:3, or a custom size), and choose the save location
- Store all project data locally without an external database server

## Requirements

- Python 3.9 or newer
- macOS, Windows, or Linux

Generated PDF and PNG exports are opened automatically with the operating system's default viewer (`open` on macOS, `os.startfile` on Windows, `xdg-open` on Linux).

**Linux only:** pywebview needs a GUI toolkit binding to render its native window. `requirements.txt` pulls in `pywebview[gtk]`, but the underlying system packages still need to be installed separately, e.g. on Debian/Ubuntu:

```bash
sudo apt install gir1.2-gtk-3.0 gir1.2-webkit2-4.0 python3-gi
```

If those packages aren't available, the app automatically falls back to browser mode (see below).

## Installation and Running (one step)

Clone or download this project, then run the launcher for your OS from the project directory:

| OS | Launcher |
| --- | --- |
| macOS | Double-click `run.command` (or run `./run.command` in a terminal) |
| Linux | Run `./run.sh` in a terminal (double-click may work too, depending on your file manager's settings) |
| Windows | Double-click `run.bat` |

The first run creates a local virtual environment (`.venv`) and installs dependencies automatically — this can take a minute the first time, and is instant on later runs. The app then opens as described below. If Python 3 isn't installed, the launcher tells you where to get it instead of failing silently.

### Manual installation

If you'd rather manage the environment yourself:

```bash
python3 -m venv .venv          # Windows: python -m venv .venv
source .venv/bin/activate      # Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python3 main.py                # Windows: python main.py
```

## Running the App

When pywebview is available and able to open a native window, Project Manager opens in its own desktop window. If pywebview isn't installed, or its native window fails to start (most commonly missing GTK packages on Linux), the Flask development server starts instead; open [http://127.0.0.1:5050](http://127.0.0.1:5050) in a browser.

## Using Project Manager

1. Create a project from the project selector in the sidebar.
2. Add statuses such as `Planned`, `In Progress`, and `Complete`. Drag statuses to set their priority order.
3. Add attribute types such as `Owner`, `Department`, or `Phase`, then add values under each type.
4. Create tasks and assign dates, a status, and any relevant attributes.
5. Open the Export page to create a PDF task report or a PNG timeline.

Global attribute types are available in every project. Project-specific attribute types are available only in the project where they were created. A timeline grouped by a global attribute type can include matching tasks from all projects.

## Data and Exports

Application data is stored in:

```text
project_manager.db
```

Generated reports and timeline images are saved in:

```text
exports/
```

Back up `project_manager.db` to preserve your projects and tasks. Deleting a project permanently deletes its associated tasks and statuses. Deleting an attribute type also removes its attributes from tasks.

## Project Structure

```text
.
├── main.py                 # Flask API, desktop window, and application entry point
├── database.py             # SQLite schema, migrations, and data-access functions
├── pdf_export.py           # PDF task-report generation
├── timeline_export.py      # PNG timeline-chart generation
├── requirements.txt        # Python dependencies
├── run.command             # One-click setup + launch (macOS)
├── run.sh                  # One-click setup + launch (Linux)
├── run.bat                 # One-click setup + launch (Windows)
├── templates/
│   └── index.html          # Main application page
├── static/
│   ├── app.js              # Frontend state, rendering, and API calls
│   └── style.css           # Application styles
├── exports/                # Generated PDF and PNG files
└── project_manager.db      # Local SQLite database, created automatically
```

## Technology

- Flask for the local web server and JSON API
- pywebview for the desktop application window
- SQLite for local persistence
- Vanilla HTML, CSS, and JavaScript for the interface
- ReportLab for PDF reports
- Matplotlib and Pillow for timeline image exports

## Development

The database schema is initialized automatically when `main.py` starts. The Flask server listens on `127.0.0.1:5050` and is intended for local use only.

To reset the application completely, stop it and remove `project_manager.db`. A new empty database will be created the next time the app starts. This permanently removes existing project data, so make a backup first.
