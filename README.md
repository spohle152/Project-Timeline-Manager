# Project Manager

A lightweight, local project-management app for organizing projects, tasks, statuses, dates, and custom attributes. It runs as a desktop window with pywebview, stores its data in SQLite, and can generate PDF task reports and PNG timeline charts.

## Features

- Create and manage multiple projects
- Track tasks with descriptions, start and end dates, and statuses
- Define color-coded statuses and reorder them by priority
- Create custom attribute types and values
- Share attribute types across every project or keep them project-specific
- Export a project's tasks as a formatted PDF report
- Export Gantt-style timeline charts grouped by a selected attribute type
- Store all project data locally without an external database server

## Requirements

- Python 3.9 or newer
- macOS for the intended desktop experience and automatic opening of exports

The app can also run in a regular browser if pywebview is not installed, although generated files are currently opened with the macOS `open` command.

## Installation

1. Clone or download this project and open a terminal in its directory.

2. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Running the App

Start the application with:

```bash
python3 main.py
```

When pywebview is available, Project Manager opens in its own desktop window. If pywebview cannot be imported, the Flask development server starts instead; open [http://127.0.0.1:5050](http://127.0.0.1:5050) in a browser.

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
