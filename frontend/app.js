/* ═══════════════════════════════════════════════════════════════════
   StatIntel — Application Logic v2.0
   Complete client-side application with Chart.js charts, analytics
   integration, officer drawer with deep analysis, registration flow,
   and competency heatmap rendering.
   ═══════════════════════════════════════════════════════════════════ */

const $ = id => document.getElementById(id);
let token = localStorage.getItem('statintel_token') || '';
let currentUser = null;
let officers = [], skills = [], courses = [], roles = [], gaps = [];
let modalSave = null;
let charts = {};

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// ── Toast ──────────────────────────────────────────────────────────
function toast(message) {
  const t = $('toast');
  t.textContent = message;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3200);
}

// ── API Helper ─────────────────────────────────────────────────────
async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData) && typeof options.body !== 'string') {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }
  const res = await fetch(path, { ...options, headers });
  if (res.status === 204) return null;
  const type = res.headers.get('content-type') || '';
  const data = type.includes('application/json') ? await res.json() : await res.text();
  if (!res.ok) {
    if (res.status === 401 && path !== '/api/auth/login' && path !== '/api/auth/register') {
      logout(false);
    }
    throw new Error(data?.detail || data || `Request failed (${res.status})`);
  }
  return data;
}

// ── Auth ───────────────────────────────────────────────────────────
function logout(show = true) {
  token = '';
  currentUser = null;
  localStorage.removeItem('statintel_token');
  $('appShell').classList.add('hidden');
  $('loginScreen').classList.remove('hidden');
  $('loginForm').classList.remove('hidden');
  $('registerForm').classList.add('hidden');
  if (show) toast('Signed out.');
}

$('loginForm').addEventListener('submit', async e => {
  e.preventDefault();
  $('loginError').textContent = '';
  try {
    const result = await api('/api/auth/login', {
      method: 'POST',
      body: { username: $('username').value.trim(), password: $('password').value }
    });
    token = result.access_token;
    localStorage.setItem('statintel_token', token);
    currentUser = { username: result.username, role: result.role, full_name: result.full_name };
    await startApp();
  } catch (err) {
    $('loginError').textContent = err.message;
  }
});

$('registerForm').addEventListener('submit', async e => {
  e.preventDefault();
  $('registerError').textContent = '';
  try {
    const result = await api('/api/auth/register', {
      method: 'POST',
      body: {
        username: $('regUsername').value.trim(),
        password: $('regPassword').value,
        full_name: $('regFullName').value.trim(),
        email: $('regEmail').value.trim(),
      }
    });
    token = result.access_token;
    localStorage.setItem('statintel_token', token);
    currentUser = { username: result.username, role: result.role, full_name: result.full_name };
    toast('Account created! Welcome to StatIntel.');
    await startApp();
  } catch (err) {
    $('registerError').textContent = err.message;
  }
});

$('showRegisterBtn').onclick = () => {
  $('loginForm').classList.add('hidden');
  $('registerForm').classList.remove('hidden');
};
$('showLoginBtn').onclick = () => {
  $('registerForm').classList.add('hidden');
  $('loginForm').classList.remove('hidden');
};

async function startApp(targetPage = null) {
  try {
    currentUser = await api('/api/auth/me');
    const displayName = currentUser.full_name || currentUser.username;
    $('userLabel').textContent = displayName + ' · ' + currentUser.role;
    $('userDisplayName').textContent = displayName;
    $('userRole').textContent = currentUser.role;
    $('userAvatar').textContent = (displayName[0] || '?').toUpperCase();
    $('loginScreen').classList.add('hidden');
    $('appShell').classList.remove('hidden');

    // Adapt UI for officer role
    if (currentUser.role === 'officer') {
      const toggleGrantBtn = $('toggleGrantAccessBtn');
      if (toggleGrantBtn) toggleGrantBtn.classList.add('hidden');
      const grantPanel = $('pathwayAdminGrantPanel');
      if (grantPanel) grantPanel.classList.add('hidden');
      targetPage = targetPage || 'pathway';
    } else {
      const toggleGrantBtn = $('toggleGrantAccessBtn');
      if (toggleGrantBtn) toggleGrantBtn.classList.remove('hidden');
    }

    const elevateBtn = $('elevateAdminBtn');
    if (elevateBtn) {
      if (currentUser.role === 'admin') {
        elevateBtn.classList.add('hidden');
      } else {
        elevateBtn.classList.remove('hidden');
        elevateBtn.onclick = () => openElevateModal();
      }
    }

    await refreshAll();
    await checkHealth();

    if (targetPage) {
      navigate(targetPage);
    }
  } catch (e) {
    logout(false);
    $('loginError').textContent = e.message;
  }
}


$('logoutBtn').onclick = () => logout();

// ── Navigation ─────────────────────────────────────────────────────
const pageLabels = {
  overview: 'Overview', analytics: 'Analytics', officers: 'Officer profiles',
  skills: 'Skill intelligence', learning: 'Learning catalogue',
  roles: 'Role registry', graph: 'Knowledge graph', reports: 'Reports & exports',
  pathway: 'Plan my pathway', succession: 'Cadre Succession'
};

function navigate(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.toggle('active', p.id === 'page-' + page));
  document.querySelectorAll('#nav button').forEach(b => b.classList.toggle('active', b.dataset.page === page));
  $('pageCrumb').textContent = pageLabels[page] || page;
  if (page === 'graph') { renderGraph(); initCopilotHandlers(); }
  if (page === 'pathway') initPathwayPage();
  if (page === 'skills') loadGaps();
  if (page === 'learning') loadCourses();
  if (page === 'roles') loadRoles();
  if (page === 'officers') loadOfficers();
  if (page === 'analytics') loadAnalytics();
  if (page === 'succession') loadSuccessionIntelligence();
}

$('nav').onclick = e => { const b = e.target.closest('[data-page]'); if (b) navigate(b.dataset.page); };
document.querySelectorAll('[data-goto]').forEach(b => b.onclick = () => navigate(b.dataset.goto));
$('mobileNav').onclick = () => $('sidebar').classList.toggle('mobile-open');

// ── Data Loading ───────────────────────────────────────────────────
async function refreshAll() {
  await Promise.all([loadDashboard(), loadOfficers(), loadSkills(), loadCourses(), loadRoles()]);
  await loadGaps();
}

async function checkHealth() {
  try {
    const h = await api('/api/health');
    $('dbStatus').textContent = `API v${h.version || '?'} · ${h.records?.officers || 0} records`;
    $('healthResult').textContent = JSON.stringify(h, null, 2);
  } catch (e) {
    $('dbStatus').textContent = 'Connection issue';
    $('healthResult').textContent = e.message;
  }
}

$('refreshBtn').onclick = async () => {
  try { await refreshAll(); toast('Dashboard refreshed.'); } catch (e) { toast(e.message); }
};
$('healthCheckBtn').onclick = checkHealth;

// ── Dashboard ──────────────────────────────────────────────────────
async function loadDashboard() {
  const [d, people] = await Promise.all([api('/api/dashboard'), api('/api/officers')]);
  officers = people;
  $('metricProfiles').textContent = d.profile_count.toLocaleString();
  $('metricReadiness').textContent = d.average_readiness.toFixed(1) + '%';
  $('metricGaps').textContent = d.reported_gaps.toLocaleString();
  $('metricMedian').textContent = (d.readiness_median || 0).toFixed(1) + '%';

  // Readiness chart (Chart.js)
  renderReadinessChart(people);
  renderPriorityPreview(d.priority_skills || []);
  renderDeptChart(d.departments || []);

  // Recent table
  $('recentRows').innerHTML = people.slice(0, 8).map(p => `
    <tr class="clickable-row" data-officer-id="${p.id}">
      <td><b>${esc(p.name)}</b><small>${p.is_demo ? 'Synthetic demo' : 'User supplied'}</small></td>
      <td>${esc(p.department)}</td>
      <td>${esc(p.current_role)}</td>
      <td>${readinessCell(p.readiness)}</td>
      <td>${p.open_gaps}</td>
    </tr>
  `).join('') || emptyRow(5, 'No profiles yet.');
  bindRowClicks('recentRows');
}

function readinessCell(n) {
  const value = Math.max(0, Math.min(100, Number(n) || 0));
  const color = value < 40 ? '#9e3523' : value < 60 ? '#a47730' : value < 80 ? '#4a7d9e' : '#3d7a5f';
  return `<div class="readiness"><span class="mini-track"><i style="width:${value}%;background:${color}"></i></span><b>${value.toFixed(0)}%</b></div>`;
}

function renderReadinessChart(people) {
  const ctx = $('readinessCanvas');
  if (!ctx) return;
  const bands = [
    { label: 'Critical (0–39%)', filter: p => p.readiness < 40, color: '#9e3523' },
    { label: 'Developing (40–59%)', filter: p => p.readiness >= 40 && p.readiness < 60, color: '#a47730' },
    { label: 'Proficient (60–79%)', filter: p => p.readiness >= 60 && p.readiness < 80, color: '#4a7d9e' },
    { label: 'Advanced (80–100%)', filter: p => p.readiness >= 80, color: '#3d7a5f' },
  ];
  const data = bands.map(b => people.filter(b.filter).length);
  const labels = bands.map(b => b.label);
  const colors = bands.map(b => b.color);

  if (charts.readiness) charts.readiness.destroy();
  charts.readiness = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ data, backgroundColor: colors, borderRadius: 3, barPercentage: 0.6 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => `${ctx.raw} officer${ctx.raw !== 1 ? 's' : ''}` } }
      },
      scales: {
        x: { grid: { color: '#e8e4d8' }, ticks: { font: { size: 10 } } },
        y: { grid: { display: false }, ticks: { font: { size: 10, family: 'Georgia, serif' } } },
      },
    },
  });
}

function renderDeptChart(departments) {
  const ctx = $('deptCanvas');
  if (!ctx || !departments.length) return;
  if (charts.dept) charts.dept.destroy();
  charts.dept = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: departments.map(d => d.name.length > 25 ? d.name.slice(0, 23) + '…' : d.name),
      datasets: [{
        label: 'Avg readiness %',
        data: departments.map(d => d.avg_readiness),
        backgroundColor: departments.map(d => d.avg_readiness >= 70 ? '#3d7a5f' : d.avg_readiness >= 50 ? '#4a7d9e' : '#9e3523'),
        borderRadius: 3,
        barPercentage: 0.55,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => `${ctx.raw}% avg · ${departments[ctx.dataIndex].count} officers` } }
      },
      scales: {
        y: { beginAtZero: true, max: 100, grid: { color: '#e8e4d8' }, ticks: { font: { size: 10 }, callback: v => v + '%' } },
        x: { grid: { display: false }, ticks: { font: { size: 9 }, maxRotation: 45 } },
      },
    },
  });
}

function renderPriorityPreview(items) {
  $('priorityPreview').innerHTML = items.slice(0, 6).map((x, i) => {
    const mentions = x.profile_mentions;
    const severity = x.severity || {};
    const level = severity.level || (mentions >= 3 ? 'high' : mentions ? 'moderate' : 'unobserved');
    return `<div class="list-item">
      <span class="list-index">0${i + 1}</span>
      <div class="list-main">
        <b>${esc(x.skill)}</b>
        <small>${mentions} mention${mentions !== 1 ? 's' : ''} · severity ${severity.score || '—'}</small>
      </div>
      <span class="priority ${level}">${level.toUpperCase()}</span>
    </div>`;
  }).join('') || '<p class="empty">No matching skill mentions yet.</p>';
}

function emptyRow(cols, msg) {
  return `<tr><td colspan="${cols}" class="empty">${esc(msg)}</td></tr>`;
}

// ── Analytics Page ─────────────────────────────────────────────────
async function loadAnalytics() {
  try {
    const [wf, hm] = await Promise.all([api('/api/analytics/workforce'), api('/api/analytics/heatmap')]);
    renderAnalyticsSummary(wf);
    renderHistogram(wf.readiness?.histogram || []);
    renderRadar(wf.skill_coverage || []);
    renderBands(wf.readiness?.bands || {});
    renderTrend(wf.trend_projection || []);
    renderHeatmap(hm);
    $('methodologyNote').textContent = wf.methodology || '';
  } catch (e) {
    toast('Analytics: ' + e.message);
  }
}

$('refreshAnalytics').onclick = loadAnalytics;

function renderAnalyticsSummary(wf) {
  const s = wf.readiness?.descriptive_stats || {};
  $('anN').textContent = s.n ?? '—';
  $('anMean').textContent = s.mean != null ? s.mean.toFixed(1) + '%' : '—';
  $('anStdDev').textContent = s.std_dev != null ? s.std_dev.toFixed(1) : '—';
  $('anSkew').textContent = s.skewness != null ? s.skewness.toFixed(3) : '—';
  $('anMedian').textContent = s.median != null ? s.median.toFixed(1) + '%' : '—';
  $('anIQR').textContent = s.iqr != null ? s.iqr.toFixed(1) : '—';
  $('anKurt').textContent = s.kurtosis != null ? s.kurtosis.toFixed(3) : '—';
  $('anCV').textContent = s.cv != null ? s.cv.toFixed(1) + '%' : '—';
}

function renderHistogram(bins) {
  const ctx = $('histCanvas');
  if (!ctx || !bins.length) return;
  if (charts.hist) charts.hist.destroy();
  charts.hist = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: bins.map(b => `${b.bin_start}–${b.bin_end}`),
      datasets: [{
        label: 'Frequency',
        data: bins.map(b => b.count),
        backgroundColor: bins.map(b => {
          const mid = (b.bin_start + b.bin_end) / 2;
          return mid < 40 ? '#9e3523' : mid < 60 ? '#a47730' : mid < 80 ? '#4a7d9e' : '#3d7a5f';
        }),
        borderRadius: 2,
        barPercentage: 0.92,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => `${ctx.raw} officer${ctx.raw !== 1 ? 's' : ''} (${(bins[ctx.dataIndex].frequency * 100).toFixed(1)}%)` } },
      },
      scales: {
        y: { beginAtZero: true, grid: { color: '#e8e4d8' }, ticks: { font: { size: 10 }, stepSize: 1 }, title: { display: true, text: 'Count', font: { size: 10 } } },
        x: { grid: { display: false }, ticks: { font: { size: 9 }, maxRotation: 45 }, title: { display: true, text: 'Readiness %', font: { size: 10 } } },
      },
    },
  });
}

function renderRadar(coverage) {
  const ctx = $('radarCanvas');
  if (!ctx || !coverage.length) return;
  if (charts.radar) charts.radar.destroy();
  const top8 = coverage.slice(0, 8);
  charts.radar = new Chart(ctx, {
    type: 'radar',
    data: {
      labels: top8.map(c => c.skill.length > 20 ? c.skill.slice(0, 18) + '…' : c.skill),
      datasets: [
        { label: 'Coverage %', data: top8.map(c => c.coverage_pct), backgroundColor: 'rgba(61,122,95,0.15)', borderColor: '#3d7a5f', borderWidth: 2, pointRadius: 3 },
        { label: 'Gap %', data: top8.map(c => c.gap_pct), backgroundColor: 'rgba(158,53,35,0.1)', borderColor: '#9e3523', borderWidth: 2, pointRadius: 3 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom', labels: { font: { size: 10 }, padding: 12 } } },
      scales: {
        r: {
          beginAtZero: true,
          max: 100,
          ticks: { font: { size: 8 }, stepSize: 25 },
          pointLabels: { font: { size: 9, family: 'Georgia, serif' } },
          grid: { color: '#e8e4d8' },
        },
      },
    },
  });
}

function renderBands(bands) {
  const ctx = $('bandCanvas');
  if (!ctx) return;
  if (charts.band) charts.band.destroy();
  const order = ['critical', 'developing', 'proficient', 'advanced'];
  const colors = { critical: '#9e3523', developing: '#a47730', proficient: '#4a7d9e', advanced: '#3d7a5f' };
  const labels = order.map(k => (bands[k]?.range || k).replace(/\b\w/g, l => l.toUpperCase()));
  const data = order.map(k => bands[k]?.count || 0);

  charts.band = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{ data, backgroundColor: order.map(k => colors[k]), borderWidth: 2, borderColor: '#faf8f1' }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      cutout: '55%',
      plugins: {
        legend: { position: 'bottom', labels: { font: { size: 10 }, padding: 10, usePointStyle: true } },
        tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.raw} officer${ctx.raw !== 1 ? 's' : ''}` } },
      },
    },
  });
}

function renderTrend(projection) {
  const ctx = $('trendCanvas');
  if (!ctx || !projection.length) return;
  if (charts.trend) charts.trend.destroy();
  charts.trend = new Chart(ctx, {
    type: 'line',
    data: {
      labels: projection.map(p => p.quarter),
      datasets: [{
        label: 'Projected readiness %',
        data: projection.map(p => p.projected_readiness),
        borderColor: '#4a7d9e',
        backgroundColor: 'rgba(74,125,158,0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 5,
        pointBackgroundColor: '#4a7d9e',
        borderWidth: 2.5,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => `${ctx.raw.toFixed(1)}% (±${projection[ctx.dataIndex].confidence_interval}%)` } },
      },
      scales: {
        y: { beginAtZero: false, grid: { color: '#e8e4d8' }, ticks: { font: { size: 10 }, callback: v => v + '%' } },
        x: { grid: { display: false }, ticks: { font: { size: 11, family: 'Georgia, serif' } } },
      },
    },
  });
}

function renderHeatmap(hm) {
  const container = $('heatmapContainer');
  if (!container || !hm.matrix?.length) {
    container.innerHTML = '<p class="empty">No data for heatmap.</p>';
    return;
  }
  const skills = hm.skills || [];
  let html = '<table class="heatmap-table"><thead><tr><th></th>';
  skills.forEach(s => {
    html += `<th class="rotated">${esc(s.length > 22 ? s.slice(0, 20) + '…' : s)}</th>`;
  });
  html += '</tr></thead><tbody>';
  hm.matrix.forEach(row => {
    html += `<tr><th style="text-align:right;white-space:nowrap;padding-right:12px">${esc(row.department.length > 30 ? row.department.slice(0, 28) + '…' : row.department)} <small style="color:#999">(${row.officer_count})</small></th>`;
    skills.forEach(s => {
      const cell = row.skills[s] || {};
      const pct = cell.coverage_pct || 0;
      const cls = pct >= 75 ? 'heat-high' : pct >= 50 ? 'heat-medium' : pct >= 25 ? 'heat-low' : 'heat-minimal';
      html += `<td><div class="heatmap-cell ${cls}" title="${esc(s)}: ${pct}% coverage">${pct > 0 ? pct + '%' : '—'}</div></td>`;
    });
    html += '</tr>';
  });
  html += '</tbody></table>';
  container.innerHTML = html;
}

// ── Officers ───────────────────────────────────────────────────────
async function loadOfficers() {
  officers = await api('/api/officers?q=' + encodeURIComponent($('officerSearch').value || ''));
  $('officerRows').innerHTML = officers.map(p => `
    <tr>
      <td><b class="officer-link" data-id="${p.id}" style="cursor:pointer;color:var(--accent)">${esc(p.name)}</b><small>${p.is_demo ? 'Synthetic seed data' : 'User supplied'}</small></td>
      <td>${esc(p.department)}</td>
      <td>${esc(p.current_role)}</td>
      <td>${esc(p.target_role)}</td>
      <td>${readinessCell(p.readiness)}</td>
      <td>${p.open_gaps}</td>
      <td class="row-actions">
        <button class="text-btn" data-view-officer="${p.id}">View</button>
        <button class="text-btn" data-edit-officer="${p.id}">Edit</button>
        <button class="text-btn danger-text" data-delete-officer="${p.id}">Delete</button>
      </td>
    </tr>
  `).join('') || emptyRow(7, 'No matching profiles.');

  $('officerRows').querySelectorAll('[data-view-officer]').forEach(b => b.onclick = () => openOfficerDrawer(Number(b.dataset.viewOfficer)));
  $('officerRows').querySelectorAll('.officer-link').forEach(b => b.onclick = () => openOfficerDrawer(Number(b.dataset.id)));
  $('officerRows').querySelectorAll('[data-edit-officer]').forEach(b => b.onclick = () => editOfficer(Number(b.dataset.editOfficer)));
  $('officerRows').querySelectorAll('[data-delete-officer]').forEach(b => b.onclick = () => deleteOfficer(Number(b.dataset.deleteOfficer)));
}

function bindRowClicks(containerId) {
  document.querySelectorAll(`#${containerId} .clickable-row`).forEach(row => {
    row.style.cursor = 'pointer';
    row.onclick = () => openOfficerDrawer(Number(row.dataset.officerId));
  });
}

$('officerSearch').oninput = () => loadOfficers().catch(e => toast(e.message));

// ── Officer Drawer (deep analysis) ─────────────────────────────────
async function openOfficerDrawer(id) {
  $('officerDrawer').classList.remove('hidden');
  $('drawerOfficerName').textContent = 'Loading…';
  $('drawerBody').innerHTML = '<p class="muted">Fetching analysis…</p>';
  try {
    const data = await api(`/api/analytics/officer/${id}`);
    const o = data.officer;
    $('drawerOfficerName').textContent = o.name;

    let html = '';
    // Summary stats
    html += `<div class="drawer-section">
      <h3>Readiness Assessment</h3>
      <div class="drawer-stat-row">
        <div class="drawer-stat"><strong>${o.readiness.toFixed(0)}%</strong><small>Readiness</small></div>
        <div class="drawer-stat"><strong>${o.open_gaps}</strong><small>Open gaps</small></div>
        <div class="drawer-stat"><strong style="font-size:14px">${esc(data.readiness_band)}</strong><small>Band</small></div>
      </div>
      <div style="padding:10px 14px;background:var(--panel2);border-radius:3px;font-size:11px;line-height:1.7;color:var(--muted)">
        ${esc(data.interpretation)}
      </div>
    </div>`;

    // Officer details
    html += `<div class="drawer-section">
      <h3>Profile Details</h3>
      <table style="width:100%">
        <tr><td style="font-weight:600;width:40%">Department</td><td>${esc(o.department)}</td></tr>
        <tr><td style="font-weight:600">Current role</td><td>${esc(o.current_role)}</td></tr>
        <tr><td style="font-weight:600">Target role</td><td>${esc(o.target_role)}</td></tr>
      </table>
    </div>`;

    // Skill profile
    html += `<div class="drawer-section">
      <h3>Competency Profile (${data.evidenced_count} evidenced · ${data.gap_count} gaps · ${data.unassessed_count} unassessed)</h3>`;
    (data.skill_profile || []).forEach(s => {
      html += `<span class="skill-tag ${s.status}">${esc(s.skill)}</span>`;
    });
    html += '</div>';

    // Gap remediation
    if (data.gap_remediation?.length) {
      html += '<div class="drawer-section"><h3>Recommended Learning</h3>';
      data.gap_remediation.forEach(r => {
        html += `<div style="margin-bottom:8px"><b style="font-size:11px;color:var(--accent)">${esc(r.skill)}</b> <small style="color:var(--muted)">${esc(r.domain)}</small>`;
        if (r.courses.length) {
          r.courses.forEach(c => {
            html += `<div class="course-recommend"><b>${esc(c.name)}</b><small>${esc(c.provider)} · ${esc(c.duration)} · ${c.verified ? 'Verified' : 'Unverified'}</small></div>`;
          });
        } else {
          html += '<div class="course-recommend"><small>No matching courses in catalogue</small></div>';
        }
        html += '</div>';
      });
      html += '</div>';
    }

    $('drawerBody').innerHTML = html;
  } catch (e) {
    $('drawerBody').innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

$('drawerClose').onclick = () => $('officerDrawer').classList.add('hidden');
$('officerDrawer').onclick = e => { if (e.target === $('officerDrawer')) $('officerDrawer').classList.add('hidden'); };

// ── Modal Forms ────────────────────────────────────────────────────
function fieldsMarkup(fields, values = {}) {
  return fields.map(f => {
    const value = values[f.key] ?? f.value ?? '';
    if (f.type === 'textarea')
      return `<label>${esc(f.label)}<textarea name="${esc(f.key)}" ${f.required ? 'required' : ''} placeholder="${esc(f.placeholder || '')}">${esc(Array.isArray(value) ? value.join('; ') : value)}</textarea></label>`;
    if (f.type === 'select')
      return `<label>${esc(f.label)}<select name="${esc(f.key)}">${f.options.map(o => `<option ${String(value) === String(o.value) ? 'selected' : ''} value="${esc(o.value)}">${esc(o.label)}</option>`).join('')}</select></label>`;
    return `<label>${esc(f.label)}<input name="${esc(f.key)}" type="${f.type || 'text'}" value="${esc(value)}" ${f.required ? 'required' : ''} ${f.min !== undefined ? `min="${f.min}"` : ''} ${f.max !== undefined ? `max="${f.max}"` : ''} placeholder="${esc(f.placeholder || '')}"></label>`;
  }).join('');
}

function openForm(title, fields, values, save) {
  $('modalTitle').textContent = title;
  $('modalFields').innerHTML = fieldsMarkup(fields, values);
  $('modalError').textContent = '';
  $('modalBack').classList.remove('hidden');
  modalSave = save;
}

function closeForm() { $('modalBack').classList.add('hidden'); modalSave = null; }

$('modalClose').onclick = closeForm;
$('modalCancel').onclick = closeForm;
$('modalBack').onclick = e => { if (e.target === $('modalBack')) closeForm(); };
$('entityForm').onsubmit = async e => {
  e.preventDefault();
  if (!modalSave) return;
  const fd = new FormData(e.currentTarget);
  const values = Object.fromEntries(fd.entries());
  try {
    await modalSave(values);
    closeForm();
    await refreshAll();
    toast('Saved to the database.');
  } catch (err) {
    $('modalError').textContent = err.message;
  }
};

const officerFields = [
  { key: 'name', label: 'Officer name', required: true },
  { key: 'department', label: 'Department' },
  { key: 'current_role', label: 'Current role', required: true },
  { key: 'target_role', label: 'Target role' },
  { key: 'readiness', label: 'Readiness (0–100)', type: 'number', min: 0, max: 100, required: true },
  { key: 'open_gaps', label: 'Open skill gaps', type: 'number', min: 0, max: 1000, required: true },
  { key: 'years_in_role', label: 'Years in current role', type: 'number', min: 0, max: 50 },
  { key: 'qualification', label: 'Qualification' },
  { key: 'skills', label: 'Evidenced skills', type: 'textarea', placeholder: 'Separate skills with semicolons' },
  { key: 'missing_skills', label: 'Missing skills', type: 'textarea', placeholder: 'Separate skills with semicolons' },
  { key: 'assessment_source', label: 'Assessment source / evidence reference', required: true },
  { key: 'assessment_date', label: 'Assessment date (YYYY-MM-DD)' },
];

function officerPayload(v, isDemo = false) {
  return {
    ...v,
    readiness: Number(v.readiness),
    open_gaps: Number(v.open_gaps),
    years_in_role: Number(v.years_in_role || 0),
    skills: (v.skills || '').split(/[;|]/).map(s => s.trim()).filter(Boolean),
    missing_skills: (v.missing_skills || '').split(/[;|]/).map(s => s.trim()).filter(Boolean),
    is_demo: isDemo,
  };
}

$('addOfficerBtn').onclick = () => openForm('Add officer profile', officerFields, {
  readiness: 60, open_gaps: 0, years_in_role: 0,
  department: 'Not specified', current_role: 'Not specified',
  target_role: 'Not specified', assessment_source: 'User-entered; unverified',
}, async v => api('/api/officers', { method: 'POST', body: officerPayload(v, false) }));

async function editOfficer(id) {
  const p = await api('/api/officers');
  const x = p.find(v => v.id === id);
  if (!x) return;
  openForm('Edit officer profile', officerFields, {
    ...x, skills: x.skills, missing_skills: x.missing_skills,
  }, async v => api('/api/officers/' + id, { method: 'PUT', body: officerPayload(v, x.is_demo) }));
}

async function deleteOfficer(id) {
  const p = officers.find(x => x.id === id);
  if (!p || !confirm(`Delete profile for ${p.name}? This cannot be undone.`)) return;
  try { await api('/api/officers/' + id, { method: 'DELETE' }); await refreshAll(); toast('Profile deleted.'); }
  catch (e) { toast(e.message); }
}

// CSV Import/Export
$('importCsvBtn').onclick = () => $('csvFile').click();
$('csvFile').onchange = async e => {
  const file = e.target.files?.[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  try {
    const result = await api('/api/officers/import-csv', { method: 'POST', body: fd });
    await refreshAll();
    toast(`Import: ${result.added} added, ${result.updated} updated, ${result.skipped} skipped.`);
  } catch (err) { toast(err.message); }
  finally { e.target.value = ''; }
};

// ── Skills ─────────────────────────────────────────────────────────
async function loadSkills() {
  skills = await api('/api/skills');
}

async function loadGaps() {
  try {
    const result = await api('/api/gap-analysis');
    gaps = result.items || [];
    $('gapMethod').innerHTML = `<b>Methodology</b><span>${esc(result.method)} ${esc(result.data_quality_warning)}</span>`;

    $('skillRows').innerHTML = gaps.map(g => `
      <tr>
        <td><b>${esc(g.skill)}</b></td>
        <td>${esc(g.domain)}</td>
        <td>${g.profile_mentions}</td>
        <td><b>${g.severity_score?.toFixed(1) || '—'}</b><small>${g.mention_ratio || 0}% of profiles</small></td>
        <td><span class="priority ${g.severity_level || 'unobserved'}">${(g.severity_level || 'NONE').toUpperCase()}</span></td>
        <td>${esc(g.source_status)}${g.profiles?.length ? '<small>' + g.profiles.slice(0, 3).map(esc).join(', ') + (g.profiles.length > 3 ? ` +${g.profiles.length - 3} more` : '') + '</small>' : ''}</td>
      </tr>
    `).join('') || emptyRow(6, 'No skills in the catalogue yet.');

    renderPriorityPreview(gaps.map(g => ({ skill: g.skill, profile_mentions: g.profile_mentions, severity: { score: g.severity_score, level: g.severity_level } })));
  } catch (e) {
    $('gapMethod').textContent = e.message;
  }
}

$('addSkillBtn').onclick = () => openForm('Add skill', [
  { key: 'name', label: 'Skill name', required: true },
  { key: 'domain', label: 'Domain', required: true },
  { key: 'description', label: 'Definition / description', type: 'textarea' },
  { key: 'source_reference', label: 'Authoritative source reference / URL' },
  { key: 'review_status', label: 'Review status' },
], { domain: 'General', review_status: 'Pending review' }, async v => api('/api/skills', { method: 'POST', body: v }));

// ── Courses ────────────────────────────────────────────────────────
async function loadCourses() {
  courses = await api('/api/courses?q=' + encodeURIComponent($('courseSearch').value || ''));
  $('courseRows').innerHTML = courses.map(c => `
    <tr>
      <td><b>${esc(c.name)}</b></td>
      <td>${esc(c.provider)}</td>
      <td>${esc(c.skill_name)}</td>
      <td>${esc(c.duration)}</td>
      <td><span class="priority ${c.verified ? 'low' : 'moderate'}">${c.verified ? 'VERIFIED' : 'UNVERIFIED'}</span></td>
      <td>${c.source_reference ? `<a href="${esc(c.source_reference)}" target="_blank" rel="noreferrer">Source →</a>` : 'Not supplied'}</td>
    </tr>
  `).join('') || emptyRow(6, 'No learning programmes yet.');
}

$('courseSearch').oninput = () => loadCourses().catch(e => toast(e.message));
$('addCourseBtn').onclick = () => openForm('Add learning programme', [
  { key: 'name', label: 'Programme name', required: true },
  { key: 'provider', label: 'Provider', required: true },
  { key: 'skill_name', label: 'Skill focus', required: true },
  { key: 'domain', label: 'Domain' },
  { key: 'duration', label: 'Duration' },
  { key: 'url', label: 'Course URL (optional)' },
  { key: 'source_reference', label: 'Verification source URL' },
  { key: 'verified', label: 'Verified?', type: 'select', options: [{ value: 'false', label: 'No — requires review' }, { value: 'true', label: 'Yes — source checked' }] },
], { provider: 'Unverified provider', domain: 'General', duration: 'Not specified', verified: 'false' },
  async v => api('/api/courses', { method: 'POST', body: { ...v, verified: v.verified === 'true' } }));

// ── Roles ──────────────────────────────────────────────────────────
async function loadRoles() {
  roles = await api('/api/roles');
  $('roleRows').innerHTML = roles.map(r => `
    <tr>
      <td><b>${esc(r.name)}</b></td>
      <td>${esc(r.grade)}</td>
      <td>${r.required_skills.map(x => esc(x.skill) + ' (L' + x.required_level + ')').join(', ') || 'Not mapped'}</td>
      <td>${esc(r.review_status)}</td>
      <td>${r.source_reference ? esc(r.source_reference) : 'Not attached'}</td>
    </tr>
  `).join('') || emptyRow(5, 'No roles defined.');
}

$('addRoleBtn').onclick = () => openForm('Add role definition', [
  { key: 'name', label: 'Role name', required: true },
  { key: 'grade', label: 'Grade / level' },
  { key: 'description', label: 'Role description', type: 'textarea' },
  { key: 'source_reference', label: 'Official role standard URL / reference' },
  { key: 'review_status', label: 'Review status' },
  { key: 'required_skills', label: 'Required skills', type: 'textarea', placeholder: 'Skill A; Skill B' },
], { grade: 'Not specified', review_status: 'Pending review' },
  async v => api('/api/roles', { method: 'POST', body: { ...v, required_skills: (v.required_skills || '').split(/[;|]/).map(s => s.trim()).filter(Boolean) } }));

// ── Neural Network Graph & AI Cadre Copilot ──────────────────────────
let activeNeuralNode = null;

const CADRE_ORDER = [
  'Statistical Investigator',
  'Junior Statistical Officer',
  'Senior Statistical Officer',
  'Assistant Director',
  'Deputy Director',
  'Director',
  'ISS Officer'
];

function updateTargetOptions(currentRole, availableRoles = []) {
  const targetSelect = $('copilotTargetRole');
  if (!targetSelect) return;

  const currIdx = CADRE_ORDER.findIndex(x => x.toLowerCase() === (currentRole || '').toLowerCase());
  let higherRoles = [];

  if (currIdx !== -1) {
    // Only allow promotional transitions strictly higher in the cadre hierarchy
    higherRoles = CADRE_ORDER.filter((r, idx) => idx > currIdx);
  } else {
    higherRoles = availableRoles.filter(r => r.toLowerCase() !== (currentRole || '').toLowerCase());
  }

  // If already at apex role, offer official executive specialization
  if (!higherRoles.length) {
    higherRoles = ['Senior Cadre Specialization', 'Principal Statistical Advisor'];
  }

  const prevValue = targetSelect.value;
  targetSelect.innerHTML = higherRoles.map(r => `<option value="${esc(r)}">${esc(r)}</option>`).join('');

  if (higherRoles.includes(prevValue)) {
    targetSelect.value = prevValue;
  } else {
    targetSelect.selectedIndex = 0;
  }
}

async function renderGraph() {
  try {
    const [graph, allRoles] = await Promise.all([api('/api/graph'), api('/api/roles')]);
    const svg = $('graphSvg');
    if (!svg) return;

    const r = graph.nodes.filter(n => n.type === 'role');
    const s = graph.nodes.filter(n => n.type === 'skill');
    const c = graph.nodes.filter(n => n.type === 'course');
    const roleLabels = r.map(x => x.label);

    // Populate Copilot selects with dynamic promotion constraints
    const roleSelect = $('copilotCurrentRole');
    const targetSelect = $('copilotTargetRole');
    if (roleSelect && targetSelect && (!roleSelect.children.length || !targetSelect.children.length)) {
      roleSelect.innerHTML = roleLabels.map(x => `<option value="${esc(x)}">${esc(x)}</option>`).join('');
      roleSelect.onchange = () => {
        updateTargetOptions(roleSelect.value, roleLabels);
        triggerCopilotPathway(roleSelect.value, targetSelect.value);
      };
      updateTargetOptions(roleSelect.value, roleLabels);
    }

    // Neural Coordinates (3-Layer Deep Architecture)
    const pos = {};
    const W = 1100, H = 660;
    const xRole = 165, xSkill = 490, xCourse = 780;

    r.forEach((n, i) => pos[n.id] = { x: xRole, y: 70 + i * ((H - 140) / Math.max(r.length - 1, 1)), layer: 1, idx: `x${i+1}` });
    s.forEach((n, i) => pos[n.id] = { x: xSkill, y: 55 + i * ((H - 110) / Math.max(s.length - 1, 1)), layer: 2, idx: `h${i+1}` });
    c.forEach((n, i) => pos[n.id] = { x: xCourse, y: 75 + i * ((H - 150) / Math.max(c.length - 1, 1)), layer: 3, idx: `y${i+1}` });

    let svgHtml = `
      <defs>
        <pattern id="neuralDots" width="22" height="22" patternUnits="userSpaceOnUse">
          <circle cx="2" cy="2" r="1.2" fill="#dcd6c8" />
        </pattern>
        <filter id="neuralGlow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>
      <rect width="100%" height="100%" fill="url(#neuralDots)" opacity="0.6"/>
    `;

    // Layer Headers with warm editorial palette
    svgHtml += `
      <g class="neural-headers" opacity="0.95">
        <text x="${xRole}" y="32" text-anchor="middle" fill="#2d6648" font-size="10.5" font-weight="800" letter-spacing="1.5">INPUT LAYER &bull; CADRE POSTS</text>
        <text x="${xSkill}" y="32" text-anchor="middle" fill="#a47730" font-size="10.5" font-weight="800" letter-spacing="1.5">HIDDEN LAYER &bull; COMPETENCY NEURONS</text>
        <text x="${xCourse + 70}" y="32" text-anchor="middle" fill="#4a7d9e" font-size="10.5" font-weight="800" letter-spacing="1.5">OUTPUT LAYER &bull; VERIFIED CURRICULA</text>
      </g>
    `;

    // Render Synapses (Edges)
    for (const e of graph.edges) {
      const a = pos[e.from], b = pos[e.to];
      if (!a || !b) continue;
      const dx = Math.abs(b.x - a.x) * 0.45;
      const pathId = `synapse-${e.from}-${e.to}`;
      svgHtml += `<path class="synapse" id="${pathId}" data-from="${e.from}" data-to="${e.to}"
        d="M ${a.x} ${a.y} C ${a.x + dx} ${a.y}, ${b.x - dx} ${b.y}, ${b.x} ${b.y}"
        fill="none" stroke="#d5cfbf" stroke-width="1.3" stroke-opacity="0.65" />`;
    }

    // Render Neurons (Nodes)
    const all = [...r, ...s, ...c];
    all.forEach(n => {
      const p = pos[n.id];
      if (!p) return;
      const color = p.layer === 1 ? '#2d6648' : p.layer === 2 ? '#a47730' : '#4a7d9e';
      const label = n.label.length > 20 ? n.label.slice(0, 19) + '…' : n.label;

      svgHtml += `
        <g class="neuron-node" id="neuron-${n.id}" data-id="${n.id}" data-type="${n.type}" data-label="${esc(n.label)}" data-layer="${p.layer}">
          <!-- Synaptic Halo -->
          <circle class="neuron-halo" cx="${p.x}" cy="${p.y}" r="20" fill="${color}" fill-opacity="0.10" stroke="${color}" stroke-opacity="0.35" stroke-width="1" />
          <!-- Neuron Core -->
          <circle class="neuron-core" cx="${p.x}" cy="${p.y}" r="13" fill="${color}" fill-opacity="0.95" stroke="#ffffff" stroke-width="1.8" />
          <!-- Index Glyph -->
          <text x="${p.x}" y="${p.y + 3.5}" text-anchor="middle" fill="#ffffff" font-size="8.5" font-weight="800">${p.idx}</text>
          <!-- Label Card -->
          <g class="neuron-label-group">
            <rect x="${p.layer === 1 ? p.x - 150 : p.layer === 3 ? p.x + 20 : p.x - 70}" y="${p.layer === 2 ? p.y + 16 : p.y - 12}"
              width="${p.layer === 2 ? 140 : p.layer === 3 ? 150 : 125}" height="24" rx="3"
              fill="#ffffff" fill-opacity="0.95" stroke="${color}" stroke-opacity="0.5" stroke-width="1" />
            <text x="${p.layer === 1 ? p.x - 87 : p.layer === 3 ? p.x + 95 : p.x}" y="${p.layer === 2 ? p.y + 31 : p.y + 3.5}"
              text-anchor="middle" fill="#1a2420" font-size="9" font-weight="700">${esc(label)}</text>
          </g>
        </g>
      `;
    });

    svg.innerHTML = svgHtml;

    // Neuron Click & Activation Listeners
    svg.querySelectorAll('.neuron-node').forEach(g => {
      const nid = g.dataset.id;
      const ntype = g.dataset.type;
      const nlabel = g.dataset.label;

      g.onclick = () => {
        activateNeuralCircuit(nid, graph, pos);
        if (ntype === 'role') {
          if ($('copilotCurrentRole')) {
            $('copilotCurrentRole').value = nlabel;
            updateTargetOptions(nlabel, roleLabels);
          }
          triggerCopilotPathway(nlabel, $('copilotTargetRole')?.value || 'Senior Statistical Officer');
        } else if (ntype === 'skill') {
          triggerCopilotPathway($('copilotCurrentRole')?.value || 'Junior Statistical Officer', $('copilotTargetRole')?.value || 'Senior Statistical Officer', `Focus on learning roadmap for ${nlabel}`);
        }
      };
    });

    // Reset button
    const resetBtn = $('resetNeuralView');
    if (resetBtn) {
      resetBtn.onclick = () => resetNeuralActivation();
    }

    // Set default initial Copilot view if empty
    if ($('copilotRoadmap') && $('copilotRoadmap').querySelector('h3')?.textContent.includes('Select a Cadre')) {
      triggerCopilotPathway('Junior Statistical Officer', 'Senior Statistical Officer');
    }

  } catch (e) {
    console.error('Neural graph render error:', e);
  }
}

function activateNeuralCircuit(targetId, graph, pos) {
  activeNeuralNode = targetId;
  const svg = $('graphSvg');
  if (!svg) return;

  // Find connected nodes and synapses
  const connectedNodes = new Set([targetId]);
  const activeSynapses = new Set();

  // Forward connections
  graph.edges.forEach(e => {
    if (e.from === targetId) {
      activeSynapses.add(`synapse-${e.from}-${e.to}`);
      connectedNodes.add(e.to);
      // Secondary forward (e.g. Role -> Skill -> Course)
      graph.edges.forEach(e2 => {
        if (e2.from === e.to) {
          activeSynapses.add(`synapse-${e2.from}-${e2.to}`);
          connectedNodes.add(e2.to);
        }
      });
    }
  });

  // Backward connections (if skill or course clicked)
  graph.edges.forEach(e => {
    if (e.to === targetId) {
      activeSynapses.add(`synapse-${e.from}-${e.to}`);
      connectedNodes.add(e.from);
      // Secondary backward
      graph.edges.forEach(e2 => {
        if (e2.to === e.from) {
          activeSynapses.add(`synapse-${e2.from}-${e2.to}`);
          connectedNodes.add(e2.from);
        }
      });
    }
  });

  // Update SVG DOM classes
  svg.querySelectorAll('.synapse').forEach(s => {
    const isAct = activeSynapses.has(s.id);
    s.classList.toggle('synapse-firing', isAct);
    s.classList.toggle('dimmed', !isAct);
  });

  svg.querySelectorAll('.neuron-node').forEach(n => {
    const isTarget = n.dataset.id === targetId;
    const isConn = connectedNodes.has(n.dataset.id);
    n.classList.toggle('neuron-firing', isTarget);
    n.classList.toggle('neuron-activated', isConn && !isTarget);
    n.classList.toggle('dimmed', !isConn);
  });

  // Update guide banner badge with circuit summary
  const statusBadge = $('networkStatusBadge');
  if (statusBadge) {
    const targetNode = graph.nodes.find(n => n.id === targetId);
    if (targetNode) {
      const connSkills = Array.from(connectedNodes).map(id => graph.nodes.find(n => n.id === id)).filter(n => n && n.type === 'skill');
      const connCourses = Array.from(connectedNodes).map(id => graph.nodes.find(n => n.id === id)).filter(n => n && n.type === 'course');
      if (targetNode.type === 'role') {
        statusBadge.innerHTML = `<strong>Active Circuit:</strong> ${esc(targetNode.label)} &rarr; ${connSkills.length} Required Competencies &rarr; ${connCourses.length} Curricula`;
      } else if (targetNode.type === 'skill') {
        statusBadge.innerHTML = `<strong>Competency Filter:</strong> ${esc(targetNode.label)} &bull; Linked to ${connCourses.length} Curricula`;
      } else {
        statusBadge.innerHTML = `<strong>Curriculum Node:</strong> ${esc(targetNode.label)}`;
      }
    }
  }
}

function resetNeuralActivation() {
  activeNeuralNode = null;
  const svg = $('graphSvg');
  if (!svg) return;
  svg.querySelectorAll('.synapse').forEach(s => {
    s.classList.remove('synapse-firing', 'dimmed');
  });
  svg.querySelectorAll('.neuron-node').forEach(n => {
    n.classList.remove('neuron-firing', 'neuron-activated', 'dimmed');
  });
  const statusBadge = $('networkStatusBadge');
  if (statusBadge) {
    statusBadge.innerHTML = 'Interactive Network: Click any cadre post to activate neural pathway';
  }
}

// ── AI Copilot Pathway & Chat Controller ────────────────────────────
async function triggerCopilotPathway(currentRole, targetRole, query = '') {
  const roadmapEl = $('copilotRoadmap');
  const sourcesEl = $('copilotSourcesArea');
  if (!roadmapEl) return;

  roadmapEl.innerHTML = `
    <div class="cadre-analyzing-box">
      <div class="cadre-pulse-bar"></div>
      <b>Evaluating Cadre Competency Standards…</b>
      <p>Consulting civil service progression frameworks, competency deltas, and verified institutional curricula.</p>
    </div>
  `;
  if (sourcesEl) sourcesEl.innerHTML = '';

  try {
    const res = await api('/api/ai/career-copilot', {
      method: 'POST',
      body: {
        current_role: currentRole,
        target_role: targetRole,
        message: query
      }
    });

    if (res.status === 'success') {
      renderCopilotOutput(res);
    } else {
      roadmapEl.innerHTML = `<p class="error">Advisory Engine: ${esc(res.detail || 'Unable to generate pathway')}</p>`;
    }
  } catch (err) {
    roadmapEl.innerHTML = `<p class="error">Advisory Engine: ${esc(err.message)}</p>`;
  }
}

function renderCopilotOutput(data) {
  const roadmapEl = $('copilotRoadmap');
  const sourcesEl = $('copilotSourcesArea');
  if (!roadmapEl) return;

  // Format markdown in narrative
  let md = data.ai_analysis || '';
  let html = md
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^#### (.*$)/gim, '<h4>$1</h4>')
    .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/^\* (.*$)/gim, '<li>$1</li>')
    .replace(/<\/li>\n<li>/g, '</li><li>');

  html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

  roadmapEl.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid var(--line)">
      <span class="badge ${data.mode === 'live_gemini' ? 'badge-green' : 'badge-blue'}">${data.mode === 'live_gemini' ? 'Gemini Cognitive Engine' : 'Official Cadre Analytics'}</span>
      <small style="color:var(--muted)">Est. Duration: ${esc(data.estimated_duration)}</small>
    </div>
    ${html}
  `;

  // Render Verified Learning Sources
  if (sourcesEl && data.verified_sources?.length) {
    let sHtml = `
      <h4 style="margin:16px 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--ink)">
        Verified Official Sources to Learn From:
      </h4>
      <div class="sources-grid">
    `;

    data.verified_sources.forEach(s => {
      sHtml += `
        <div class="source-card">
          <div class="source-card-top">
            <h4>${esc(s.title)}</h4>
            <span class="source-provider">${esc(s.provider)}</span>
          </div>
          <p><b>Focus:</b> ${esc(s.focus)} &bull; <small style="color:var(--muted)">${esc(s.duration)}</small></p>
          <a href="${esc(s.url)}" target="_blank" rel="noreferrer" class="source-link-btn">
            Open Official Resource &rarr;
          </a>
        </div>
      `;
    });
    sHtml += '</div>';
    sourcesEl.innerHTML = sHtml;
  }
}

// Bind Copilot controls
document.addEventListener('DOMContentLoaded', () => {
  initCopilotHandlers();
});

function initCopilotHandlers() {
  const genBtn = $('copilotGenerateBtn');
  if (genBtn) {
    genBtn.onclick = () => {
      const curr = $('copilotCurrentRole')?.value || 'Junior Statistical Officer';
      const targ = $('copilotTargetRole')?.value || 'Senior Statistical Officer';
      triggerCopilotPathway(curr, targ);
    };
  }

  const chatForm = $('copilotChatForm');
  if (chatForm) {
    chatForm.onsubmit = e => {
      e.preventDefault();
      const inp = $('copilotChatInput');
      const q = inp?.value.trim();
      if (!q) return;
      inp.value = '';
      const curr = $('copilotCurrentRole')?.value || 'Junior Statistical Officer';
      const targ = $('copilotTargetRole')?.value || 'Senior Statistical Officer';
      triggerCopilotPathway(curr, targ, q);
    };
  }

  document.querySelectorAll('.chip').forEach(chip => {
    chip.onclick = () => {
      const prompt = chip.dataset.prompt;
      const currEl = $('copilotCurrentRole');
      const targEl = $('copilotTargetRole');
      if (prompt === 'JSO to SSO Transition') {
        if (currEl) currEl.value = 'Junior Statistical Officer';
        updateTargetOptions('Junior Statistical Officer', CADRE_ORDER);
        if (targEl) targEl.value = 'Senior Statistical Officer';
        triggerCopilotPathway('Junior Statistical Officer', 'Senior Statistical Officer');
      } else if (prompt === 'ISS Cadre Fast-Track') {
        const curr = currEl?.value || 'Senior Statistical Officer';
        updateTargetOptions(curr, CADRE_ORDER);
        if (targEl) targEl.value = 'ISS Officer';
        triggerCopilotPathway(curr, 'ISS Officer', 'Direct Indian Statistical Service (ISS) Cadre Progression Prerequisite & Roadmap');
      } else {
        const curr = currEl?.value || 'Junior Statistical Officer';
        const targ = targEl?.value || 'Senior Statistical Officer';
        triggerCopilotPathway(curr, targ, prompt);
      }
    };
  });
}

// ── Downloads / Exports ────────────────────────────────────────────
async function download(path, filename) {
  const res = await fetch(path, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error((await res.json()).detail || 'Export failed');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

$('exportOfficers').onclick = () => download('/api/export/officers.csv', 'statintel-officers.csv').catch(e => toast(e.message));
$('reportOfficerCsv').onclick = () => download('/api/export/officers.csv', 'statintel-officers.csv').catch(e => toast(e.message));
$('reportGapCsv').onclick = async () => {
  try {
    const data = await api('/api/gap-analysis');
    const rows = [
      ['skill', 'domain', 'profile_mentions', 'severity_score', 'severity_level', 'mention_ratio', 'source_status'],
      ...data.items.map(x => [x.skill, x.domain, x.profile_mentions, x.severity_score, x.severity_level, x.mention_ratio, x.source_status])
    ];
    const csv = rows.map(r => r.map(v => '"' + String(v ?? '').replace(/"/g, '""') + '"').join(',')).join('\r\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'statintel-gap-analysis.csv'; a.click();
    URL.revokeObjectURL(url);
  } catch (e) { toast(e.message); }
};
if ($('reportPitchPdf')) {
  $('reportPitchPdf').onclick = () => {
    window.open('/api/export/pitch-dossier.pdf', '_blank');
  };
}

// ── Plan My Pathway Controller ─────────────────────────────────────
let currentPathwayRoadmap = null;
let checkedPathwayItems = new Set();
let pathwayInitialized = false;

const FALLBACK_OFFICERS = [
  { id: 1, name: 'Dr. Ramesh Kumar Sharma', department: 'National Sample Survey Office', current_role: 'Senior Statistical Officer', target_role: 'Assistant Director', readiness: 68 },
  { id: 2, name: 'Priya Sundaram', department: 'Data Informatics & Innovation Division', current_role: 'Junior Statistical Officer', target_role: 'Senior Statistical Officer', readiness: 48 },
  { id: 3, name: 'Amitabh Verma', department: 'National Accounts Division', current_role: 'Assistant Director', target_role: 'Deputy Director', readiness: 74 },
  { id: 4, name: 'Sunita Rao', department: 'Economic Statistics Division', current_role: 'Junior Statistical Officer', target_role: 'Senior Statistical Officer', readiness: 52 },
  { id: 5, name: 'Vikramaditya Sen', department: 'Price & Cost of Living Division', current_role: 'Deputy Director', target_role: 'Director', readiness: 81 }
];

async function initPathwayPage() {
  try {
    if (!officers || !officers.length) {
      try {
        officers = await api('/api/officers');
      } catch (e) {
        console.warn('Using fallback officers for pathway:', e);
      }
    }
    if (!officers || !officers.length) {
      officers = FALLBACK_OFFICERS;
    }

    const sel = $('pathwayOfficerSelect');
    if (sel && (!sel.children.length || !pathwayInitialized)) {
      sel.innerHTML = officers.map(o => `<option value="${o.id}">${esc(o.name)} (${esc(o.department)})</option>`).join('');
      sel.onchange = () => onPathwayOfficerChange();

      if ($('generatePathwayBtn')) $('generatePathwayBtn').onclick = () => generatePathwayPlan();
      if ($('resetPathwayBtn')) $('resetPathwayBtn').onclick = () => resetPathwayPlan();
      if ($('downloadPathwayPdfBtn')) $('downloadPathwayPdfBtn').onclick = () => downloadPathwayPdf();

      // Check if logged in user is an Officer with an Authority-Assigned Pathway
      if (currentUser && currentUser.role === 'officer') {
        try {
          const myRes = await api('/api/pathway/my-pathway').catch(() => null);
          if (myRes && myRes.has_assigned && myRes.roadmap) {
            currentPathwayRoadmap = myRes.roadmap;
            const assignedBanner = $('officerAssignedPathwayBanner');
            if (assignedBanner) {
              assignedBanner.classList.remove('hidden');
              if ($('officerAssignedMeta')) {
                const dt = myRes.assigned_at ? new Date(myRes.assigned_at).toLocaleDateString() : 'Active';
                $('officerAssignedMeta').textContent = `Authorized by: ${myRes.assigned_by} (${dt})`;
              }
              if ($('officerAssignedNote')) {
                $('officerAssignedNote').textContent = `This curriculum was officially authorized for ${myRes.officer.name} (${myRes.officer.current_role} → ${myRes.officer.target_role}).`;
              }
              const dlBtn = $('officerDossierDownloadBtn');
              if (dlBtn) dlBtn.onclick = () => downloadPathwayPdf();
            }

            // Lock selector to officer
            sel.innerHTML = `<option value="${myRes.officer.id}">${esc(myRes.officer.name)} (${esc(myRes.officer.department)})</option>`;
            sel.disabled = true;
            if ($('pathwayCurrentRole')) $('pathwayCurrentRole').value = myRes.officer.current_role;
            if ($('pathwayTargetRoleSelect')) {
              $('pathwayTargetRoleSelect').innerHTML = `<option value="${esc(myRes.officer.target_role)}">${esc(myRes.officer.target_role)}</option>`;
              $('pathwayTargetRoleSelect').disabled = true;
            }

            renderPathwayDashboard(myRes.roadmap);
            loadPathwayChatHistory(myRes.officer.id);
            pathwayInitialized = true;
            return;
          }
        } catch (e) {
          console.warn('Could not load officer assigned pathway:', e);
        }
      }

      // Administrator Grant Access Handlers
      const grantPanel = $('pathwayAdminGrantPanel');
      const toggleGrantBtn = $('toggleGrantAccessBtn');
      const closeGrantBtn = $('closeGrantAccessBtn');
      const grantOfficerSel = $('grantUserOfficerSelect');

      if (toggleGrantBtn && grantPanel) {
        if (currentUser && currentUser.role === 'officer') {
          toggleGrantBtn.classList.add('hidden');
        } else {
          toggleGrantBtn.classList.remove('hidden');
          toggleGrantBtn.onclick = () => {
            grantPanel.classList.toggle('hidden');
            const elevationBanner = $('grantAdminElevationBanner');
            if (elevationBanner) {
              if (currentUser && currentUser.role !== 'admin') {
                elevationBanner.classList.remove('hidden');
              } else {
                elevationBanner.classList.add('hidden');
              }
            }
            if (!grantPanel.classList.contains('hidden') && grantOfficerSel) {
              grantOfficerSel.innerHTML = '<option value="">-- No linked officer profile (General study access) --</option>' +
                officers.map(o => `<option value="${o.id}">${esc(o.name)} (${esc(o.department)})</option>`).join('');
            }
          };
        }
      }
      if (closeGrantBtn && grantPanel) {
        closeGrantBtn.onclick = () => grantPanel.classList.add('hidden');
      }

      const promptElevateBtn = $('promptElevateAdminBtn');
      if (promptElevateBtn) {
        promptElevateBtn.onclick = () => openElevateModal(() => {
          const elevationBanner = $('grantAdminElevationBanner');
          if (elevationBanner) elevationBanner.classList.add('hidden');
        });
      }

      const grantForm = $('pathwayGrantAccessForm');
      if (grantForm) {
        grantForm.onsubmit = async e => {
          e.preventDefault();
          const emailInput = $('grantUserEmail');
          const email = emailInput?.value.trim();
          const offId = $('grantUserOfficerSelect')?.value ? parseInt($('grantUserOfficerSelect').value, 10) : null;
          const feedback = $('grantAccessFeedback');
          const resultBox = $('grantAccessResultBox');

          if (!email) return;
          if (feedback) feedback.textContent = 'Provisioning access…';

          try {
            const attachRoadmap = $('grantAttachRoadmap')?.checked ?? true;
            const res = await api('/api/pathway/grant-access', {
              method: 'POST',
              body: {
                email: email,
                officer_id: offId,
                target_role: $('pathwayTargetRoleSelect')?.value || 'Senior Statistical Officer',
                weekly_hours: parseInt($('pathwayWeeklyHours')?.value || '4', 10),
                preferred_style: $('pathwayStyle')?.value || 'applied',
                attach_current_roadmap: attachRoadmap,
                roadmap: currentPathwayRoadmap
              }
            });

            if (feedback) feedback.textContent = '';
            if (resultBox) {
              resultBox.classList.remove('hidden');
              let credsHtml = '';
              if (res.temporary_credentials) {
                credsHtml = `
                  <div style="margin:10px 0;padding:10px 12px;background:#ffffff;border:1px solid var(--line);border-radius:4px">
                    <b style="color:var(--ink)">Issued Login Credentials:</b><br>
                    Username: <code>${esc(res.temporary_credentials.username)}</code> &bull; 
                    Temporary Password: <code>${esc(res.temporary_credentials.temporary_password)}</code>
                  </div>
                `;
              }
              const fullDirectUrl = window.location.origin + res.direct_access_url;
              resultBox.innerHTML = `
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                  <strong style="color:var(--green);font-size:13px">✓ ${esc(res.message)}</strong>
                  <span class="badge ${res.assigned_pathway_attached ? 'badge-green' : 'badge-gray'}">
                    ${res.assigned_pathway_attached ? '🏛️ Official Curriculum Sealed & Attached' : 'Standard Access'}
                  </span>
                </div>
                <p style="margin:4px 0 0 0;color:var(--ink)">${esc(res.access_scope)}</p>
                ${credsHtml}
                <div style="margin-top:10px">
                  <label style="font-weight:700;font-size:11px;color:var(--muted)">One-Click Direct Access Link:</label>
                  <div style="display:flex;gap:8px;margin-top:4px">
                    <input id="directAccessLinkInput" readonly value="${esc(fullDirectUrl)}" style="width:100%;font-family:monospace;font-size:11px;padding:6px">
                    <button type="button" class="secondary" id="copyDirectLinkBtn" style="white-space:nowrap;font-size:11px">Copy Link</button>
                    <a href="${esc(res.direct_access_url)}" target="_blank" class="button primary" style="white-space:nowrap;font-size:11px;text-decoration:none">Test Access ↗</a>
                  </div>
                </div>
                <div style="margin-top:10px">
                  <button type="button" class="secondary" id="copyInviteNoteBtn" style="font-size:11px">📋 Copy Full Officer Invitation Note</button>
                </div>
                <div style="font-size:10px;color:var(--muted);margin-top:8px">Audit Log recorded under System Security Register.</div>
              `;

              $('copyDirectLinkBtn') && ($('copyDirectLinkBtn').onclick = () => {
                navigator.clipboard.writeText(fullDirectUrl);
                toast('Direct login link copied to clipboard!');
              });
              $('copyInviteNoteBtn') && ($('copyInviteNoteBtn').onclick = () => {
                navigator.clipboard.writeText(res.invitation_note);
                toast('Full invitation note copied to clipboard!');
              });
            }
            toast(`Access granted to ${email}`);
            emailInput.value = '';
          } catch (err) {
            if (feedback) feedback.textContent = `Error: ${err.message}`;
            if (err.message && err.message.toLowerCase().includes('admin')) {
              toast('Administrator authorization required. Opening elevation prompt…');
              openElevateModal(async () => {
                if (feedback) feedback.textContent = 'Retrying access grant with administrator privileges…';
                grantForm.requestSubmit();
              });
            } else {
              toast(`Grant failed: ${err.message}`);
            }
          }
        };
      }


      // YouTube Instant Search Filter
      const ytSearch = $('pathwayYtSearchInput');
      if (ytSearch) {
        ytSearch.oninput = () => {
          const q = ytSearch.value.toLowerCase().trim();
          filterPathwayYtList(q);
        };
      }

      const chatForm = $('pathwayChatForm');
      if (chatForm) {
        chatForm.onsubmit = e => {
          e.preventDefault();
          const inp = $('pathwayChatInput');
          const q = inp?.value.trim();
          if (!q) return;
          inp.value = '';
          sendPathwayAdvisorMessage(q);
        };
      }

      document.querySelectorAll('[data-pathway-prompt]').forEach(chip => {
        chip.onclick = () => {
          const prompt = chip.dataset.pathwayPrompt;
          if (prompt) sendPathwayAdvisorMessage(prompt);
        };
      });

      const clearBtn = $('clearChatBtn');
      if (clearBtn) clearBtn.onclick = () => clearPathwayChatHistory();

      pathwayInitialized = true;
      onPathwayOfficerChange();
    } else if (sel && !currentPathwayRoadmap) {
      onPathwayOfficerChange();
    }

  } catch (err) {
    console.error('Pathway init error:', err);
  }
}

function onPathwayOfficerChange() {
  const sel = $('pathwayOfficerSelect');
  if (!sel) return;
  const officerId = parseInt(sel.value, 10);
  const officerList = (officers && officers.length) ? officers : FALLBACK_OFFICERS;
  const officer = officerList.find(o => o.id === officerId) || officerList[0];
  if (!officer) return;

  const roleInput = $('pathwayCurrentRole');
  if (roleInput) roleInput.value = officer.current_role || 'Junior Statistical Officer';

  // Target role options using our official cadre hierarchy
  const targetSel = $('pathwayTargetRoleSelect');
  if (targetSel) {
    const currIdx = CADRE_ORDER.findIndex(x => x.toLowerCase() === (officer.current_role || '').toLowerCase());
    let higherRoles = [];
    if (currIdx !== -1) {
      higherRoles = CADRE_ORDER.filter((r, idx) => idx > currIdx);
    } else {
      higherRoles = CADRE_ORDER.filter(r => r.toLowerCase() !== (officer.current_role || '').toLowerCase());
    }
    if (!higherRoles.length) {
      higherRoles = ['Senior Cadre Specialization', 'Principal Statistical Advisor'];
    }
    targetSel.innerHTML = higherRoles.map(r => `<option value="${esc(r)}">${esc(r)}</option>`).join('');

    if (higherRoles.includes(officer.target_role)) {
      targetSel.value = officer.target_role;
    } else {
      targetSel.selectedIndex = 0;
    }
  }

  generatePathwayPlan();
  loadPathwayChatHistory(officerId);
}


async function generatePathwayPlan() {
  const sel = $('pathwayOfficerSelect');
  if (!sel) return;
  const officerId = parseInt(sel.value, 10) || 1;
  const targetRole = $('pathwayTargetRoleSelect')?.value || 'Senior Statistical Officer';
  const weeklyHours = parseInt($('pathwayWeeklyHours')?.value || '4', 10);
  const style = $('pathwayStyle')?.value || 'applied';

  // Dynamically deduce tier for content level
  const trLower = targetRole.toLowerCase();
  let level = 'operational';
  if (trLower.includes('deputy director') || trLower.includes('director') || trLower.includes('iss') || trLower.includes('advisor')) {
    level = 'executive';
  } else if (trLower.includes('assistant director') || trLower.includes('senior statistical')) {
    level = 'senior';
  }

  const container = $('pathwayPhasesContainer');
  if (container) {
    container.innerHTML = `
      <div class="cadre-analyzing-box" style="margin:20px">
        <div class="cadre-pulse-bar"></div>
        <b>Evaluating Competency Deficits & YouTube Curricula…</b>
        <p>Ranking accredited video lectures and computing quantitative readiness trajectory.</p>
      </div>
    `;
  }
  const ytContainer = $('pathwayYtList');
  if (ytContainer) {
    ytContainer.innerHTML = `
      <div class="empty-state" style="padding:24px;text-align:center;color:var(--muted)">
        Retrieving verified video lectures for target gaps…
      </div>
    `;
  }

  try {
    const res = await api('/api/pathway/generate', {
      method: 'POST',
      body: {
        officer_id: officerId,
        target_role: targetRole,
        weekly_hours: weeklyHours,
        preferred_style: style,
        content_level: level
      }
    });

    if (res.status === 'success') {
      currentPathwayRoadmap = res;
      checkedPathwayItems.clear();
      renderPathwayDashboard(res);
    } else {
      if (container) container.innerHTML = `<p class="error">Plan Generation Error: ${esc(res.detail || 'Failed')}</p>`;
    }
  } catch (err) {
    if (container) container.innerHTML = `<p class="error">Plan Generation Error: ${esc(err.message)}</p>`;
  }
}

function resetPathwayPlan() {
  checkedPathwayItems.clear();
  generatePathwayPlan();
  toast('Pathway reset to baseline standards');
}

let officerProgressData = null;

async function loadOfficerProgress(officerId) {
  if (!officerId) return;
  try {
    const res = await api(`/api/pathway/progress/${officerId}`);
    officerProgressData = res;

    // Update local officer in officers cache
    const off = officers.find(o => o.id === officerId);
    if (off) off.readiness = res.current_readiness;

    // Restore checked items
    checkedPathwayItems.clear();
    if (res.items && res.items.length) {
      res.items.forEach(it => {
        if (it.completed) {
          checkedPathwayItems.add(it.item_key);
          if (it.item_key.startsWith('video:')) {
            checkedPathwayItems.add(it.item_key.replace('video:', ''));
          } else if (it.item_key.startsWith('task:')) {
            checkedPathwayItems.add(it.item_key.replace('task:', ''));
          }
        }
      });
    }

    // Apply checked state to visible rows and checkboxes
    document.querySelectorAll('.phase-item-check').forEach(chk => {
      const id = chk.dataset.id;
      const isDone = checkedPathwayItems.has(id) || checkedPathwayItems.has('task:' + id) || checkedPathwayItems.has('video:' + id);
      chk.checked = isDone;
      chk.closest('tr')?.classList.toggle('item-completed', isDone);
    });

    // Update video cards in right column
    document.querySelectorAll('.yt-video-card').forEach(card => {
      const vid = card.dataset.vid;
      if (vid) {
        const isDone = checkedPathwayItems.has(vid) || checkedPathwayItems.has('video:' + vid);
        card.classList.toggle('yt-card-completed', isDone);
        const btn = card.querySelector('.btn-toggle-done');
        if (btn) {
          btn.classList.toggle('done', isDone);
          btn.textContent = isDone ? '✓ Completed' : 'Mark Done';
        }
      }
    });

    renderProgressHud(res);
    updatePathwayProgress();
  } catch (err) {
    console.warn('Could not load officer progress:', err);
  }
}

function renderProgressHud(data) {
  if (!data) return;
  if ($('hudReadinessVal')) $('hudReadinessVal').textContent = `${data.current_readiness}%`;
  if ($('hudUpliftBadge')) $('hudUpliftBadge').textContent = `+${data.readiness_uplift}% Uplift`;
  if ($('hudTargetRoleText')) $('hudTargetRoleText').textContent = data.target_role || '--';
  if ($('hudVideosWatched')) $('hudVideosWatched').textContent = `${data.completed_videos} done`;
  if ($('hudTasksDone')) $('hudTasksDone').textContent = `${data.completed_tasks} done`;
  if ($('hudCertsEarned')) $('hudCertsEarned').textContent = data.certificates_earned;
  if ($('hudReadinessBarText')) $('hudReadinessBarText').textContent = `${data.current_readiness}% (Base: ${data.base_readiness}%)`;
  if ($('hudTargetThresholdText')) $('hudTargetThresholdText').textContent = `Cadre Promotion Target: ${data.target_threshold}%`;

  const pctOfTarget = Math.min(100, Math.round((data.current_readiness / (data.target_threshold || 85)) * 100));
  if ($('hudProgressBar')) $('hudProgressBar').style.width = `${pctOfTarget}%`;

  const nextActionTitle = $('hudNextActionTitle');
  const nextActionBtn = $('hudNextActionBtn');

  if (nextActionTitle && nextActionBtn) {
    if (data.current_readiness >= data.target_threshold) {
      nextActionTitle.innerHTML = `<span style="color:#059669">🏆 <b>Cadre Promotion Threshold Achieved (${data.current_readiness}%)</b> — Ready for Departmental Promotion Review!</span>`;
      nextActionBtn.textContent = 'Download Certified Dossier 📄';
      nextActionBtn.onclick = () => $('downloadPathwayPdfBtn')?.click();
    } else {
      let foundAction = false;
      if (currentPathwayRoadmap && currentPathwayRoadmap.phases) {
        for (const ph of currentPathwayRoadmap.phases) {
          if (ph.items) {
            for (const it of ph.items) {
              const isDone = checkedPathwayItems.has(it.id) || checkedPathwayItems.has('video:' + it.id);
              if (!isDone) {
                nextActionTitle.innerHTML = `Watch lecture: <b>${esc(it.title)}</b> (${it.duration_min} min • ${esc(it.channel)})`;
                nextActionBtn.textContent = '▶ Start Video Lecture';
                nextActionBtn.onclick = () => openVideoPlayer(it.id, it.title, it.channel, it.verified_standard);
                foundAction = true;
                break;
              }
            }
          }
          if (foundAction) break;
        }

        if (!foundAction && currentPathwayRoadmap.phases.length) {
          const ph = currentPathwayRoadmap.phases[0];
          nextActionTitle.innerHTML = `Take Examination: <b>Phase ${ph.order} Competency Quiz</b> (${esc(ph.skill)})`;
          nextActionBtn.textContent = '📝 Take Assessment';
          nextActionBtn.onclick = () => openCompetencyQuiz(ph.skill, currentPathwayRoadmap.cadre_tier || 'operational', ph.order);
          foundAction = true;
        }
      }

      if (!foundAction) {
        nextActionTitle.textContent = 'Review curriculum and complete verified modules to elevate readiness.';
        nextActionBtn.textContent = 'Explore Curricula ↓';
        nextActionBtn.onclick = () => {
          $('pathwayPhasesContainer')?.scrollIntoView({ behavior: 'smooth' });
        };
      }
    }
  }
}

async function toggleItemPersistentProgress(officerId, itemType, itemKey, itemTitle, completed) {
  if (!officerId) return;
  try {
    const res = await api('/api/pathway/progress/toggle', {
      method: 'POST',
      body: {
        officer_id: officerId,
        item_type: itemType,
        item_key: itemKey,
        item_title: itemTitle || '',
        completed: completed
      }
    });

    if (completed) {
      checkedPathwayItems.add(itemKey);
      if (itemKey.startsWith('video:')) checkedPathwayItems.add(itemKey.replace('video:', ''));
      if (itemKey.startsWith('task:')) checkedPathwayItems.add(itemKey.replace('task:', ''));
      toast(`✓ Progress saved! Readiness increased to ${res.current_readiness}% (+${res.readiness_uplift}% total uplift)`);
    } else {
      checkedPathwayItems.delete(itemKey);
      if (itemKey.startsWith('video:')) checkedPathwayItems.delete(itemKey.replace('video:', ''));
      if (itemKey.startsWith('task:')) checkedPathwayItems.delete(itemKey.replace('task:', ''));
      toast(`Item unmarked. Readiness recalculated to ${res.current_readiness}%.`);
    }

    await loadOfficerProgress(officerId);
  } catch (err) {
    console.error('Failed to update progress:', err);
    toast(`Progress update error: ${err.message}`);
  }
}

function renderPathwayDashboard(data) {
  // Update metric strip
  if ($('pathwayCurrentReadiness')) $('pathwayCurrentReadiness').textContent = `${data.current_readiness}%`;
  if ($('pathwayProjectedReadiness')) $('pathwayProjectedReadiness').textContent = `${data.projected_readiness}%`;
  const delta = Math.max(0, Math.round(data.projected_readiness - data.current_readiness));
  if ($('pathwayUpliftBadge')) $('pathwayUpliftBadge').textContent = `+${delta}% uplift`;
  if ($('pathwayGapsCount')) $('pathwayGapsCount').textContent = data.phases ? data.phases.length : 0;
  if ($('pathwayWeeksCount')) $('pathwayWeeksCount').textContent = `${data.estimated_weeks} wks`;

  // Render Left Column: Phases & Practical Milestones Checklist
  const container = $('pathwayPhasesContainer');
  if (container) {
    if (!data.phases || !data.phases.length) {
      container.innerHTML = '<div class="empty-state" style="padding:24px;text-align:center">No competency deficits identified for this target cadre.</div>';
    } else {
      let html = `
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:14px;padding:10px 14px;background:var(--card);border:1px solid var(--line);border-radius:2px">
          <div>
            <span class="phase-severity-pill ${data.cadre_tier === 'executive' ? 'critical' : data.cadre_tier === 'senior' ? 'high' : 'moderate'}" style="font-size:10px;text-transform:uppercase">
              ${esc(data.tier_title || (data.cadre_tier ? data.cadre_tier.toUpperCase() : 'CADRE PROGRAM'))}
            </span>
            <div style="font-size:11.5px;color:var(--ink);margin-top:4px">
              Target Cadre: <b>${esc(data.target_role)}</b> &bull; Current Post: <b>${esc(data.current_role)}</b>
            </div>
          </div>
          <div style="font-size:11px;color:var(--muted);text-align:right">
            ${data.open_gaps_count || (data.phases ? data.phases.length : 0)} Competency Deficits Identified
          </div>
        </div>
      `;
      data.phases.forEach(ph => {
        const sevClass = ph.gap_severity >= 50 ? 'critical' : ph.gap_severity >= 30 ? 'high' : 'moderate';
        html += `
          <div class="pathway-phase-card">
            <div class="phase-card-header">
              <h3>Phase ${ph.order}: ${esc(ph.skill)}</h3>
              <span class="phase-severity-pill ${sevClass}">Severity: ${ph.gap_severity} &bull; ${esc(ph.severity_level)}</span>
            </div>
            <div class="phase-milestone-box">
              <b>Official Practical Milestone:</b>
              ${esc(ph.milestone)}
            </div>

            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin:12px 0 10px">
              <button type="button" class="btn-phase-quiz" data-skill="${esc(ph.skill)}" data-order="${ph.order}" data-tier="${esc(data.cadre_tier || 'operational')}">
                📝 Verify Competency & Take Phase Quiz
              </button>
              <div id="phaseCertBadge_${ph.order}"></div>
            </div>

            <table class="phase-items-table">
              <thead>
                <tr>
                  <th style="width:40px;text-align:center">Done</th>
                  <th>Verified Module</th>
                  <th>Duration</th>
                  <th>Score</th>
                  <th style="text-align:right">Action</th>
                </tr>
              </thead>
              <tbody>
        `;

        ph.items.forEach(it => {
          const isChecked = checkedPathwayItems.has(it.id);
          html += `
            <tr class="${isChecked ? 'item-completed' : ''}" id="row_${it.id}">
              <td style="text-align:center">
                <input type="checkbox" class="phase-item-check" data-id="${it.id}" ${isChecked ? 'checked' : ''}>
              </td>
              <td>
                <div class="phase-item-title">${esc(it.title)}</div>
                <div class="phase-item-channel">${esc(it.channel)} &bull; <b>${esc(it.verified_standard || 'Accredited')}</b></div>
              </td>
              <td><span class="priority low">${it.duration_min} min</span></td>
              <td><span class="phase-score-badge">${it.score}</span></td>
              <td style="text-align:right;white-space:nowrap">
                <button type="button" class="btn-watch-lecture" data-vid="${esc(it.id)}" data-title="${esc(it.title)}" data-channel="${esc(it.channel)}" data-standard="${esc(it.verified_standard || 'Accredited')}">
                  ▶ In-App Player
                </button>
                <a href="${esc(it.url)}" target="_blank" rel="noreferrer" class="source-link-btn" style="margin-left:4px">
                  ↗
                </a>
              </td>
            </tr>
          `;
        });

        html += `
              </tbody>
            </table>
          </div>
        `;
      });
      container.innerHTML = html;

      // Bind checkbox events
      container.querySelectorAll('.phase-item-check').forEach(chk => {
        chk.onchange = e => {
          const id = e.target.dataset.id;
          const officerId = currentPathwayRoadmap?.officer_id || 1;
          const row = e.target.closest('tr');
          const title = row?.querySelector('.phase-item-title')?.textContent || id;
          toggleItemPersistentProgress(officerId, 'phase_task', 'task:' + id, title, e.target.checked);
        };
      });

      // Bind Phase Quiz buttons
      container.querySelectorAll('.btn-phase-quiz').forEach(btn => {
        btn.onclick = () => {
          const skill = btn.dataset.skill;
          const order = parseInt(btn.dataset.order, 10);
          const tier = btn.dataset.tier;
          openCompetencyQuiz(skill, tier, order);
        };
      });

      // Bind in-app video player buttons
      container.querySelectorAll('.btn-watch-lecture').forEach(btn => {
        btn.onclick = () => {
          openVideoPlayer(btn.dataset.vid, btn.dataset.title, btn.dataset.channel, btn.dataset.standard);
        };
      });

      // Load existing certificates for this officer
      loadOfficerCertificates(data.officer_id);
    }
  }

  // Render Right Column: Dedicated YouTube Links Rectangle Box
  const ytContainer = $('pathwayYtList');
  if (ytContainer) {
    let allVideos = [];
    if (data.phases) {
      data.phases.forEach(ph => {
        if (ph.items) {
          ph.items.forEach(it => {
            allVideos.push({ ...it, phaseSkill: ph.skill, phaseOrder: ph.order });
          });
        }
      });
    }
    currentPathwayVideos = allVideos;
    renderPathwayVideosList(allVideos);
  }

  updatePathwayProgress();
  loadOfficerProgress(data.officer_id);
}

let currentPathwayVideos = [];

function renderPathwayVideosList(videos) {
  const ytContainer = $('pathwayYtList');
  if (!ytContainer) return;
  if (!videos.length) {
    ytContainer.innerHTML = '<div class="empty-state" style="padding:20px;text-align:center;color:var(--muted)">No video modules matching search.</div>';
    return;
  }
  ytContainer.innerHTML = videos.map(it => {
    const isDone = checkedPathwayItems.has(it.id) || checkedPathwayItems.has('video:' + it.id);
    return `
      <div class="yt-video-card ${isDone ? 'yt-card-completed' : ''}" data-vid="${esc(it.id)}">
        <div class="yt-card-top">
          <h4 class="yt-card-title">${esc(it.title)}</h4>
          <span class="yt-duration-badge">${it.duration_min} min</span>
        </div>
        <div class="yt-card-meta">
          <span class="yt-card-channel">${esc(it.channel)}</span>
          <span class="yt-card-standard">${esc(it.verified_standard || 'Accredited MoSPI/ISI Standard')}</span>
        </div>
        <div style="font-size:9.5px;color:var(--muted);line-height:1.4">
          Phase ${it.phaseOrder}: <b>${esc(it.phaseSkill)}</b> &bull; Quality: <b>${it.score}/100</b>
        </div>
        <div class="yt-card-actions">
          <button type="button" class="btn-toggle-done ${isDone ? 'done' : ''}" data-vid="${esc(it.id)}" data-title="${esc(it.title)}">
            ${isDone ? '✓ Completed' : 'Mark Done'}
          </button>
          <div style="display:flex;gap:4px">
            <button type="button" class="btn-card-play button primary" style="font-size:10px;padding:3px 8px" data-vid="${esc(it.id)}" data-title="${esc(it.title)}" data-channel="${esc(it.channel)}" data-standard="${esc(it.verified_standard || 'Accredited')}">
              ▶ Play
            </button>
            <a href="${esc(it.url)}" target="_blank" rel="noreferrer" class="btn-card-note" style="text-decoration:none">
              YouTube ↗
            </a>
          </div>
        </div>
      </div>
    `;
  }).join('');

  ytContainer.querySelectorAll('.btn-toggle-done').forEach(btn => {
    btn.onclick = () => {
      const vid = btn.dataset.vid;
      const title = btn.dataset.title;
      const officerId = currentPathwayRoadmap?.officer_id || 1;
      const isDone = checkedPathwayItems.has(vid) || checkedPathwayItems.has('video:' + vid);
      toggleItemPersistentProgress(officerId, 'video_lecture', 'video:' + vid, title, !isDone);
    };
  });

  ytContainer.querySelectorAll('.btn-card-play').forEach(btn => {
    btn.onclick = () => {
      openVideoPlayer(btn.dataset.vid, btn.dataset.title, btn.dataset.channel, btn.dataset.standard);
    };
  });
}

function filterPathwayYtList(query) {
  if (!query) {
    renderPathwayVideosList(currentPathwayVideos);
    return;
  }
  const filtered = currentPathwayVideos.filter(v => 
    (v.title && v.title.toLowerCase().includes(query)) ||
    (v.channel && v.channel.toLowerCase().includes(query)) ||
    (v.phaseSkill && v.phaseSkill.toLowerCase().includes(query)) ||
    (v.focus && v.focus.toLowerCase().includes(query))
  );
  renderPathwayVideosList(filtered);
}

function updatePathwayProgress() {
  if (!currentPathwayRoadmap || !currentPathwayRoadmap.phases) return;
  let totalItems = 0;
  currentPathwayRoadmap.phases.forEach(ph => totalItems += (ph.items ? ph.items.length : 0));
  const doneCount = checkedPathwayItems.size;
  const pct = totalItems > 0 ? Math.round((doneCount / totalItems) * 100) : 0;

  const textEl = $('pathwayProgressText');
  const barEl = $('pathwayProgressBarFill');
  if (textEl) textEl.textContent = `${doneCount} of ${totalItems} modules completed (${pct}%)`;
  if (barEl) barEl.style.width = `${pct}%`;
}

function appendPathwayChatMessage(role, htmlContent) {
  const stream = $('pathwayChatStream');
  if (!stream) return;
  const msgEl = document.createElement('div');
  msgEl.className = `chat-msg ${role === 'user' ? 'user-msg' : 'advisor-msg'}`;
  const headerText = role === 'user' ? 'OFFICER / USER' : 'STATINTEL ADVISOR';
  msgEl.innerHTML = `
    <div class="chat-msg-header">${headerText}</div>
    <div class="chat-bubble">${htmlContent}</div>
  `;
  stream.appendChild(msgEl);
  stream.scrollTop = stream.scrollHeight;
  return msgEl;
}

async function sendPathwayAdvisorMessage(userMsg) {
  if (!currentPathwayRoadmap) {
    toast('Please wait for the pathway roadmap to load');
    return;
  }
  const stream = $('pathwayChatStream');
  const statusBadge = $('pathwayAdvisorStatusBadge');

  // Append user message to stream
  appendPathwayChatMessage('user', esc(userMsg));

  // Append thinking bubble
  let thinkingEl = null;
  if (stream) {
    thinkingEl = document.createElement('div');
    thinkingEl.className = 'chat-msg advisor-msg';
    thinkingEl.innerHTML = `
      <div class="chat-msg-header">STATINTEL ADVISOR &bull; VERIFYING</div>
      <div class="chat-bubble" style="color:var(--muted)">
        Consulting mathematical prerequisites, gap severity, and accredited video pools…
      </div>
    `;
    stream.appendChild(thinkingEl);
    stream.scrollTop = stream.scrollHeight;
  }

  if (statusBadge) {
    statusBadge.textContent = 'Consulting Cadre Advisor…';
    statusBadge.className = 'badge badge-blue';
  }

  try {
    const res = await api('/api/pathway/chat/send', {
      method: 'POST',
      body: {
        officer_id: currentPathwayRoadmap?.officer_id || 1,
        message: userMsg,
        roadmap: currentPathwayRoadmap
      }
    });

    if (thinkingEl) thinkingEl.remove();

    if (res.status === 'success') {
      appendPathwayChatMessage('advisor', `<p style="margin:0">${esc(res.reply)}</p>`);
      if (statusBadge) {
        statusBadge.textContent = 'Grounded AI Advisor';
        statusBadge.className = 'badge badge-green';
      }
    } else {
      appendPathwayChatMessage('advisor', `<p class="error" style="margin:0">Advisor Notice: ${esc(res.detail || 'Unable to process query against engine.')}</p>`);
      if (statusBadge) {
        statusBadge.textContent = 'Engine Notice';
        statusBadge.className = 'badge badge-red';
      }
    }
  } catch (err) {
    if (thinkingEl) thinkingEl.remove();
    appendPathwayChatMessage('advisor', `<p class="error" style="margin:0">Advisor Error: ${esc(err.message)}</p>`);
    if (statusBadge) {
      statusBadge.textContent = 'Error';
      statusBadge.className = 'badge badge-red';
    }
  }
}

async function loadPathwayChatHistory(officerId) {
  if (!officerId) return;
  const stream = $('pathwayChatStream');
  if (!stream) return;
  try {
    const history = await api(`/api/pathway/chat/history/${officerId}`).catch(() => []);
    stream.innerHTML = '';
    if (!history || !history.length) {
      appendPathwayChatMessage('advisor', `
        <b>StatIntel Grounded Pathway Advisor Ready</b>
        <p style="margin:4px 0 0 0">
          I am your Cadre Development Advisor for National Statistical Systems. Ask me about prerequisites, promotional standards, recommended project milestones, or why specific accredited videos are recommended for your career progression.
        </p>
      `);
    } else {
      history.forEach(m => {
        appendPathwayChatMessage(m.sender, `<p style="margin:0">${esc(m.message)}</p>`);
      });
    }
  } catch (e) {
    console.warn('Could not load chat history:', e);
  }
}

async function clearPathwayChatHistory() {
  const officerId = currentPathwayRoadmap?.officer_id || 1;
  if (!confirm('Clear all conversation history with your AI advisor?')) return;
  try {
    await api(`/api/pathway/chat/clear/${officerId}`, { method: 'DELETE' });
    toast('Chat history cleared.');
    loadPathwayChatHistory(officerId);
  } catch (e) {
    toast(`Clear error: ${e.message}`);
  }
}


async function downloadPathwayPdf() {
  if (!currentPathwayRoadmap) {
    toast('Please generate a pathway first');
    return;
  }

  // Inject checkbox status into roadmap for PDF export
  const exportRoadmap = JSON.parse(JSON.stringify(currentPathwayRoadmap));
  if (exportRoadmap.phases) {
    exportRoadmap.phases.forEach(ph => {
      if (ph.items) {
        ph.items.forEach(it => {
          it.status = checkedPathwayItems.has(it.id) ? 'completed' : 'todo';
          it.checked = checkedPathwayItems.has(it.id);
        });
      }
    });
  }

  try {
    toast('Generating Official Pathway Dossier PDF…');
    const res = await fetch('/api/pathway/export-pdf', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ roadmap: exportRoadmap })
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'PDF Export failed');
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `statintel-pathway-checklist-officer-${exportRoadmap.officer_id || 'dossier'}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
    toast('Dossier PDF downloaded successfully');
  } catch (err) {
    toast(`Export error: ${err.message}`);
  }
}

// ── Competency Assessment & Certification Controller ─────────────────────
let activeQuizData = null;
let activeQuizAnswers = {};
let activeQuizStep = 0;
let lastEarnedCertUuid = null;
let currentActiveVideoId = null;

async function openCompetencyQuiz(skillName, cadreTier, phaseOrder) {
  const sel = $('pathwayOfficerSelect');
  const officerId = parseInt(sel?.value || '1', 10);
  const officerList = (officers && officers.length) ? officers : FALLBACK_OFFICERS;
  const off = officerList.find(o => o.id === officerId) || officerList[0];

  try {
    toast(`Loading Competency Examination for ${skillName}…`);
    const data = await api(`/api/assessment/quiz?skill=${encodeURIComponent(skillName)}&tier=${encodeURIComponent(cadreTier)}&phase=${phaseOrder}&officer_id=${officerId}`);
    
    activeQuizData = { ...data, officerId, targetRole: off?.target_role || '' };
    activeQuizAnswers = {};
    activeQuizStep = 0;

    // Setup modal headers
    if ($('quizSkillTitle')) $('quizSkillTitle').textContent = `Phase ${phaseOrder}: ${skillName}`;
    if ($('quizMetaBadges')) {
      const tierBadge = `<span class="badge ${cadreTier === 'executive' ? 'badge-red' : cadreTier === 'senior' ? 'badge-blue' : 'badge-green'}" style="text-transform:uppercase">${cadreTier} Tier</span>`;
      const officerBadge = `<span class="badge badge-gray">Candidate: ${esc(off?.name || 'Officer')}</span>`;
      $('quizMetaBadges').innerHTML = `${tierBadge} ${officerBadge}`;
    }

    // Toggle views
    $('quizActiveView')?.classList.remove('hidden');
    $('quizActiveActions')?.classList.remove('hidden');
    $('quizResultView')?.classList.add('hidden');
    $('quizResultActions')?.classList.add('hidden');

    renderQuizStep(0);
    $('quizModalBack')?.classList.remove('hidden');
  } catch (err) {
    toast(`Assessment error: ${err.message}`);
  }
}

function renderQuizStep(stepIndex) {
  if (!activeQuizData || !activeQuizData.questions || !activeQuizData.questions.length) return;
  activeQuizStep = Math.max(0, Math.min(stepIndex, activeQuizData.questions.length - 1));
  const total = activeQuizData.questions.length;
  const q = activeQuizData.questions[activeQuizStep];

  // Update progress bar
  if ($('quizStepIndicator')) $('quizStepIndicator').textContent = `Question ${activeQuizStep + 1} of ${total}`;
  if ($('quizTrackFill')) $('quizTrackFill').style.width = `${Math.round(((activeQuizStep + 1) / total) * 100)}%`;

  // Render question and options
  const container = $('quizQuestionContainer');
  if (container) {
    const selected = activeQuizAnswers[String(q.id)];
    let optionsHtml = '';
    q.options.forEach((opt, idx) => {
      const isSel = (selected === idx);
      optionsHtml += `
        <label class="quiz-option-card ${isSel ? 'selected' : ''}" onclick="selectQuizOption('${q.id}', ${idx})">
          <input type="radio" name="quiz_opt_${q.id}" value="${idx}" ${isSel ? 'checked' : ''}>
          <span>${esc(opt)}</span>
        </label>
      `;
    });

    container.innerHTML = `
      <div class="quiz-question-box">
        <div class="quiz-question-text">${activeQuizStep + 1}. ${esc(q.question)}</div>
        <div class="quiz-options-group">
          ${optionsHtml}
        </div>
      </div>
    `;
  }

  // Button states
  if ($('quizPrevBtn')) $('quizPrevBtn').disabled = (activeQuizStep === 0);
  const isLast = (activeQuizStep === total - 1);
  if ($('quizNextBtn')) $('quizNextBtn').classList.toggle('hidden', isLast);
  if ($('quizSubmitBtn')) $('quizSubmitBtn').classList.toggle('hidden', !isLast);
}

function selectQuizOption(qid, optIndex) {
  activeQuizAnswers[String(qid)] = optIndex;
  renderQuizStep(activeQuizStep);
}

async function submitCompetencyQuiz() {
  if (!activeQuizData) return;
  const total = activeQuizData.questions.length;
  const answered = Object.keys(activeQuizAnswers).length;
  if (answered < total) {
    if (!confirm(`You have answered ${answered} of ${total} questions. Submit anyway?`)) {
      return;
    }
  }

  try {
    toast('Evaluating examination against official standards…');
    const result = await api('/api/assessment/submit', {
      method: 'POST',
      body: {
        officer_id: activeQuizData.officerId,
        skill_name: activeQuizData.skill_name,
        cadre_tier: activeQuizData.cadre_tier,
        phase_order: activeQuizData.phase_order,
        target_role: activeQuizData.targetRole,
        answers: activeQuizAnswers
      }
    });

    lastEarnedCertUuid = result.certificate_uuid;

    // Hide active question view, show result view
    $('quizActiveView')?.classList.add('hidden');
    $('quizActiveActions')?.classList.add('hidden');
    $('quizResultView')?.classList.remove('hidden');
    $('quizResultActions')?.classList.remove('hidden');

    const banner = $('quizResultBanner');
    if (banner) {
      if (result.passed) {
        banner.className = 'quiz-result-card passed';
        banner.innerHTML = `
          <div class="quiz-score-circle">${result.score}%</div>
          <h3 style="color:#065f46;font-size:20px;margin-bottom:6px">Verified Cadre Competency Approved! ✓</h3>
          <p style="color:#047857;font-size:13px;max-width:520px;margin:0 auto">
            Congratulations! You scored ${result.score}% (${result.correct_count}/${result.total_questions} correct), achieving the official standard.
            <b>+${result.readiness_gain}% readiness uplift</b> has been credited to your official cadre profile.
          </p>
          <div style="margin-top:10px;font-size:11.5px;color:#065f46">
            Official Credential Issued: <b>${result.certificate_uuid}</b>
          </div>
        `;
        if ($('quizDownloadCertBtn')) {
          $('quizDownloadCertBtn').classList.remove('hidden');
          $('quizDownloadCertBtn').onclick = () => downloadCertificate(result.certificate_uuid);
        }
      } else {
        banner.className = 'quiz-result-card failed';
        banner.innerHTML = `
          <div class="quiz-score-circle">${result.score}%</div>
          <h3 style="color:#991b1b;font-size:20px;margin-bottom:6px">Examination Incomplete (${result.score}%)</h3>
          <p style="color:#b91c1c;font-size:13px;max-width:520px;margin:0 auto">
            Score achieved: ${result.score}% (${result.correct_count}/${result.total_questions} correct).
            Passing threshold is 80%. Review the official rationales below and re-attempt when ready.
          </p>
        `;
        if ($('quizDownloadCertBtn')) $('quizDownloadCertBtn').classList.add('hidden');
      }
    }

    // Explanations list
    const explList = $('quizExplanationsList');
    if (explList && result.explanations) {
      explList.innerHTML = `
        <h4 style="font-size:13px;text-transform:uppercase;color:var(--text-muted);margin-bottom:12px">Detailed Methodological Review</h4>
        ${result.explanations.map((exp, idx) => `
          <div class="quiz-expl-item ${exp.is_correct ? 'is-correct' : 'is-incorrect'}">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
              <b>Question ${idx + 1}: ${esc(exp.question)}</b>
              <span class="badge ${exp.is_correct ? 'badge-green' : 'badge-red'}">${exp.is_correct ? 'Correct ✓' : 'Incorrect ✗'}</span>
            </div>
            <div style="font-size:12px;color:var(--ink);margin-bottom:6px">
              <b>Your Answer:</b> ${exp.selected_index !== null && exp.selected_index !== undefined ? esc(exp.options[exp.selected_index] || 'None') : '<em>Unanswered</em>'}
            </div>
            ${!exp.is_correct ? `<div style="font-size:12px;color:#059669;margin-bottom:6px"><b>Correct Answer:</b> ${esc(exp.options[exp.correct_index])}</div>` : ''}
            <div style="font-size:11.5px;color:var(--text-muted);background:#f8fafc;padding:8px 10px;border-radius:4px;border:1px solid #e2e8f0">
              <b>Methodological Rationale:</b> ${esc(exp.rationale)}
            </div>
          </div>
        `).join('')}
      `;
    }

    // Update officer readiness dynamically in memory and UI
    if (result.passed) {
      if ($('pathwayCurrentReadiness')) $('pathwayCurrentReadiness').textContent = `${result.new_readiness}%`;
      const off = officers.find(o => o.id === result.officer_id);
      if (off) off.readiness = result.new_readiness;
      loadOfficerCertificates(result.officer_id);
    }
  } catch (err) {
    toast(`Submission error: ${err.message}`);
  }
}

async function downloadCertificate(certUuid) {
  if (!certUuid) return;
  try {
    toast('Generating Official Vector PDF Certificate…');
    const res = await fetch(`/api/assessment/certificate/${encodeURIComponent(certUuid)}/pdf`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) throw new Error('Failed to generate certificate');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `StatIntel-Certificate-${certUuid}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
    toast('Certificate downloaded successfully');
  } catch (err) {
    toast(`Certificate error: ${err.message}`);
  }
}

async function loadOfficerCertificates(officerId) {
  if (!officerId) return;
  try {
    const certs = await api(`/api/assessment/certificates/officer/${officerId}`);
    if (certs && certs.length) {
      certs.forEach(c => {
        // Find matching phase cards or badge locations
        document.querySelectorAll('.btn-phase-quiz').forEach(btn => {
          if (btn.dataset.skill.toLowerCase() === c.skill_name.toLowerCase()) {
            const badgeBox = $(`phaseCertBadge_${btn.dataset.order}`);
            if (badgeBox) {
              badgeBox.innerHTML = `
                <button type="button" class="cert-badge-pill" onclick="downloadCertificate('${c.cert_uuid}')" title="Click to download certificate">
                  🎓 Verified (${c.score}%) • ${c.cert_uuid}
                </button>
              `;
            }
          }
        });
      });
    }
  } catch (err) {
    console.warn('Could not load officer certificates:', err);
  }
}

// ── In-App Video Modal Controller ─────────────────────────────────────────
function openVideoPlayer(videoId, title, channel, standard) {
  currentActiveVideoId = videoId;
  const modal = $('videoModalBack');
  const iframe = $('videoModalIframe');
  if (iframe) iframe.src = `https://www.youtube.com/embed/${videoId}?autoplay=1`;
  if ($('videoModalTitle')) $('videoModalTitle').textContent = title || 'Verified Video Lecture';
  if ($('videoModalStandard')) $('videoModalStandard').textContent = standard || 'VERIFIED CURRICULUM LECTURE';
  if ($('videoModalMeta')) $('videoModalMeta').textContent = `Channel: ${channel} • Quality Standard: ${standard}`;
  
  const chk = $('videoMarkCompleteCheckbox');
  if (chk) {
    const isDone = checkedPathwayItems.has(videoId) || checkedPathwayItems.has('video:' + videoId);
    chk.checked = isDone;
    chk.onchange = () => {
      const officerId = currentPathwayRoadmap?.officer_id || 1;
      toggleItemPersistentProgress(officerId, 'video_lecture', 'video:' + videoId, title, chk.checked);
    };
  }

  const extLink = $('videoExternalLink');
  if (extLink) extLink.href = `https://www.youtube.com/watch?v=${videoId}`;

  modal?.classList.remove('hidden');
}

function closeVideoPlayer() {
  const iframe = $('videoModalIframe');
  if (iframe) iframe.src = '';  // Stops video playback immediately
  $('videoModalBack')?.classList.add('hidden');
}

let onElevateSuccessCallback = null;

function openElevateModal(callback = null) {
  onElevateSuccessCallback = callback;
  const back = $('elevateModalBack');
  const targetLabel = $('elevateUserTarget');
  const errEl = $('elevateError');
  const passInp = $('elevateAdminPasswordInput');
  if (errEl) errEl.textContent = '';
  if (passInp) passInp.value = '';
  if (targetLabel && currentUser) {
    targetLabel.textContent = `${currentUser.full_name || currentUser.username} (@${currentUser.username})`;
  }
  if (back) back.classList.remove('hidden');
  if (passInp) setTimeout(() => passInp.focus(), 50);
}

function closeElevateModal() {
  const back = $('elevateModalBack');
  if (back) back.classList.add('hidden');
  onElevateSuccessCallback = null;
}

// Wire Global Listeners for Quiz, Video, & Elevation Modals
document.addEventListener('DOMContentLoaded', () => {
  $('quizPrevBtn') && ($('quizPrevBtn').onclick = () => renderQuizStep(activeQuizStep - 1));
  $('quizNextBtn') && ($('quizNextBtn').onclick = () => renderQuizStep(activeQuizStep + 1));
  $('quizSubmitBtn') && ($('quizSubmitBtn').onclick = () => submitCompetencyQuiz());
  $('quizModalClose') && ($('quizModalClose').onclick = () => $('quizModalBack')?.classList.add('hidden'));
  $('quizCancelBtn') && ($('quizCancelBtn').onclick = () => $('quizModalBack')?.classList.add('hidden'));
  $('quizCloseResultBtn') && ($('quizCloseResultBtn').onclick = () => $('quizModalBack')?.classList.add('hidden'));

  $('videoModalClose') && ($('videoModalClose').onclick = closeVideoPlayer);
  $('videoCloseBtn') && ($('videoCloseBtn').onclick = closeVideoPlayer);
  
  $('elevateModalClose') && ($('elevateModalClose').onclick = closeElevateModal);
  $('elevateCancelBtn') && ($('elevateCancelBtn').onclick = closeElevateModal);

  // Close modals on clicking backdrop
  $('quizModalBack') && ($('quizModalBack').onclick = e => {
    if (e.target === $('quizModalBack')) $('quizModalBack').classList.add('hidden');
  });
  $('videoModalBack') && ($('videoModalBack').onclick = e => {
    if (e.target === $('videoModalBack')) closeVideoPlayer();
  });
  $('elevateModalBack') && ($('elevateModalBack').onclick = e => {
    if (e.target === $('elevateModalBack')) closeElevateModal();
  });

  const elevateForm = $('elevateAdminForm');
  if (elevateForm) {
    elevateForm.onsubmit = async e => {
      e.preventDefault();
      const passInp = $('elevateAdminPasswordInput');
      const errEl = $('elevateError');
      const pwd = passInp?.value || '';
      if (!pwd) return;
      if (errEl) errEl.textContent = 'Verifying administrator credentials…';
      try {
        const res = await api('/api/auth/elevate', {
          method: 'POST',
          body: { admin_password: pwd }
        });
        token = res.access_token;
        localStorage.setItem('statintel_token', token);
        currentUser.role = 'admin';

        const displayName = currentUser.full_name || currentUser.username;
        if ($('userLabel')) $('userLabel').textContent = displayName + ' · admin';
        if ($('userRole')) $('userRole').textContent = 'admin';

        const elevateBtn = $('elevateAdminBtn');
        if (elevateBtn) elevateBtn.classList.add('hidden');
        const banner = $('grantAdminElevationBanner');
        if (banner) banner.classList.add('hidden');

        toast('Account elevated to Administrator!');
        closeElevateModal();

        if (onElevateSuccessCallback) {
          const cb = onElevateSuccessCallback;
          onElevateSuccessCallback = null;
          cb();
        }
      } catch (err) {
        if (errEl) errEl.textContent = err.message || 'Elevation failed';
        toast(`Elevation error: ${err.message}`);
      }
    };
  }
});

// ── Cadre Succession & Strategic Intelligence ───────────────────────
let currentSuccessionData = null;
let currentDepartmentWeights = null;

async function loadSuccessionIntelligence() {
  const cardsContainer = $('successionMatrixCards');
  const deptsContainer = $('deptWeightsList');
  if (cardsContainer) cardsContainer.innerHTML = '<div style="text-align:center;padding:30px;color:var(--muted)">Computing cadre vulnerability matrix & bench strength ratios…</div>';
  if (deptsContainer) deptsContainer.innerHTML = '<div style="text-align:center;padding:30px;color:var(--muted)">Loading departmental skill criticality weights…</div>';

  try {
    const [matrixRes, weightsRes] = await Promise.all([
      api('/api/succession/vulnerability-matrix'),
      api('/api/succession/department-weights')
    ]);

    currentSuccessionData = matrixRes;
    currentDepartmentWeights = weightsRes;

    renderSuccessionSummary(matrixRes.overall_summary);
    renderSuccessionMatrix(matrixRes.succession_matrix);
    renderDepartmentWeights(weightsRes.departments);
  } catch (err) {
    if (cardsContainer) cardsContainer.innerHTML = `<div class="error" style="padding:20px">Failed to load succession matrix: ${esc(err.message)}</div>`;
    if (deptsContainer) deptsContainer.innerHTML = `<div class="error" style="padding:20px">Failed to load department weights: ${esc(err.message)}</div>`;
    toast(`Error: ${err.message}`);
  }
}

function renderSuccessionSummary(summary) {
  if (!summary) return;
  if ($('succTotalSanctioned')) $('succTotalSanctioned').textContent = summary.total_sanctioned_evaluated ?? '—';
  if ($('succTotalReady')) $('succTotalReady').textContent = summary.total_ready_feeder_officers ?? '—';
  if ($('succOverallRatio')) {
    const r = summary.overall_bench_strength_ratio ?? 0;
    $('succOverallRatio').textContent = `${r.toFixed(2)}×`;
    $('succOverallRatio').style.color = r < 0.5 ? 'var(--accent)' : (r < 1.0 ? 'var(--amber)' : 'var(--green)');
  }
  if ($('succCriticalDeficits')) $('succCriticalDeficits').textContent = `${summary.critical_vulnerabilities ?? 0} Cadres`;
}

function renderSuccessionMatrix(matrix) {
  const container = $('successionMatrixCards');
  if (!container) return;
  if (!matrix || !matrix.length) {
    container.innerHTML = '<p class="muted" style="padding:20px;text-align:center">No cadre succession tiers defined.</p>';
    return;
  }

  container.innerHTML = matrix.map(m => {
    const ratio = m.bench_strength_ratio || 0;
    const pctBar = Math.min(Math.round((ratio / 2.0) * 100), 100);
    const riskBadgeClass = m.risk_level === 'CRITICAL' ? 'badge-red' : (m.risk_level === 'VULNERABLE' ? 'badge-amber' : (m.risk_level === 'HEALTHY' ? 'badge-blue' : 'badge-green'));

    const candidateRows = (m.top_candidates && m.top_candidates.length > 0)
      ? m.top_candidates.map(c => `
          <div style="display:flex;align-items:center;justify-content:space-between;padding:7px 10px;background:#ffffff;border:1px solid var(--line);border-radius:4px;margin-bottom:6px;font-size:12px">
            <div>
              <b style="color:var(--ink);cursor:pointer" onclick="openDrawer(${c.id})">${esc(c.name)}</b>
              <div style="font-size:10.5px;color:var(--muted)">${esc(c.department)} · ${c.years_in_role} yrs in role</div>
            </div>
            <div style="display:flex;align-items:center;gap:8px">
              <span style="font-weight:700;font-size:12px;color:${c.readiness >= 75 ? 'var(--green)' : (c.readiness >= 60 ? 'var(--amber)' : 'var(--accent)')}">${c.readiness}%</span>
              <span class="badge ${c.status === 'ready' ? 'badge-green' : (c.status === 'near_ready' ? 'badge-amber' : '')}" style="font-size:9.5px;padding:2px 6px">
                ${c.status === 'ready' ? '✓ Ready' : (c.status === 'near_ready' ? 'Pipeline' : 'Developing')}
              </span>
            </div>
          </div>
        `).join('')
      : '<p class="muted" style="font-size:11.5px;margin:6px 0">No feeder candidates actively mapped to this tier.</p>';

    return `
      <article class="panel" style="border-top:3px solid ${m.risk_color};display:flex;flex-direction:column;justify-content:space-between">
        <div>
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
            <div>
              <span class="badge" style="font-size:10px;text-transform:uppercase;background:var(--panel2);color:var(--ink);margin-bottom:4px;display:inline-block">
                ${esc(m.cadre_tier)}
              </span>
              <h3 style="margin:2px 0 0 0;font-size:15px;color:var(--ink)">
                ${esc(m.feeder_cadre)} &rarr; <span style="color:var(--accent)">${esc(m.target_cadre)}</span>
              </h3>
            </div>
            <span class="badge ${riskBadgeClass}" style="font-size:10.5px;font-weight:700">
              ${esc(m.risk_level)}
            </span>
          </div>

          <p class="muted" style="font-size:11.5px;line-height:1.45;margin-bottom:12px">
            ${esc(m.responsibilities)}
          </p>

          <!-- Bench Strength Metric Card -->
          <div style="background:#ffffff;border:1px solid var(--line);border-radius:4px;padding:12px;margin-bottom:12px">
            <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px">
              <span style="font-size:11px;font-weight:700;text-transform:uppercase;color:var(--muted)">Bench Strength Ratio:</span>
              <b style="font-size:17px;color:${m.risk_color}">${ratio.toFixed(2)}×</b>
            </div>
            <div style="width:100%;height:8px;background:#e5e7eb;border-radius:999px;overflow:hidden;margin-bottom:8px">
              <div style="width:${pctBar}%;height:100%;background:${m.risk_color};border-radius:999px;transition:width 0.4s ease"></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:10.5px;color:var(--muted)">
              <span>Qualified Bench: <b>${m.ready_candidates_count}</b></span>
              <span>Pipeline (60-74%): <b>${m.pipeline_candidates_count}</b></span>
              <span>Sanctioned: <b>${m.sanctioned_posts}</b></span>
            </div>
          </div>

          <!-- Recommendation Alert -->
          <div style="background:rgba(0,0,0,0.02);border-left:3px solid ${m.risk_color};padding:8px 10px;border-radius:2px;font-size:11.5px;color:var(--ink);margin-bottom:12px">
            <b>Directive:</b> ${esc(m.strategic_recommendation)}
          </div>

          <!-- Top Candidates Roster -->
          <div style="margin-top:10px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
              <span style="font-size:10.5px;font-weight:700;text-transform:uppercase;color:var(--muted)">Feeder Candidate Roster</span>
              <span style="font-size:10px;color:var(--muted)">Threshold: ≥${m.critical_threshold}%</span>
            </div>
            ${candidateRows}
          </div>
        </div>
      </article>
    `;
  }).join('');
}

function renderDepartmentWeights(departments) {
  const container = $('deptWeightsList');
  if (!container) return;
  if (!departments || !departments.length) {
    container.innerHTML = '<p class="muted" style="padding:20px;text-align:center">No departmental weights loaded.</p>';
    return;
  }

  const isAdmin = currentUser && currentUser.role === 'admin';
  const notice = $('deptWeightAdminNotice');
  if (notice) {
    if (isAdmin) {
      notice.textContent = '👑 Admin Mode: Multipliers Editable';
      notice.className = 'badge badge-green';
    } else {
      notice.textContent = 'Viewer Mode: Read-Only Multipliers';
      notice.className = 'badge badge-amber';
    }
  }

  container.innerHTML = departments.map(d => {
    const deltaColor = d.readiness_delta >= 0 ? 'var(--green)' : 'var(--accent)';
    const deltaSign = d.readiness_delta >= 0 ? '+' : '';

    const priorityItems = (d.priorities || []).map(p => `
      <div style="background:#ffffff;border:1px solid var(--line);border-radius:4px;padding:10px 12px;margin-bottom:10px">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px">
          <div>
            <b style="font-size:12.5px;color:var(--ink)">${esc(p.skill_name)}</b>
            <div style="font-size:10.5px;color:var(--muted);margin-top:2px">${esc(p.rationale)}</div>
          </div>
          <span class="badge" style="background:#f0fdf4;color:#166534;border:1px solid #bbf7d0;font-weight:700">
            <span id="multVal-${p.id}">${p.multiplier.toFixed(1)}</span>×
          </span>
        </div>

        <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--muted);margin-bottom:6px">
          <span>Gap Prevalence: <b>${p.gap_percentage}%</b> (${p.officers_with_gap} officers)</span>
          <span>Weighted Score: <b>${p.weighted_gap_score}</b></span>
        </div>

        ${isAdmin ? `
          <div style="display:flex;align-items:center;gap:10px;margin-top:8px;padding-top:8px;border-top:1px dashed var(--line)">
            <input type="range" min="1.0" max="2.5" step="0.1" value="${p.multiplier}" 
              id="slider-${p.id}" 
              style="flex:1;accent-color:var(--green);cursor:pointer"
              oninput="$('multVal-${p.id}').textContent = parseFloat(this.value).toFixed(1)"
            >
            <button class="secondary" style="font-size:10.5px;padding:3px 8px" onclick="saveMultiplier(${p.id})">Save</button>
          </div>
        ` : ''}
      </div>
    `).join('');

    return `
      <article class="panel" style="background:#ffffff">
        <div class="panel-head" style="padding-bottom:10px;border-bottom:1px solid var(--line)">
          <div>
            <span class="badge" style="font-size:9.5px;background:var(--panel2);color:var(--ink);margin-bottom:3px;display:inline-block">DIRECTORATE</span>
            <h3 style="margin:0;font-size:14.5px;color:var(--ink)">${esc(d.department)}</h3>
            <span style="font-size:11px;color:var(--muted)">${d.officer_count} officers assigned</span>
          </div>
          <div style="text-align:right">
            <div style="font-size:10px;text-transform:uppercase;color:var(--muted);font-weight:700">Strategic Readiness</div>
            <div style="font-size:16px;font-weight:800;color:var(--ink)">
              ${d.strategic_weighted_readiness}%
              <span style="font-size:11px;font-weight:600;color:${deltaColor}">(${deltaSign}${d.readiness_delta}%)</span>
            </div>
            <div style="font-size:10px;color:var(--muted)">Baseline: ${d.baseline_readiness}%</div>
          </div>
        </div>
        <div style="padding-top:12px">
          <div style="font-size:10.5px;font-weight:700;text-transform:uppercase;color:var(--muted);margin-bottom:8px">Mission-Critical Competencies:</div>
          ${priorityItems || '<p class="muted" style="font-size:11px">No priority competencies configured.</p>'}
        </div>
      </article>
    `;
  }).join('');
}

async function saveMultiplier(weightId) {
  const slider = $(`slider-${weightId}`);
  if (!slider) return;
  const newMultiplier = parseFloat(slider.value);
  try {
    toast('Updating departmental priority multiplier…');
    await api('/api/succession/department-weights', {
      method: 'POST',
      body: {
        weight_id: weightId,
        multiplier: newMultiplier,
        rationale: 'Updated via Executive Directorate Intelligence Cockpit'
      }
    });
    toast('Priority multiplier saved!');
    await loadSuccessionIntelligence();
  } catch (err) {
    toast(`Failed to update weight: ${err.message}`);
  }
}

function exportSuccessionDossier() {
  if (!currentSuccessionData) {
    toast('No succession data available to export.');
    return;
  }
  const payload = {
    exported_at: new Date().toISOString(),
    organization: 'National Statistical Office / ISS Cadre Authority',
    cadre_bench_strength_standard: 'Officers in Feeder Cadre with Readiness >= 75% / Sanctioned Target Posts',
    overall_summary: currentSuccessionData.overall_summary,
    succession_matrix: currentSuccessionData.succession_matrix,
    departmental_weights: currentDepartmentWeights ? currentDepartmentWeights.departments : []
  };

  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `StatIntel-Cadre-Succession-Intelligence-${new Date().toISOString().slice(0,10)}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  toast('Succession dossier exported successfully.');
}

// Wire succession page action buttons
if ($('refreshSuccessionBtn')) $('refreshSuccessionBtn').onclick = () => loadSuccessionIntelligence();
if ($('exportSuccessionBtn')) $('exportSuccessionBtn').onclick = exportSuccessionDossier;

// ── Boot ───────────────────────────────────────────────────────────
(async () => {
  let targetPage = null;
  const hash = window.location.hash;
  if (hash && hash.includes('autologin=')) {
    const params = new URLSearchParams(hash.substring(1));
    const autoToken = params.get('autologin');
    targetPage = params.get('page') || 'pathway';
    if (autoToken) {
      token = autoToken;
      localStorage.setItem('statintel_token', token);
      window.history.replaceState(null, '', window.location.pathname);
    }
  }
  if (token) await startApp(targetPage);
})();


