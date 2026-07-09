import os
import platform
import subprocess
import threading
import time
from datetime import datetime

from flask import Flask, jsonify, request, render_template

import database as db
from pdf_export import export_pdf
from timeline_export import export_timeline

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORTS_DIR = os.path.join(BASE_DIR, 'exports')
# System.Drawing.Icon (used by pywebview's Windows backend) requires a real
# .ico file — a .png there raises an exception and crashes startup.
APP_ICON = os.path.join(
    BASE_DIR, 'static', 'images',
    'app-icon.ico' if platform.system() == 'Windows' else 'app-icon.png'
)
os.makedirs(EXPORTS_DIR, exist_ok=True)

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static'),
)
app.config['SECRET_KEY'] = 'pm-secret-key'


def open_file(path):
    system = platform.system()
    if system == 'Darwin':
        subprocess.Popen(['open', path])
    elif system == 'Windows':
        os.startfile(path)
    else:
        subprocess.Popen(['xdg-open', path])


class Api:
    """Exposed to the frontend as window.pywebview.api.* — only reachable
    when running inside the native pywebview window, not browser fallback."""

    def save_dialog(self, default_filename, file_types=None):
        import webview
        if not webview.windows:
            return None
        window = webview.windows[0]
        file_dialog_enum = getattr(webview, 'FileDialog', None)
        dialog_type = file_dialog_enum.SAVE if file_dialog_enum else webview.SAVE_DIALOG
        result = window.create_file_dialog(
            dialog_type,
            directory=EXPORTS_DIR,
            save_filename=default_filename,
            file_types=tuple(file_types) if file_types else (),
        )
        if not result:
            return None
        return result[0] if isinstance(result, (list, tuple)) else result


# ── Main page ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# ── Projects ──────────────────────────────────────────────────────────────────

@app.route('/api/projects', methods=['GET'])
def list_projects():
    return jsonify(db.get_projects())


@app.route('/api/projects', methods=['POST'])
def create_project():
    data = request.json
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    new_id = db.create_project(name, data.get('description', ''))
    return jsonify({'id': new_id, 'name': name}), 201


@app.route('/api/projects/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    data = request.json
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    db.update_project(project_id, name, data.get('description', ''))
    return jsonify({'ok': True})


@app.route('/api/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    db.delete_project(project_id)
    return jsonify({'ok': True})


# ── Attribute Types ───────────────────────────────────────────────────────────

@app.route('/api/attribute-types', methods=['GET'])
def list_attribute_types():
    project_id = request.args.get('project_id', type=int)
    return jsonify(db.get_attribute_types(project_id))


@app.route('/api/attribute-types', methods=['POST'])
def create_attribute_type():
    data = request.json
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    is_global = bool(data.get('is_global', False))
    project_id = data.get('project_id') if not is_global else None
    new_id = db.create_attribute_type(name, project_id=project_id, is_global=is_global)
    return jsonify({'id': new_id, 'name': name, 'is_global': is_global}), 201


@app.route('/api/attribute-types/<int:type_id>', methods=['PUT'])
def update_attribute_type(type_id):
    data = request.json
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    is_global = data.get('is_global')
    project_id = data.get('project_id')
    db.update_attribute_type(type_id, name, is_global=is_global, project_id=project_id)
    return jsonify({'ok': True})


@app.route('/api/attribute-types/<int:type_id>', methods=['DELETE'])
def delete_attribute_type(type_id):
    db.delete_attribute_type(type_id)
    return jsonify({'ok': True})


# ── Attributes ────────────────────────────────────────────────────────────────

@app.route('/api/attributes', methods=['GET'])
def list_attributes():
    type_id = request.args.get('type_id')
    return jsonify(db.get_attributes(type_id))


@app.route('/api/attributes', methods=['POST'])
def create_attribute():
    data = request.json
    type_id = data.get('type_id')
    name = (data.get('name') or '').strip()
    if not type_id or not name:
        return jsonify({'error': 'type_id and name required'}), 400
    new_id = db.create_attribute(type_id, name)
    return jsonify({'id': new_id, 'type_id': type_id, 'name': name}), 201


@app.route('/api/attributes/<int:attr_id>', methods=['PUT'])
def update_attribute(attr_id):
    data = request.json
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    db.update_attribute(attr_id, name)
    return jsonify({'ok': True})


@app.route('/api/attributes/<int:attr_id>', methods=['DELETE'])
def delete_attribute(attr_id):
    db.delete_attribute(attr_id)
    return jsonify({'ok': True})


# ── Statuses ──────────────────────────────────────────────────────────────────

@app.route('/api/statuses', methods=['GET'])
def list_statuses():
    project_id = request.args.get('project_id', type=int)
    if not project_id:
        return jsonify({'error': 'project_id required'}), 400
    return jsonify(db.get_statuses(project_id))


@app.route('/api/statuses', methods=['POST'])
def create_status():
    data = request.json
    name = (data.get('name') or '').strip()
    color = data.get('color', '#808080')
    project_id = data.get('project_id')
    if not name or not project_id:
        return jsonify({'error': 'name and project_id required'}), 400
    new_id = db.create_status(name, color, project_id)
    return jsonify({'id': new_id, 'name': name, 'color': color}), 201


@app.route('/api/statuses/<int:status_id>', methods=['PUT'])
def update_status(status_id):
    data = request.json
    name = (data.get('name') or '').strip()
    color = data.get('color', '#808080')
    if not name:
        return jsonify({'error': 'Name required'}), 400
    db.update_status(status_id, name, color)
    return jsonify({'ok': True})


@app.route('/api/statuses/<int:status_id>', methods=['DELETE'])
def delete_status(status_id):
    db.delete_status(status_id)
    return jsonify({'ok': True})


@app.route('/api/statuses/reorder', methods=['PUT'])
def reorder_statuses():
    data = request.json
    db.reorder_statuses(data.get('ordered_ids', []))
    return jsonify({'ok': True})


# ── Tasks ─────────────────────────────────────────────────────────────────────

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    project_id = request.args.get('project_id', type=int)
    return jsonify(db.get_tasks(project_id))


@app.route('/api/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    task = db.get_task(task_id)
    if not task:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(task)


@app.route('/api/tasks', methods=['POST'])
def create_task():
    data = request.json
    name = (data.get('name') or '').strip()
    project_id = data.get('project_id')
    if not name or not project_id:
        return jsonify({'error': 'name and project_id required'}), 400
    new_id = db.create_task(
        name=name,
        description=data.get('description', ''),
        start_date=data.get('start_date'),
        end_date=data.get('end_date'),
        status_id=data.get('status_id'),
        attribute_ids=data.get('attribute_ids', []),
        project_id=project_id,
    )
    return jsonify({'id': new_id}), 201


@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    data = request.json
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    db.update_task(
        task_id=task_id,
        name=name,
        description=data.get('description', ''),
        start_date=data.get('start_date'),
        end_date=data.get('end_date'),
        status_id=data.get('status_id'),
        attribute_ids=data.get('attribute_ids', []),
    )
    return jsonify({'ok': True})


@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    db.delete_task(task_id)
    return jsonify({'ok': True})


# ── Subtasks (checklist items) ──────────────────────────────────────────────

@app.route('/api/tasks/<int:task_id>/subtasks', methods=['POST'])
def create_subtask(task_id):
    data = request.json
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    new_id = db.create_subtask(task_id, name)
    return jsonify({'id': new_id, 'name': name, 'is_done': 0}), 201


@app.route('/api/subtasks/<int:subtask_id>', methods=['PUT'])
def update_subtask(subtask_id):
    data = request.json
    name = data.get('name')
    if name is not None:
        name = name.strip()
        if not name:
            return jsonify({'error': 'Name required'}), 400
    db.update_subtask(subtask_id, name=name, is_done=data.get('is_done'))
    return jsonify({'ok': True})


@app.route('/api/subtasks/<int:subtask_id>', methods=['DELETE'])
def delete_subtask(subtask_id):
    db.delete_subtask(subtask_id)
    return jsonify({'ok': True})


# ── Exports ───────────────────────────────────────────────────────────────────

def _resolve_export_path(save_path, default_prefix, extension):
    """save_path comes from the native save dialog (desktop mode) and is
    trusted, absolute, user-chosen input. Without it, fall back to the
    auto-named exports/ folder used by browser-fallback mode."""
    if save_path:
        path = save_path
        if not path.lower().endswith(extension):
            path += extension
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        return path
    filename = f'{default_prefix}_{datetime.now().strftime("%Y%m%d_%H%M%S")}{extension}'
    return os.path.join(EXPORTS_DIR, filename)


@app.route('/api/export/pdf', methods=['POST'])
def export_pdf_route():
    data = request.json or {}
    project_id = data.get('project_id')
    project_name = data.get('project_name', 'Project')
    tasks = db.get_tasks(project_id)
    path = _resolve_export_path(data.get('save_path'), 'tasks', '.pdf')
    export_pdf(tasks, path, project_name=project_name)
    open_file(path)
    return jsonify({'ok': True, 'filename': os.path.basename(path), 'path': path})


@app.route('/api/export/timeline', methods=['POST'])
def export_timeline_route():
    data = request.json
    range_start = data.get('start_date')
    range_end = data.get('end_date')
    attr_type_id = data.get('attribute_type_id')
    attr_type_name = data.get('attribute_type_name', 'Attribute')
    project_id = data.get('project_id')
    is_global = data.get('is_global', False)

    if not range_start or not range_end or not attr_type_id:
        return jsonify({'error': 'start_date, end_date, and attribute_type_id required'}), 400

    def _clamped_int(value, default, lo, hi):
        try:
            return max(lo, min(int(value), hi))
        except (TypeError, ValueError):
            return default

    dpi = _clamped_int(data.get('dpi'), 150, 72, 600)
    target_width = _clamped_int(data.get('width'), None, 200, 6000) if data.get('width') else None
    target_height = _clamped_int(data.get('height'), None, 200, 6000) if data.get('height') else None

    # Global attribute type: show all projects' tasks
    tasks = db.get_tasks(None if is_global else project_id)

    path = _resolve_export_path(data.get('save_path'), 'timeline', '.png')

    try:
        export_timeline(
            tasks, attr_type_id, attr_type_name, range_start, range_end, path,
            dpi=dpi, target_width=target_width, target_height=target_height,
            current_project_id=project_id, highlight_other_projects=is_global,
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    open_file(path)
    return jsonify({'ok': True, 'filename': os.path.basename(path), 'path': path})


# ── Entry point ───────────────────────────────────────────────────────────────

def run_flask():
    app.run(host='127.0.0.1', port=5050, debug=False, use_reloader=False)


def main():
    db.init_db()
    try:
        import webview
    except ImportError:
        webview = None

    if webview is None:
        print('pywebview not found — running as web server.')
        print('Open http://127.0.0.1:5050 in your browser.')
        app.run(host='127.0.0.1', port=5050, debug=True)
        return

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(0.8)

    try:
        webview.create_window(
            'Project Manager',
            'http://127.0.0.1:5050',
            width=1400,
            height=900,
            min_size=(900, 600),
            js_api=Api(),
        )
        webview.start(debug=False, icon=APP_ICON)
    except Exception as e:
        # On Linux this usually means no GTK/QT webview backend is
        # installed; rather than crash, fall back to the already-running
        # Flask server that flask_thread started above.
        print(f'pywebview could not open a native window ({e}).')
        print('Falling back to browser mode — open http://127.0.0.1:5050 in your browser.')
        flask_thread.join()


if __name__ == '__main__':
    main()
