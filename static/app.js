// ── State ─────────────────────────────────────────────────────────────────────

const S = {
  page: 'tasks',
  projects: [],
  currentProjectId: null,
  currentProject: null,
  tasks: [],
  statuses: [],
  attrTypes: [],   // global + project-specific for current project
  attrs: [],
};

// ── API ───────────────────────────────────────────────────────────────────────

async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

async function loadProjectData() {
  if (!S.currentProjectId) return;
  const pid = S.currentProjectId;
  const [tasks, statuses, attrTypes, attrs] = await Promise.all([
    api('GET', `/api/tasks?project_id=${pid}`),
    api('GET', `/api/statuses?project_id=${pid}`),
    api('GET', `/api/attribute-types?project_id=${pid}`),
    api('GET', '/api/attributes'),
  ]);
  S.tasks = tasks;
  S.statuses = statuses;
  S.attrTypes = attrTypes;
  S.attrs = attrs;
}

// ── Native save dialog (desktop app mode only) ──────────────────────────────────

// window.pywebview is injected by the desktop shell once its JS bridge is
// ready; it's never present when running as a plain browser fallback.
window.addEventListener('pywebviewready', () => {
  if (S.page === 'export') renderPage();
});

function hasNativeSaveDialog() {
  return !!(window.pywebview && window.pywebview.api && window.pywebview.api.save_dialog);
}

async function nativeSaveDialog(defaultFilename, fileTypes) {
  if (!hasNativeSaveDialog()) return null;
  try {
    return await window.pywebview.api.save_dialog(defaultFilename, fileTypes || []);
  } catch (e) {
    console.error('save_dialog failed', e);
    return null;
  }
}

// ── Toast ─────────────────────────────────────────────────────────────────────

function toast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast show' + (type ? ` ${type}` : '');
  clearTimeout(el._t);
  el._t = setTimeout(() => { el.className = 'toast'; }, 3000);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function durationLabel(start, end) {
  if (!start || !end) return '';
  const s = new Date(start + 'T00:00:00');
  const e = new Date(end + 'T00:00:00');
  const days = Math.round((e - s) / 86400000) + 1;
  if (days <= 0) return '';
  if (days === 1) return '1 day';
  if (days < 7) return `${days} days`;
  const weeks = Math.floor(days / 7), rem = days % 7;
  let out = `${weeks} week${weeks > 1 ? 's' : ''}`;
  if (rem) out += `, ${rem} day${rem > 1 ? 's' : ''}`;
  return out;
}

function formatDate(d) {
  if (!d) return '';
  const [y, m, day] = d.split('-');
  return `${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+m-1]} ${+day}, ${y}`;
}

function groupAttrs(attributes) {
  const map = {};
  for (const a of attributes) {
    const t = a.type_name || 'Uncategorized';
    if (!map[t]) map[t] = [];
    map[t].push(a.name);
  }
  return map;
}

// ── Boot ──────────────────────────────────────────────────────────────────────

async function boot() {
  S.projects = await api('GET', '/api/projects');
  updateProjectSelector();

  if (S.projects.length === 0) {
    renderNoProjects();
    return;
  }

  const savedId = parseInt(localStorage.getItem('pm_project_id') || '0');
  const found = S.projects.find(p => p.id === savedId);
  S.currentProjectId = found ? savedId : S.projects[0].id;
  S.currentProject = S.projects.find(p => p.id === S.currentProjectId);
  updateProjectSelector();

  await loadProjectData();
  renderPage();
}

function renderNoProjects() {
  document.getElementById('content').innerHTML = `
    <div class="welcome-screen">
      <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#cbd5e0" stroke-width="1.5">
        <path d="M3 7a2 2 0 0 1 2-2h3l2 3h9a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
      </svg>
      <h2>Welcome to Project Manager</h2>
      <p>Create your first project to get started tracking tasks and timelines.</p>
      <button class="btn btn-primary" onclick="openNewProjectModal()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>Create First Project
      </button>
    </div>`;
}

// ── Navigation ────────────────────────────────────────────────────────────────

function navigate(page) {
  S.page = page;
  document.querySelectorAll('.nav-link').forEach(l =>
    l.classList.toggle('active', l.dataset.page === page)
  );
  renderPage();
}

async function renderPage() {
  if (!S.currentProjectId) { renderNoProjects(); return; }
  await loadProjectData();
  const el = document.getElementById('content');
  switch (S.page) {
    case 'tasks':      el.innerHTML = renderTasksPage();      bindTasksPage(); break;
    case 'statuses':   el.innerHTML = renderStatusesPage();   bindStatusesPage(); break;
    case 'attributes': el.innerHTML = renderAttributesPage(); break;
    case 'export':     el.innerHTML = renderExportPage();     bindExportPage(); break;
  }
}

// ── Project selector ──────────────────────────────────────────────────────────

function updateProjectSelector() {
  const label = document.getElementById('current-project-label');
  if (label) label.textContent = S.currentProject?.name || 'No Project';

  const list = document.getElementById('project-menu-list');
  if (!list) return;
  list.innerHTML = S.projects.map(p => `
    <button class="project-menu-item ${p.id === S.currentProjectId ? 'active' : ''}"
            onclick="selectProject(${p.id})">
      <span class="check-icon">
        ${p.id === S.currentProjectId
          ? '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>'
          : ''}
      </span>
      ${escHtml(p.name)}
    </button>`).join('');
}

function toggleProjectMenu(e) {
  e.stopPropagation();
  const menu = document.getElementById('project-menu');
  const isOpen = menu.style.display !== 'none';
  menu.style.display = isOpen ? 'none' : 'block';
  updateProjectSelector();
}

document.addEventListener('click', () => {
  const menu = document.getElementById('project-menu');
  if (menu) menu.style.display = 'none';
});

async function selectProject(id) {
  document.getElementById('project-menu').style.display = 'none';
  S.currentProjectId = id;
  S.currentProject = S.projects.find(p => p.id === id);
  localStorage.setItem('pm_project_id', id);
  updateProjectSelector();
  await renderPage();
}

// ── Project modals ────────────────────────────────────────────────────────────

function openNewProjectModal() {
  document.getElementById('project-edit-id').value = '';
  document.getElementById('project-modal-name').value = '';
  document.getElementById('project-modal-desc').value = '';
  document.getElementById('project-modal-title').textContent = 'New Project';
  document.getElementById('project-modal-delete').style.display = 'none';
  document.getElementById('project-modal').classList.add('open');
  setTimeout(() => document.getElementById('project-modal-name').focus(), 50);
}

function openEditProjectModal(project) {
  document.getElementById('project-edit-id').value = project.id;
  document.getElementById('project-modal-name').value = project.name;
  document.getElementById('project-modal-desc').value = project.description || '';
  document.getElementById('project-modal-title').textContent = 'Edit Project';
  document.getElementById('project-modal-delete').style.display = 'inline-flex';
  document.getElementById('project-modal').classList.add('open');
  setTimeout(() => document.getElementById('project-modal-name').focus(), 50);
}

function closeProjectModal() {
  document.getElementById('project-modal').classList.remove('open');
}

async function saveProject() {
  const id = document.getElementById('project-edit-id').value;
  const name = document.getElementById('project-modal-name').value.trim();
  const desc = document.getElementById('project-modal-desc').value.trim();
  if (!name) { toast('Project name is required', 'error'); return; }
  try {
    if (id) {
      await api('PUT', `/api/projects/${id}`, { name, description: desc });
      toast('Project updated', 'success');
    } else {
      const res = await api('POST', '/api/projects', { name, description: desc });
      S.currentProjectId = res.id;
      localStorage.setItem('pm_project_id', res.id);
      toast('Project created', 'success');
    }
    closeProjectModal();
    S.projects = await api('GET', '/api/projects');
    S.currentProject = S.projects.find(p => p.id === S.currentProjectId);
    updateProjectSelector();
    if (document.getElementById('manage-projects-modal').classList.contains('open')) {
      renderManageProjectsList();
    }
    await renderPage();
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function deleteProjectFromModal() {
  const id = document.getElementById('project-edit-id').value;
  if (!id) return;
  const proj = S.projects.find(p => p.id === parseInt(id));
  if (!confirm(`Delete "${proj?.name}"? All tasks and statuses in this project will be permanently deleted.`)) return;
  try {
    await api('DELETE', `/api/projects/${id}`);
    toast('Project deleted');
    closeProjectModal();
    S.projects = await api('GET', '/api/projects');
    if (parseInt(id) === S.currentProjectId) {
      S.currentProjectId = S.projects[0]?.id || null;
      S.currentProject = S.projects[0] || null;
      if (S.currentProjectId) localStorage.setItem('pm_project_id', S.currentProjectId);
      else localStorage.removeItem('pm_project_id');
    }
    updateProjectSelector();
    if (document.getElementById('manage-projects-modal').classList.contains('open')) {
      renderManageProjectsList();
    }
    await renderPage();
  } catch (e) {
    toast(e.message, 'error');
  }
}

function openManageProjectsModal() {
  document.getElementById('project-menu').style.display = 'none';
  renderManageProjectsList();
  document.getElementById('manage-projects-modal').classList.add('open');
}

function closeManageProjectsModal() {
  document.getElementById('manage-projects-modal').classList.remove('open');
}

function renderManageProjectsList() {
  const body = document.getElementById('manage-projects-body');
  if (!body) return;
  if (S.projects.length === 0) {
    body.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:24px 0">No projects yet.</p>';
    return;
  }
  body.innerHTML = S.projects.map(p => `
    <div class="project-list-item">
      <div style="flex:1">
        <div class="project-list-name">${escHtml(p.name)}</div>
        ${p.description ? `<div class="project-list-desc">${escHtml(p.description)}</div>` : ''}
      </div>
      <button class="btn btn-ghost btn-sm" onclick="openEditProjectModal(${JSON.stringify(p).replace(/"/g,'&quot;')})">Edit</button>
    </div>`).join('');
}

// Close modals on overlay click
['project-modal','manage-projects-modal','task-modal'].forEach(id => {
  document.getElementById(id)?.addEventListener('click', function(e) {
    if (e.target === this) {
      this.classList.remove('open');
    }
  });
});

// ── Tasks Page ────────────────────────────────────────────────────────────────

function renderTasksPage() {
  const byStatus = {};
  const statusOrder = [];
  for (const s of S.statuses) {
    byStatus[s.id] = { status: s, tasks: [] };
    statusOrder.push(s.id);
  }
  const noStatus = [];
  for (const task of S.tasks) {
    if (task.status_id && byStatus[task.status_id]) byStatus[task.status_id].tasks.push(task);
    else noStatus.push(task);
  }

  const projectName = S.currentProject?.name || 'Project';
  let html = `
    <div class="page-header">
      <div>
        <div class="page-title">${escHtml(projectName)}</div>
        <div class="page-subtitle">${S.tasks.length} task${S.tasks.length !== 1 ? 's' : ''}</div>
      </div>
      <button class="btn btn-primary" onclick="openTaskModal()">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>New Task
      </button>
    </div>`;

  if (S.tasks.length === 0) {
    html += `<div class="empty-state">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="display:block;margin:0 auto 12px">
        <rect x="3" y="4" width="18" height="18" rx="2"/>
        <line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="12" y2="17"/>
      </svg>
      <p>No tasks yet</p><span>Click "New Task" to get started</span>
    </div>`;
    return html;
  }

  for (const sid of statusOrder) {
    const { status, tasks } = byStatus[sid];
    if (!tasks.length) continue;
    html += `<div class="status-section">
      <div class="status-section-header">
        <div class="status-badge" style="background:${status.color}">
          <div class="status-dot"></div>${escHtml(status.name)}
        </div>
        <span class="status-count">${tasks.length} task${tasks.length !== 1 ? 's' : ''}</span>
      </div>
      ${tasks.map(t => taskCardHtml(t, status.color)).join('')}
    </div>`;
  }
  if (noStatus.length) {
    html += `<div class="status-section">
      <div class="status-section-header">
        <div class="status-badge" style="background:#718096"><div class="status-dot"></div>No Status</div>
        <span class="status-count">${noStatus.length}</span>
      </div>
      ${noStatus.map(t => taskCardHtml(t, '#718096')).join('')}
    </div>`;
  }
  return html;
}

function taskCardHtml(task, color) {
  const grouped = groupAttrs(task.attributes || []);
  const dateRange = (task.start_date || task.end_date)
    ? `${task.start_date ? formatDate(task.start_date) : '?'} → ${task.end_date ? formatDate(task.end_date) : '?'}`
    : '';
  const duration = durationLabel(task.start_date, task.end_date);
  const attrHtml = Object.entries(grouped).map(([type, vals]) => `
    <div class="attr-group">
      <div class="attr-type-label">${escHtml(type)}</div>
      <div class="attr-values">${vals.map(v => `<span class="attr-tag">${escHtml(v)}</span>`).join('')}</div>
    </div>`).join('');
  const subtasks = task.subtasks || [];
  const doneCount = subtasks.filter(s => s.is_done).length;
  const subtaskBadge = subtasks.length
    ? `<div class="subtask-progress">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
        </svg>${doneCount}/${subtasks.length}
      </div>`
    : '';
  return `<div class="task-card" style="border-left-color:${color}" onclick="openTaskModal(${task.id})">
    <div class="task-card-header">
      <div>
        <div class="task-name">${escHtml(task.name)}</div>
        ${task.description ? `<div class="task-description">${escHtml(task.description)}</div>` : ''}
      </div>
    </div>
    <div class="task-meta">
      ${dateRange ? `<div class="task-dates">
        <div class="date-range">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/>
            <line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
          </svg>${dateRange}
        </div>
        ${duration ? `<div class="date-duration">${duration}</div>` : ''}
      </div>` : ''}
      ${attrHtml ? `<div class="task-attrs">${attrHtml}</div>` : ''}
      ${subtaskBadge}
    </div>
  </div>`;
}

function bindTasksPage() {}

// ── Task Modal ────────────────────────────────────────────────────────────────

async function openTaskModal(taskId) {
  const deleteBtn = document.getElementById('modal-delete-btn');
  document.getElementById('task-id').value = '';
  document.getElementById('task-name').value = '';
  document.getElementById('task-description').value = '';
  document.getElementById('task-start').value = '';
  document.getElementById('task-end').value = '';

  const statusSel = document.getElementById('task-status');
  statusSel.innerHTML = '<option value="">— No Status —</option>';
  for (const s of S.statuses) {
    statusSel.innerHTML += `<option value="${s.id}">${escHtml(s.name)}</option>`;
  }

  const attrContainer = document.getElementById('task-attributes-container');
  attrContainer.innerHTML = '';
  for (const type of S.attrTypes) {
    const typeAttrs = S.attrs.filter(a => a.type_id === type.id);
    if (!typeAttrs.length) continue;
    const badge = type.is_global
      ? `<span class="global-badge"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>All Projects</span>`
      : '';
    attrContainer.innerHTML += `
      <div class="attr-type-group">
        <div class="attr-type-group-header" style="display:flex;align-items:center;gap:8px">
          ${escHtml(type.name)} ${badge}
        </div>
        <div class="attr-checkboxes">
          ${typeAttrs.map(a => `
            <label class="attr-checkbox-label">
              <input type="checkbox" class="task-attr-cb" value="${a.id}" data-type-id="${type.id}" />
              ${escHtml(a.name)}
            </label>`).join('')}
        </div>
      </div>`;
  }

  if (taskId) {
    document.getElementById('modal-title').textContent = 'Edit Task';
    deleteBtn.style.display = 'inline-flex';
    try {
      const task = await api('GET', `/api/tasks/${taskId}`);
      document.getElementById('task-id').value = task.id;
      document.getElementById('task-name').value = task.name;
      document.getElementById('task-description').value = task.description || '';
      document.getElementById('task-start').value = task.start_date || '';
      document.getElementById('task-end').value = task.end_date || '';
      if (task.status_id) statusSel.value = task.status_id;
      const attrIds = new Set((task.attributes || []).map(a => a.id));
      document.querySelectorAll('.task-attr-cb').forEach(cb => {
        cb.checked = attrIds.has(parseInt(cb.value));
      });
      renderSubtasksInModal(taskId, task.subtasks || []);
    } catch (e) { toast(e.message, 'error'); return; }
  } else {
    document.getElementById('modal-title').textContent = 'New Task';
    deleteBtn.style.display = 'none';
    renderSubtasksInModal(null, []);
  }

  document.getElementById('task-modal').classList.add('open');
  setTimeout(() => document.getElementById('task-name').focus(), 50);
}

// ── Subtasks (checklist) ─────────────────────────────────────────────────────

function renderSubtasksInModal(taskId, subtasks) {
  const container = document.getElementById('task-subtasks-container');
  if (!taskId) {
    container.innerHTML = `<div class="field-hint">Save the task first to add subtasks.</div>`;
    return;
  }
  const items = subtasks.map(s => `
    <div class="subtask-item">
      <input type="checkbox" ${s.is_done ? 'checked' : ''}
             onchange="toggleSubtask(${taskId}, ${s.id}, this.checked)" />
      <span class="subtask-name${s.is_done ? ' done' : ''}">${escHtml(s.name)}</span>
      <button type="button" class="subtask-delete-btn" onclick="deleteSubtaskItem(${taskId}, ${s.id})" aria-label="Delete subtask">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>`).join('');
  container.innerHTML = `
    <div class="subtask-list">${items}</div>
    <form class="subtask-add-form" onsubmit="event.preventDefault(); addSubtaskItem(${taskId}, this)">
      <input type="text" name="name" placeholder="Add a subtask…" />
      <button type="submit" class="btn btn-ghost">Add</button>
    </form>`;
}

async function refreshSubtasksInModal(taskId) {
  try {
    const task = await api('GET', `/api/tasks/${taskId}`);
    renderSubtasksInModal(taskId, task.subtasks || []);
    const cached = S.tasks.find(t => t.id === taskId);
    if (cached) cached.subtasks = task.subtasks || [];
  } catch (e) { toast(e.message, 'error'); }
}

async function addSubtaskItem(taskId, form) {
  const input = form.elements.name;
  const name = input.value.trim();
  if (!name) return;
  try {
    await api('POST', `/api/tasks/${taskId}/subtasks`, { name });
    input.value = '';
    await refreshSubtasksInModal(taskId);
  } catch (e) { toast(e.message, 'error'); }
}

async function toggleSubtask(taskId, subtaskId, isDone) {
  try {
    await api('PUT', `/api/subtasks/${subtaskId}`, { is_done: isDone });
    await refreshSubtasksInModal(taskId);
  } catch (e) { toast(e.message, 'error'); }
}

async function deleteSubtaskItem(taskId, subtaskId) {
  try {
    await api('DELETE', `/api/subtasks/${subtaskId}`);
    await refreshSubtasksInModal(taskId);
  } catch (e) { toast(e.message, 'error'); }
}

function closeTaskModal() {
  document.getElementById('task-modal').classList.remove('open');
}

async function saveTask() {
  const id = document.getElementById('task-id').value;
  const name = document.getElementById('task-name').value.trim();
  if (!name) { toast('Task name is required', 'error'); return; }
  const statusId = document.getElementById('task-status').value || null;
  const startDate = document.getElementById('task-start').value || null;
  const endDate = document.getElementById('task-end').value || null;
  const description = document.getElementById('task-description').value.trim();
  const attrIds = [...document.querySelectorAll('.task-attr-cb:checked')].map(cb => parseInt(cb.value));
  try {
    if (id) {
      await api('PUT', `/api/tasks/${id}`, {
        name, description, start_date: startDate, end_date: endDate,
        status_id: statusId ? parseInt(statusId) : null, attribute_ids: attrIds,
      });
      toast('Task updated', 'success');
    } else {
      await api('POST', '/api/tasks', {
        name, description, start_date: startDate, end_date: endDate,
        status_id: statusId ? parseInt(statusId) : null, attribute_ids: attrIds,
        project_id: S.currentProjectId,
      });
      toast('Task created', 'success');
    }
    closeTaskModal();
    await renderPage();
  } catch (e) { toast(e.message, 'error'); }
}

async function deleteCurrentTask() {
  const id = document.getElementById('task-id').value;
  if (!id || !confirm('Delete this task? This cannot be undone.')) return;
  try {
    await api('DELETE', `/api/tasks/${id}`);
    toast('Task deleted');
    closeTaskModal();
    await renderPage();
  } catch (e) { toast(e.message, 'error'); }
}

// ── Statuses Page ─────────────────────────────────────────────────────────────

function renderStatusesPage() {
  const items = S.statuses.map((s, i) => `
    <div class="status-item" draggable="true" data-id="${s.id}">
      <div class="drag-handle">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="9" cy="5" r="1" fill="currentColor"/><circle cx="9" cy="12" r="1" fill="currentColor"/>
          <circle cx="9" cy="19" r="1" fill="currentColor"/><circle cx="15" cy="5" r="1" fill="currentColor"/>
          <circle cx="15" cy="12" r="1" fill="currentColor"/><circle cx="15" cy="19" r="1" fill="currentColor"/>
        </svg>
      </div>
      <div class="status-color-swatch" style="background:${s.color}"></div>
      <div class="inline-edit" style="flex:1">
        <input type="text" value="${escHtml(s.name)}" class="status-name-input"
          onchange="updateStatusName(${s.id}, this.value, '${s.color}')" />
      </div>
      <input type="color" value="${s.color}" class="status-color-input"
        onchange="updateStatusColor(${s.id}, '${escHtml(s.name)}', this.value)"
        style="width:36px;height:30px;flex-shrink:0" />
      <span class="rank-badge">#${i + 1}</span>
      <button class="btn-icon" onclick="removeStatus(${s.id})" title="Delete">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
          <path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/>
        </svg>
      </button>
    </div>`).join('');

  return `
    <div class="page-header">
      <div>
        <div class="page-title">Statuses</div>
        <div class="page-subtitle">${escHtml(S.currentProject?.name || '')} · Drag to reorder by priority</div>
      </div>
    </div>
    <div class="status-list" id="status-list">${items}</div>
    <div class="add-form">
      <input type="text" id="new-status-name" placeholder="New status name…"
        onkeydown="if(event.key==='Enter')addStatus()" />
      <input type="color" id="new-status-color" value="#4f6ef7"
        style="width:40px;height:36px;flex-shrink:0" />
      <button class="btn btn-primary btn-sm" onclick="addStatus()">Add Status</button>
    </div>`;
}

function bindStatusesPage() {
  const list = document.getElementById('status-list');
  if (!list) return;
  let dragSrc = null;

  list.addEventListener('dragstart', e => {
    dragSrc = e.target.closest('.status-item');
    dragSrc.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
  });
  list.addEventListener('dragover', e => {
    e.preventDefault();
    const over = e.target.closest('.status-item');
    if (over && over !== dragSrc) {
      list.querySelectorAll('.status-item').forEach(el => el.classList.remove('drag-over'));
      over.classList.add('drag-over');
    }
  });
  list.addEventListener('dragleave', e => {
    e.target.closest?.('.status-item')?.classList.remove('drag-over');
  });
  list.addEventListener('drop', e => {
    e.preventDefault();
    const over = e.target.closest('.status-item');
    if (!over || over === dragSrc) return;
    const items = [...list.querySelectorAll('.status-item')];
    if (items.indexOf(dragSrc) < items.indexOf(over)) list.insertBefore(dragSrc, over.nextSibling);
    else list.insertBefore(dragSrc, over);
    over.classList.remove('drag-over');
    saveStatusOrder();
  });
  list.addEventListener('dragend', () => {
    list.querySelectorAll('.status-item').forEach(el => el.classList.remove('dragging','drag-over'));
    updateRankBadges();
  });
}

function updateRankBadges() {
  document.querySelectorAll('#status-list .status-item').forEach((item, i) => {
    const badge = item.querySelector('.rank-badge');
    if (badge) badge.textContent = `#${i + 1}`;
  });
}

async function saveStatusOrder() {
  const ids = [...document.querySelectorAll('#status-list .status-item')].map(el => parseInt(el.dataset.id));
  try {
    await api('PUT', '/api/statuses/reorder', { ordered_ids: ids });
    updateRankBadges();
    toast('Order saved', 'success');
  } catch (e) { toast(e.message, 'error'); }
}

async function addStatus() {
  const name = document.getElementById('new-status-name').value.trim();
  const color = document.getElementById('new-status-color').value;
  if (!name) { toast('Enter a status name', 'error'); return; }
  try {
    await api('POST', '/api/statuses', { name, color, project_id: S.currentProjectId });
    toast('Status added', 'success');
    await renderPage();
  } catch (e) { toast(e.message, 'error'); }
}

async function updateStatusName(id, name, color) {
  name = name.trim();
  if (!name) return;
  try { await api('PUT', `/api/statuses/${id}`, { name, color }); }
  catch (e) { toast(e.message, 'error'); }
}

async function updateStatusColor(id, name, color) {
  const swatch = document.querySelector(`.status-item[data-id="${id}"] .status-color-swatch`);
  if (swatch) swatch.style.background = color;
  try { await api('PUT', `/api/statuses/${id}`, { name, color }); }
  catch (e) { toast(e.message, 'error'); }
}

async function removeStatus(id) {
  if (!confirm('Delete this status? Tasks with this status will lose it.')) return;
  try {
    await api('DELETE', `/api/statuses/${id}`);
    toast('Status deleted');
    await renderPage();
  } catch (e) { toast(e.message, 'error'); }
}

// ── Attributes Page ───────────────────────────────────────────────────────────

function renderAttributesPage() {
  const globalTypes = S.attrTypes.filter(t => t.is_global);
  const projectTypes = S.attrTypes.filter(t => !t.is_global);

  function typeSection(type) {
    const typeAttrs = S.attrs.filter(a => a.type_id === type.id);
    const globalBadge = type.is_global
      ? `<span class="global-badge">
           <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
             <circle cx="12" cy="12" r="10"/>
             <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
           </svg>All Projects
         </span>`
      : '';

    const attrItems = typeAttrs.map(a => `
      <div class="attr-item" data-id="${a.id}">
        <div class="inline-edit" style="flex:1">
          <input type="text" value="${escHtml(a.name)}" onchange="updateAttr(${a.id}, this.value)" />
        </div>
        <button class="btn-icon" onclick="removeAttr(${a.id})" title="Delete">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>`).join('');

    return `
      <div class="attr-type-section">
        <div class="attr-type-header">
          <div class="inline-edit" style="flex:1">
            <input type="text" value="${escHtml(type.name)}" onchange="updateAttrType(${type.id}, this.value)" />
          </div>
          ${globalBadge}
          <label class="global-toggle" title="Make available to all projects">
            <input type="checkbox" ${type.is_global ? 'checked' : ''}
              onchange="toggleAttrTypeGlobal(${type.id}, '${escHtml(type.name)}', this.checked)" />
            Global
          </label>
          <button class="btn-icon" onclick="removeAttrType(${type.id})" title="Delete type">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
              <path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/>
            </svg>
          </button>
        </div>
        <div class="attr-items">${attrItems}</div>
        <div class="attr-add-row">
          <input type="text" placeholder="Add attribute…" id="new-attr-${type.id}"
            onkeydown="if(event.key==='Enter')addAttr(${type.id})" />
          <button class="btn btn-ghost btn-sm" onclick="addAttr(${type.id})">Add</button>
        </div>
      </div>`;
  }

  const globalSection = globalTypes.length
    ? `<div class="attr-section-label">
         <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
           <circle cx="12" cy="12" r="10"/>
           <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
         </svg>Shared Across All Projects
       </div>
       ${globalTypes.map(typeSection).join('')}`
    : '';

  const projectSection = projectTypes.length
    ? `<div class="attr-section-label" style="margin-top:${globalTypes.length ? 24 : 0}px">
         <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
           <path d="M3 7a2 2 0 0 1 2-2h3l2 3h9a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
         </svg>${escHtml(S.currentProject?.name || 'Project')} Only
       </div>
       ${projectTypes.map(typeSection).join('')}`
    : '';

  return `
    <div class="page-header">
      <div>
        <div class="page-title">Attributes</div>
        <div class="page-subtitle">Global types appear in all projects; project types are scoped here</div>
      </div>
    </div>
    ${globalSection}${projectSection}
    <div class="add-form" style="margin-top:${(globalTypes.length || projectTypes.length) ? 8 : 0}px">
      <input type="text" id="new-type-name" placeholder="New attribute type name…"
        onkeydown="if(event.key==='Enter')addAttrType(false)" />
      <button class="btn btn-ghost btn-sm" onclick="addAttrType(false)">
        Add to ${escHtml(S.currentProject?.name || 'Project')}
      </button>
      <button class="btn btn-primary btn-sm" onclick="addAttrType(true)">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10"/>
        </svg>Add as Global
      </button>
    </div>`;
}

async function addAttrType(isGlobal) {
  const name = document.getElementById('new-type-name').value.trim();
  if (!name) { toast('Enter a type name', 'error'); return; }
  try {
    await api('POST', '/api/attribute-types', {
      name,
      is_global: isGlobal,
      project_id: isGlobal ? null : S.currentProjectId,
    });
    toast(`Attribute type added${isGlobal ? ' (global)' : ''}`, 'success');
    await renderPage();
  } catch (e) { toast(e.message, 'error'); }
}

async function updateAttrType(id, name) {
  name = name.trim();
  if (!name) return;
  try { await api('PUT', `/api/attribute-types/${id}`, { name }); }
  catch (e) { toast(e.message, 'error'); }
}

async function toggleAttrTypeGlobal(id, name, isGlobal) {
  try {
    await api('PUT', `/api/attribute-types/${id}`, {
      name,
      is_global: isGlobal,
      project_id: isGlobal ? null : S.currentProjectId,
    });
    toast(isGlobal ? 'Now shared across all projects' : 'Now project-specific', 'success');
    await renderPage();
  } catch (e) { toast(e.message, 'error'); }
}

async function removeAttrType(id) {
  if (!confirm('Delete this attribute type and ALL its attributes? Tasks will lose these attributes.')) return;
  try {
    await api('DELETE', `/api/attribute-types/${id}`);
    toast('Attribute type deleted');
    await renderPage();
  } catch (e) { toast(e.message, 'error'); }
}

async function addAttr(typeId) {
  const input = document.getElementById(`new-attr-${typeId}`);
  const name = (input?.value || '').trim();
  if (!name) { toast('Enter an attribute name', 'error'); return; }
  try {
    await api('POST', '/api/attributes', { type_id: typeId, name });
    toast('Attribute added', 'success');
    await renderPage();
  } catch (e) { toast(e.message, 'error'); }
}

async function updateAttr(id, name) {
  name = name.trim();
  if (!name) return;
  try { await api('PUT', `/api/attributes/${id}`, { name }); }
  catch (e) { toast(e.message, 'error'); }
}

async function removeAttr(id) {
  if (!confirm('Delete this attribute? Tasks using it will lose it.')) return;
  try {
    await api('DELETE', `/api/attributes/${id}`);
    toast('Attribute deleted');
    await renderPage();
  } catch (e) { toast(e.message, 'error'); }
}

// ── Export Page ───────────────────────────────────────────────────────────────

function renderExportPage() {
  const typeOptions = S.attrTypes.map(t =>
    `<option value="${t.id}" data-name="${escHtml(t.name)}" data-global="${t.is_global ? '1' : '0'}">${escHtml(t.name)}${t.is_global ? ' (All Projects)' : ''}</option>`
  ).join('');

  return `
    <div class="page-header">
      <div>
        <div class="page-title">Export</div>
        <div class="page-subtitle">Download reports and timeline charts</div>
      </div>
    </div>

    <div class="export-section">
      <h3>Task Report (PDF)</h3>
      <p>Exports all tasks for <strong>${escHtml(S.currentProject?.name || 'the current project')}</strong> organized by status (highest priority first) with colored status accents. ${exportDestinationHint()}</p>
      <button class="btn btn-primary" id="pdf-btn" onclick="exportPDF()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
        </svg>Export PDF
      </button>
    </div>

    <div class="export-section">
      <h3>Project Timeline (PNG Image)</h3>
      <p>Generates a Gantt-style timeline. If you choose a <strong>global attribute type</strong>, tasks from <em>all projects</em> are included. Otherwise only the current project's tasks are shown. ${exportDestinationHint()}</p>
      <div class="timeline-form">
        <div class="form-row-3">
          <div class="form-group">
            <label>Start Date</label>
            <input type="date" id="tl-start" />
          </div>
          <div class="form-group">
            <label>End Date</label>
            <input type="date" id="tl-end" />
          </div>
          <div class="form-group">
            <label>Organize By (Attribute Type)</label>
            <select id="tl-attr-type">
              <option value="">— Select type —</option>
              ${typeOptions}
            </select>
          </div>
        </div>
        <div class="form-row-3">
          <div class="form-group">
            <label>Resolution</label>
            <select id="tl-resolution-preset" onchange="onResolutionPresetChange()">
              <option value="auto" selected>Auto (fits the chart)</option>
              <option value="1280x720">16:9 — 1280×720 (HD)</option>
              <option value="1920x1080">16:9 — 1920×1080 (Full HD)</option>
              <option value="3840x2160">16:9 — 3840×2160 (4K)</option>
              <option value="1024x768">4:3 — 1024×768</option>
              <option value="1600x1200">4:3 — 1600×1200</option>
              <option value="custom">Custom…</option>
            </select>
          </div>
          <div class="form-group" id="tl-width-group" style="display:none">
            <label>Width (px)</label>
            <input type="number" id="tl-width" min="200" max="6000" value="1920" />
          </div>
          <div class="form-group" id="tl-height-group" style="display:none">
            <label>Height (px)</label>
            <input type="number" id="tl-height" min="200" max="6000" value="1080" />
          </div>
        </div>
        <div id="tl-scope-note" style="font-size:12px;color:var(--text-muted);margin-top:-4px"></div>
        <div>
          <button class="btn btn-primary" id="timeline-btn" onclick="exportTimeline()">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2"/>
              <path d="M3 9h18M3 15h18M9 3v18"/>
            </svg>Export Timeline Image
          </button>
        </div>
      </div>
    </div>`;
}

function exportDestinationHint() {
  return hasNativeSaveDialog()
    ? 'You\'ll be asked where to save the file, then it opens automatically.'
    : 'File is saved to the <strong>exports/</strong> folder and opened automatically. (Choosing a save location requires the desktop app — see README.)';
}

// Resolution preset select: presets fill in an exact width/height (so the
// chart is scaled and letterboxed to fit that exact resolution, e.g. a
// true 16:9 or 4:3 image); "Custom" reveals free-form width/height fields;
// "Auto" exports at the chart's natural size with no forced resolution.
function onResolutionPresetChange() {
  const isCustom = document.getElementById('tl-resolution-preset').value === 'custom';
  document.getElementById('tl-width-group').style.display = isCustom ? '' : 'none';
  document.getElementById('tl-height-group').style.display = isCustom ? '' : 'none';
}

function resolveTimelineResolution() {
  const preset = document.getElementById('tl-resolution-preset').value;
  if (preset === 'auto') return { width: null, height: null };
  if (preset === 'custom') {
    const width = parseInt(document.getElementById('tl-width').value, 10);
    const height = parseInt(document.getElementById('tl-height').value, 10);
    return { width: width || null, height: height || null };
  }
  const [width, height] = preset.split('x').map(n => parseInt(n, 10));
  return { width, height };
}

function bindExportPage() {
  const today = new Date();
  const start = today.toISOString().split('T')[0];
  const end3 = new Date(today);
  end3.setMonth(end3.getMonth() + 3);
  const end = end3.toISOString().split('T')[0];
  const tlStart = document.getElementById('tl-start');
  const tlEnd = document.getElementById('tl-end');
  if (tlStart) tlStart.value = start;
  if (tlEnd) tlEnd.value = end;
  if (document.getElementById('tl-resolution-preset')) onResolutionPresetChange();

  const sel = document.getElementById('tl-attr-type');
  if (sel) {
    sel.addEventListener('change', () => {
      const opt = sel.options[sel.selectedIndex];
      const note = document.getElementById('tl-scope-note');
      if (!note) return;
      if (!opt.value) { note.textContent = ''; return; }
      if (opt.dataset.global === '1') {
        note.innerHTML = '&#127760; Global type — timeline will include tasks from <strong>all projects</strong>.';
      } else {
        note.innerHTML = `&#128196; Project type — timeline will include only <strong>${escHtml(S.currentProject?.name || 'current project')}</strong> tasks.`;
      }
    });
  }
}

async function exportPDF() {
  const projectName = S.currentProject?.name || 'Project';
  const defaultFilename = `${projectName.replace(/[\\/:*?"<>|]/g, '_')}_tasks.pdf`;

  let savePath = null;
  if (hasNativeSaveDialog()) {
    savePath = await nativeSaveDialog(defaultFilename, ['PDF Document (*.pdf)']);
    if (!savePath) return; // user cancelled the dialog
  }

  const btn = document.getElementById('pdf-btn');
  btn.disabled = true; btn.textContent = 'Generating…';
  try {
    const data = await api('POST', '/api/export/pdf', {
      project_id: S.currentProjectId,
      project_name: projectName,
      save_path: savePath,
    });
    toast(`PDF saved: ${data.filename}`, 'success');
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
    </svg>Export PDF`;
  }
}

async function exportTimeline() {
  const startDate = document.getElementById('tl-start').value;
  const endDate = document.getElementById('tl-end').value;
  const sel = document.getElementById('tl-attr-type');
  const attrTypeId = sel.value;
  const opt = sel.options[sel.selectedIndex];
  const attrTypeName = opt?.dataset?.name || '';
  const isGlobal = opt?.dataset?.global === '1';

  if (!startDate || !endDate) { toast('Please select a date range', 'error'); return; }
  if (!attrTypeId) { toast('Please select an attribute type', 'error'); return; }
  if (new Date(startDate) >= new Date(endDate)) { toast('End date must be after start date', 'error'); return; }

  const { width, height } = resolveTimelineResolution();
  if (document.getElementById('tl-resolution-preset').value === 'custom' && (!width || !height)) {
    toast('Enter a width and height for a custom resolution', 'error');
    return;
  }
  const defaultFilename = `${(attrTypeName || 'timeline').replace(/[\\/:*?"<>|]/g, '_')}_timeline.png`;

  let savePath = null;
  if (hasNativeSaveDialog()) {
    savePath = await nativeSaveDialog(defaultFilename, ['PNG Image (*.png)']);
    if (!savePath) return; // user cancelled the dialog
  }

  const btn = document.getElementById('timeline-btn');
  btn.disabled = true; btn.textContent = 'Generating…';
  try {
    const data = await api('POST', '/api/export/timeline', {
      start_date: startDate, end_date: endDate,
      attribute_type_id: attrTypeId, attribute_type_name: attrTypeName,
      project_id: S.currentProjectId, is_global: isGlobal,
      width, height, save_path: savePath,
    });
    toast(`Timeline saved: ${data.filename}`, 'success');
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="3" y="3" width="18" height="18" rx="2"/>
      <path d="M3 9h18M3 15h18M9 3v18"/>
    </svg>Export Timeline Image`;
  }
}

// ── Sidebar section label style ───────────────────────────────────────────────
// (injected via JS so no HTML change needed)
const style = document.createElement('style');
style.textContent = `.attr-section-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.6px; color: var(--text-muted); margin-bottom: 10px;
}`;
document.head.appendChild(style);

// ── Wire up nav & boot ────────────────────────────────────────────────────────

document.querySelectorAll('.nav-link').forEach(link => {
  link.addEventListener('click', e => { e.preventDefault(); navigate(link.dataset.page); });
});

boot();
