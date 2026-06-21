import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'project_manager.db')


def init_db():
    with get_db() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS attribute_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                display_order INTEGER DEFAULT 0,
                project_id INTEGER,
                is_global INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS attributes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                display_order INTEGER DEFAULT 0,
                FOREIGN KEY (type_id) REFERENCES attribute_types(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS status_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                color TEXT NOT NULL DEFAULT '#808080',
                priority_rank INTEGER NOT NULL DEFAULT 0,
                project_id INTEGER,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                start_date TEXT,
                end_date TEXT,
                status_id INTEGER,
                project_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (status_id) REFERENCES status_states(id) ON DELETE SET NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS task_attributes (
                task_id INTEGER NOT NULL,
                attribute_id INTEGER NOT NULL,
                PRIMARY KEY (task_id, attribute_id),
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (attribute_id) REFERENCES attributes(id) ON DELETE CASCADE
            );
        ''')
        _migrate(db)


def _migrate(db):
    """Add columns introduced by the multi-project update to existing databases."""
    migrations = [
        "ALTER TABLE attribute_types ADD COLUMN project_id INTEGER",
        "ALTER TABLE attribute_types ADD COLUMN is_global INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE status_states ADD COLUMN project_id INTEGER",
        "ALTER TABLE tasks ADD COLUMN project_id INTEGER",
    ]
    for sql in migrations:
        try:
            db.execute(sql)
        except Exception:
            pass  # column already exists

    # Pre-existing attribute types (no project) become global so they keep working.
    db.execute(
        "UPDATE attribute_types SET is_global = 1 WHERE project_id IS NULL AND is_global = 0"
    )

    # Pre-existing tasks and statuses are migrated to a default project.
    orphaned_tasks = db.execute(
        "SELECT COUNT(*) FROM tasks WHERE project_id IS NULL"
    ).fetchone()[0]
    orphaned_statuses = db.execute(
        "SELECT COUNT(*) FROM status_states WHERE project_id IS NULL"
    ).fetchone()[0]

    if orphaned_tasks > 0 or orphaned_statuses > 0:
        row = db.execute(
            "SELECT id FROM projects WHERE name = 'Main Project' LIMIT 1"
        ).fetchone()
        if row:
            default_id = row[0]
        else:
            cur = db.execute(
                "INSERT INTO projects (name, description) VALUES ('Main Project', '')"
            )
            default_id = cur.lastrowid
        db.execute("UPDATE tasks SET project_id = ? WHERE project_id IS NULL", (default_id,))
        db.execute("UPDATE status_states SET project_id = ? WHERE project_id IS NULL", (default_id,))


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Projects ──────────────────────────────────────────────────────────────────

def get_projects():
    with get_db() as db:
        rows = db.execute('SELECT * FROM projects ORDER BY name').fetchall()
        return [dict(r) for r in rows]


def create_project(name, description=''):
    with get_db() as db:
        cur = db.execute(
            'INSERT INTO projects (name, description) VALUES (?, ?)',
            (name, description)
        )
        return cur.lastrowid


def update_project(project_id, name, description=''):
    with get_db() as db:
        db.execute(
            'UPDATE projects SET name = ?, description = ? WHERE id = ?',
            (name, description, project_id)
        )


def delete_project(project_id):
    with get_db() as db:
        db.execute('DELETE FROM projects WHERE id = ?', (project_id,))


# ── Attribute Types ───────────────────────────────────────────────────────────

def get_attribute_types(project_id=None):
    """Return global types plus any types specific to project_id."""
    with get_db() as db:
        if project_id is not None:
            rows = db.execute(
                '''SELECT * FROM attribute_types
                   WHERE is_global = 1 OR project_id = ?
                   ORDER BY is_global DESC, display_order, id''',
                (project_id,)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT * FROM attribute_types ORDER BY is_global DESC, display_order, id'
            ).fetchall()
        return [dict(r) for r in rows]


def create_attribute_type(name, project_id=None, is_global=False):
    with get_db() as db:
        cur = db.execute(
            'SELECT COALESCE(MAX(display_order), -1) + 1 FROM attribute_types'
        )
        order = cur.fetchone()[0]
        cur = db.execute(
            '''INSERT INTO attribute_types (name, display_order, project_id, is_global)
               VALUES (?, ?, ?, ?)''',
            (name, order, None if is_global else project_id, 1 if is_global else 0)
        )
        return cur.lastrowid


def update_attribute_type(type_id, name, is_global=None, project_id=None):
    with get_db() as db:
        if is_global is not None:
            # When making global: clear project_id. When making project-specific: assign project_id.
            resolved_project_id = None if is_global else project_id
            db.execute(
                'UPDATE attribute_types SET name = ?, is_global = ?, project_id = ? WHERE id = ?',
                (name, 1 if is_global else 0, resolved_project_id, type_id)
            )
        else:
            db.execute(
                'UPDATE attribute_types SET name = ? WHERE id = ?', (name, type_id)
            )


def delete_attribute_type(type_id):
    with get_db() as db:
        db.execute('DELETE FROM attribute_types WHERE id = ?', (type_id,))


# ── Attributes ────────────────────────────────────────────────────────────────

def get_attributes(type_id=None):
    with get_db() as db:
        if type_id:
            rows = db.execute(
                'SELECT * FROM attributes WHERE type_id = ? ORDER BY display_order, id',
                (type_id,)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT * FROM attributes ORDER BY type_id, display_order, id'
            ).fetchall()
        return [dict(r) for r in rows]


def create_attribute(type_id, name):
    with get_db() as db:
        cur = db.execute(
            'SELECT COALESCE(MAX(display_order), -1) + 1 FROM attributes WHERE type_id = ?',
            (type_id,)
        )
        order = cur.fetchone()[0]
        cur = db.execute(
            'INSERT INTO attributes (type_id, name, display_order) VALUES (?, ?, ?)',
            (type_id, name, order)
        )
        return cur.lastrowid


def update_attribute(attr_id, name):
    with get_db() as db:
        db.execute('UPDATE attributes SET name = ? WHERE id = ?', (name, attr_id))


def delete_attribute(attr_id):
    with get_db() as db:
        db.execute('DELETE FROM attributes WHERE id = ?', (attr_id,))


# ── Status States ─────────────────────────────────────────────────────────────

def get_statuses(project_id):
    with get_db() as db:
        rows = db.execute(
            'SELECT * FROM status_states WHERE project_id = ? ORDER BY priority_rank',
            (project_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def create_status(name, color='#808080', project_id=None):
    with get_db() as db:
        cur = db.execute(
            'SELECT COALESCE(MAX(priority_rank), -1) + 1 FROM status_states WHERE project_id = ?',
            (project_id,)
        )
        rank = cur.fetchone()[0]
        cur = db.execute(
            'INSERT INTO status_states (name, color, priority_rank, project_id) VALUES (?, ?, ?, ?)',
            (name, color, rank, project_id)
        )
        return cur.lastrowid


def update_status(status_id, name, color):
    with get_db() as db:
        db.execute(
            'UPDATE status_states SET name = ?, color = ? WHERE id = ?',
            (name, color, status_id)
        )


def delete_status(status_id):
    with get_db() as db:
        db.execute('DELETE FROM status_states WHERE id = ?', (status_id,))


def reorder_statuses(ordered_ids):
    with get_db() as db:
        for rank, sid in enumerate(ordered_ids):
            db.execute(
                'UPDATE status_states SET priority_rank = ? WHERE id = ?', (rank, sid)
            )


# ── Tasks ─────────────────────────────────────────────────────────────────────

def _attach_attrs(db, tasks):
    result = []
    for task in tasks:
        t = dict(task)
        attrs = db.execute(
            '''SELECT a.id, a.name, a.type_id, at.name as type_name
               FROM task_attributes ta
               JOIN attributes a ON ta.attribute_id = a.id
               JOIN attribute_types at ON a.type_id = at.id
               WHERE ta.task_id = ?
               ORDER BY at.display_order, a.display_order''',
            (t['id'],)
        ).fetchall()
        t['attributes'] = [dict(a) for a in attrs]
        result.append(t)
    return result


def get_tasks(project_id=None):
    with get_db() as db:
        if project_id is not None:
            tasks = db.execute(
                '''SELECT t.*, s.name as status_name, s.color as status_color,
                          s.priority_rank as status_priority
                   FROM tasks t
                   LEFT JOIN status_states s ON t.status_id = s.id
                   WHERE t.project_id = ?
                   ORDER BY COALESCE(s.priority_rank, 9999),
                            COALESCE(t.start_date, '9999-99-99'), t.id''',
                (project_id,)
            ).fetchall()
        else:
            tasks = db.execute(
                '''SELECT t.*, s.name as status_name, s.color as status_color,
                          s.priority_rank as status_priority,
                          p.name as project_name
                   FROM tasks t
                   LEFT JOIN status_states s ON t.status_id = s.id
                   LEFT JOIN projects p ON t.project_id = p.id
                   ORDER BY COALESCE(s.priority_rank, 9999),
                            COALESCE(t.start_date, '9999-99-99'), t.id'''
            ).fetchall()
        return _attach_attrs(db, tasks)


def get_task(task_id):
    with get_db() as db:
        task = db.execute(
            '''SELECT t.*, s.name as status_name, s.color as status_color
               FROM tasks t
               LEFT JOIN status_states s ON t.status_id = s.id
               WHERE t.id = ?''',
            (task_id,)
        ).fetchone()
        if not task:
            return None
        t = dict(task)
        attrs = db.execute(
            '''SELECT a.id, a.name, a.type_id, at.name as type_name
               FROM task_attributes ta
               JOIN attributes a ON ta.attribute_id = a.id
               JOIN attribute_types at ON a.type_id = at.id
               WHERE ta.task_id = ?''',
            (task_id,)
        ).fetchall()
        t['attributes'] = [dict(a) for a in attrs]
        return t


def create_task(name, description, start_date, end_date, status_id, attribute_ids, project_id):
    with get_db() as db:
        cur = db.execute(
            '''INSERT INTO tasks (name, description, start_date, end_date, status_id, project_id)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (name, description, start_date, end_date, status_id, project_id)
        )
        task_id = cur.lastrowid
        for attr_id in attribute_ids:
            db.execute(
                'INSERT OR IGNORE INTO task_attributes (task_id, attribute_id) VALUES (?, ?)',
                (task_id, attr_id)
            )
        return task_id


def update_task(task_id, name, description, start_date, end_date, status_id, attribute_ids):
    with get_db() as db:
        db.execute(
            '''UPDATE tasks SET name = ?, description = ?, start_date = ?,
               end_date = ?, status_id = ? WHERE id = ?''',
            (name, description, start_date, end_date, status_id, task_id)
        )
        db.execute('DELETE FROM task_attributes WHERE task_id = ?', (task_id,))
        for attr_id in attribute_ids:
            db.execute(
                'INSERT OR IGNORE INTO task_attributes (task_id, attribute_id) VALUES (?, ?)',
                (task_id, attr_id)
            )


def delete_task(task_id):
    with get_db() as db:
        db.execute('DELETE FROM tasks WHERE id = ?', (task_id,))


def get_attribute_type(type_id):
    with get_db() as db:
        row = db.execute(
            'SELECT * FROM attribute_types WHERE id = ?', (type_id,)
        ).fetchone()
        return dict(row) if row else None
