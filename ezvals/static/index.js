const STORAGE_KEY = "ezvals:hidden_columns";
const WIDTHS_STORAGE_KEY = "ezvals:col_widths";
const THEME_STORAGE_KEY = "ezvals:theme";

document.getElementById('theme-toggle')?.addEventListener('click', () => {
  const html = document.documentElement;
  const isDark = html.classList.contains('dark');
  if (isDark) { html.classList.remove('dark'); localStorage.setItem(THEME_STORAGE_KEY, 'light'); }
  else { html.classList.add('dark'); localStorage.setItem(THEME_STORAGE_KEY, 'dark'); }
});

let _sortState = [];
let _filters = defaultFilters();
const selectedIndices = new Set();

const DEFAULT_HIDDEN_COLS = ["error"];
function getHiddenCols() { const s = localStorage.getItem(STORAGE_KEY); if (s === null) return DEFAULT_HIDDEN_COLS; try { return JSON.parse(s); } catch { return DEFAULT_HIDDEN_COLS; } }
function setHiddenCols(cols) { localStorage.setItem(STORAGE_KEY, JSON.stringify(cols)); }
function getSortState() { return _sortState; }
function setSortState(state) { _sortState = state; }
function getColWidths() { try { return JSON.parse(localStorage.getItem(WIDTHS_STORAGE_KEY) || "{}"); } catch { return {}; } }
function setColWidths(map) { localStorage.setItem(WIDTHS_STORAGE_KEY, JSON.stringify(map)); }
function defaultFilters() { return { valueRules: [], passedRules: [], annotation: 'any', selectedDatasets: { include: [], exclude: [] }, selectedLabels: { include: [], exclude: [] }, hasUrl: null, hasMessages: null, hasError: null }; }

// Current data for updates
let _currentData = null;
let _currentRunId = null;

const PILL_TONES = {
  'not_started': 'text-zinc-400 bg-zinc-500/10 border border-zinc-500/40',
  'pending': 'text-blue-300 bg-blue-500/10 border border-blue-500/40',
  'running': 'text-cyan-300 bg-cyan-500/10 border border-cyan-500/40',
  'completed': 'text-emerald-300 bg-emerald-500/10 border border-emerald-500/40',
  'error': 'text-rose-300 bg-rose-500/10 border border-rose-500/40',
  'cancelled': 'text-amber-300 bg-amber-500/10 border border-amber-500/40'
};
const STATS_PREF_KEY = 'ezvals:statsExpanded';

function summarizeStats(data) {
  const results = data.results || [];
  const chips = data.score_chips || [];
  const totalEvaluations = data.total_evaluations || 0;
  const selectedTotal = data.selected_total;  // For selective reruns
  const avgLatency = data.average_latency || 0;
  let completed = 0, pending = 0, running = 0, notStarted = 0;
  results.forEach((r) => {
    const status = r.result?.status || 'completed';
    if (status === 'not_started') notStarted++;
    else if (status === 'pending') pending++;
    else if (status === 'running') running++;
    else completed++;
  });
  // For selective reruns, show progress relative to selected count
  // Only selected evals will have pending/running status
  const inProgress = pending + running;
  const isSelectiveRun = selectedTotal != null && selectedTotal > 0;
  const progressTotal = isSelectiveRun ? selectedTotal : totalEvaluations;
  const progressCompleted = isSelectiveRun ? (selectedTotal - inProgress) : completed;
  const pctDone = progressTotal > 0 ? Math.round((progressCompleted / progressTotal) * 100) : 0;
  return {
    results,
    chips,
    total: totalEvaluations,
    progressTotal,
    progressCompleted,
    avgLatency,
    completed,
    pending,
    running,
    notStarted,
    pctDone,
    progressPending: inProgress,
    sessionName: data.session_name,
    runName: data.run_name,
    isRunning: inProgress > 0,
  };
}

function chipStats(chip, precision = 2) {
  if (chip.type === 'ratio') {
    const pct = chip.total > 0 ? Math.round((chip.passed / chip.total) * 100) : 0;
    return { pct, value: `${chip.passed}/${chip.total}` };
  }
  const avg = chip.avg;
  const pct = avg <= 1 ? Math.round(avg * 100) : (avg <= 10 ? Math.round(avg * 10) : Math.min(Math.round(avg), 100));
  return { pct, value: avg.toFixed(precision) };
}

function updateLatencyDisplay(expandedPanel, avgLatency, animate = false) {
  let latencyMetric = expandedPanel.querySelector('.stats-metric-sm');
  if (avgLatency > 0) {
    const html = `${avgLatency.toFixed(2)}<span class="stats-metric-unit">s</span>`;
    if (!latencyMetric) {
      const leftContent = expandedPanel.querySelector('.stats-left-content');
      if (leftContent) {
        latencyMetric = document.createElement('div');
        latencyMetric.className = 'stats-metric stats-metric-sm';
        latencyMetric.innerHTML = `<span class="stats-metric-value">${html}</span><span class="stats-metric-label">avg latency</span>`;
        leftContent.appendChild(latencyMetric);
      }
    } else {
      const el = latencyMetric.querySelector('.stats-metric-value');
      if (el && el.innerHTML !== html) {
        if (animate) {
          el.classList.add('updating');
          setTimeout(() => { el.innerHTML = html; el.classList.remove('updating'); }, 100);
        } else {
          el.innerHTML = html;
        }
      }
    }
  } else if (latencyMetric) {
    latencyMetric.remove();
  }
}

function updateChartBars(expandedPanel, chips) {
  const barsContainer = expandedPanel.querySelector('.stats-chart-bars');
  const labelsContainer = expandedPanel.querySelector('.stats-chart-labels');
  const valuesContainer = expandedPanel.querySelector('.stats-chart-values');
  if (!barsContainer || !labelsContainer || !valuesContainer) return;

  const existingBars = barsContainer.querySelectorAll('.stats-bar-col');
  const existingLabels = labelsContainer.querySelectorAll('.stats-chart-label');
  const existingValues = valuesContainer.querySelectorAll('.stats-chart-value');

  chips.forEach((chip, i) => {
    const { pct, value } = chipStats(chip, 2);
    const colorClass = getBarColor(pct);

    if (existingBars[i]) {
      const fill = existingBars[i].querySelector('.stats-chart-fill');
      if (fill) { fill.style.height = pct + '%'; fill.className = 'stats-chart-fill ' + colorClass; }
    } else {
      const barCol = document.createElement('div');
      barCol.className = 'stats-bar-col entering';
      barCol.innerHTML = `<div class="stats-chart-fill ${colorClass}" style="height: 0%"></div>`;
      barsContainer.appendChild(barCol);
      requestAnimationFrame(() => { barCol.classList.remove('entering'); barCol.querySelector('.stats-chart-fill').style.height = pct + '%'; });
    }

    if (existingLabels[i]) {
      existingLabels[i].textContent = chip.key;
    } else {
      const label = document.createElement('span');
      label.className = 'stats-chart-label entering';
      label.textContent = chip.key;
      labelsContainer.appendChild(label);
      requestAnimationFrame(() => label.classList.remove('entering'));
    }

    if (existingValues[i]) {
      if (existingValues[i].textContent !== value) {
        existingValues[i].classList.add('updating');
        setTimeout(() => { existingValues[i].textContent = value; existingValues[i].classList.remove('updating'); }, 100);
      }
    } else {
      const valSpan = document.createElement('span');
      valSpan.className = 'stats-chart-value entering';
      valSpan.textContent = value;
      valuesContainer.appendChild(valSpan);
      requestAnimationFrame(() => valSpan.classList.remove('entering'));
    }
  });

  // Remove excess bars/labels/values with exit animation
  for (let i = chips.length; i < existingBars.length; i++) { existingBars[i].classList.add('exiting'); setTimeout(() => existingBars[i].remove(), 400); }
  for (let i = chips.length; i < existingLabels.length; i++) { existingLabels[i].classList.add('exiting'); setTimeout(() => existingLabels[i].remove(), 300); }
  for (let i = chips.length; i < existingValues.length; i++) { existingValues[i].classList.add('exiting'); setTimeout(() => existingValues[i].remove(), 300); }
}

function computeFilteredStats() {
  const tbody = document.querySelector('#results-table tbody');
  if (!tbody) return null;

  const allRows = Array.from(tbody.querySelectorAll("tr[data-row='main']"));
  const visibleRows = allRows.filter(tr => !tr.classList.contains('hidden'));
  const total = allRows.length;
  const filtered = visibleRows.length;

  // Calculate latency from visible rows
  let latencySum = 0, latencyCount = 0;
  visibleRows.forEach(tr => {
    const latVal = parseFloat(tr.querySelector("td[data-col='latency']")?.getAttribute('data-value') || '');
    if (!isNaN(latVal)) { latencySum += latVal; latencyCount++; }
  });
  const avgLatency = latencyCount > 0 ? latencySum / latencyCount : 0;

  // Aggregate scores from visible rows
  const scoreMap = {};
  visibleRows.forEach(tr => {
    let scores = [];
    try { scores = JSON.parse(tr.getAttribute('data-scores') || '[]') || []; } catch {}
    scores.forEach(s => {
      const key = s?.key;
      if (!key) return;
      const d = scoreMap[key] || (scoreMap[key] = { passed: 0, failed: 0, bool: 0, sum: 0, count: 0 });
      if (s.passed === true) { d.passed++; d.bool++; }
      else if (s.passed === false) { d.failed++; d.bool++; }
      const val = parseFloat(s.value);
      if (!isNaN(val)) { d.sum += val; d.count++; }
    });
  });

  // Convert scoreMap to chips array (same format as server)
  const chips = Object.entries(scoreMap).map(([key, d]) => {
    if (d.bool > 0) {
      return { key, type: 'ratio', passed: d.passed, total: d.passed + d.failed };
    } else if (d.count > 0) {
      return { key, type: 'avg', avg: d.sum / d.count, count: d.count };
    }
    return null;
  }).filter(Boolean);

  return { total, filtered, avgLatency, chips };
}

function escapeHtml(str) {
  if (str == null) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function formatValue(val) {
  if (val == null) return '';
  if (typeof val === 'object') return JSON.stringify(val);
  return String(val);
}

function getBarColor(pct) {
  return pct >= 80 ? 'vbar-green' : (pct >= 50 ? 'vbar-amber' : 'vbar-red');
}

function getBgBarColor(pct) {
  return pct >= 80 ? 'bg-emerald-500' : (pct >= 50 ? 'bg-amber-500' : 'bg-rose-500');
}

function getTextColor(pct) {
  return pct >= 80 ? 'text-accent-success' : (pct >= 50 ? 'text-amber-500' : 'text-accent-error');
}

function renderStatsExpanded(data) {
  const { total, avgLatency, chips, pctDone, isRunning, sessionName, runName, progressCompleted, progressTotal } = summarizeStats(data);

  let headerHtml = '';
  if (sessionName || runName) {
    headerHtml = '<div class="stats-left-header">';
    if (sessionName) headerHtml += `<div class="stats-info-row"><span class="stats-info-label">session</span><span class="stats-session copyable cursor-pointer hover:text-zinc-300">${escapeHtml(sessionName)}</span></div>`;
    if (runName) headerHtml += `<div class="stats-info-row group"><span class="stats-info-label">run</span><span id="run-name-expanded" class="stats-run copyable cursor-pointer hover:text-zinc-300">${escapeHtml(runName)}</span><button class="edit-run-btn-expanded ml-1 text-zinc-600 transition hover:text-zinc-400" title="Rename run"><svg class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-pencil"></use></svg></button></div>`;
    headerHtml += '</div>';
  }

  // Only render latency if we have data (will be created dynamically during live updates)
  const latencyHtml = avgLatency > 0
    ? `<div class="stats-metric stats-metric-sm"><span class="stats-metric-value">${avgLatency.toFixed(2)}<span class="stats-metric-unit">s</span></span><span class="stats-metric-label">avg latency</span></div>`
    : '';

  let progressHtml = '';
  if (isRunning) {
    progressHtml = `<div class="stats-progress"><div class="stats-progress-bar"><div class="stats-progress-fill" style="width: ${pctDone}%"></div></div><span class="stats-progress-text text-emerald-400">${progressCompleted}/${progressTotal}</span></div>`;
  }

  let barsHtml = '';
  let labelsHtml = '';
  let valuesHtml = '';
  chips.forEach((chip) => {
    const { pct, value } = chipStats(chip, 2);
    // Start at 0 height, will animate to target via JS
    barsHtml += `<div class="stats-bar-col" style="opacity:0;transform:translateY(20px)"><div class="stats-chart-fill ${getBarColor(pct)}" data-target-height="${pct}" style="height: 0%"></div></div>`;
    labelsHtml += `<span class="stats-chart-label" style="opacity:0">${escapeHtml(chip.key)}</span>`;
    valuesHtml += `<span class="stats-chart-value" style="opacity:0">${value}</span>`;
  });

  const isCollapsed = localStorage.getItem(STATS_PREF_KEY) === 'false';
  return `
    <div id="stats-expanded" class="stats-expanded${isCollapsed ? ' hidden' : ''}">
      <div class="stats-layout">
        <button id="stats-collapse-btn" class="stats-collapse-btn" title="Collapse">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-chevron-up"></use></svg>
        </button>
        <div class="stats-left">
          <div class="stats-left-content">
            ${headerHtml}
            <div class="stats-metric-row-main">
              <div class="stats-metric"><span class="stats-metric-value">${total}</span><span class="stats-metric-label">tests</span></div>
              ${progressHtml}
            </div>
            ${latencyHtml}
          </div>
          <div class="stats-yaxis">
            <span class="stats-axis-label">100%</span>
            <span class="stats-axis-label">75%</span>
            <span class="stats-axis-label">50%</span>
            <span class="stats-axis-label">25%</span>
            <span class="stats-axis-label">0%</span>
          </div>
        </div>
        <div class="stats-right">
          <div class="stats-chart-area">
            <div class="stats-gridline" style="top: 0%"></div>
            <div class="stats-gridline" style="top: 25%"></div>
            <div class="stats-gridline" style="top: 50%"></div>
            <div class="stats-gridline" style="top: 75%"></div>
            <div class="stats-chart-bars">${barsHtml}</div>
          </div>
          <div class="stats-xaxis">
            <div class="stats-chart-labels">${labelsHtml}</div>
            <div class="stats-chart-values">${valuesHtml}</div>
          </div>
        </div>
      </div>
    </div>`;
}

function renderStatsCompact(data, hasFilters = false, filteredCount = null) {
  const stats = summarizeStats(data);
  const { total, avgLatency, chips, pctDone, progressPending, notStarted, sessionName, runName, progressCompleted, progressTotal } = stats;

  let sessionRunHtml = '';
  if (sessionName || runName) {
    sessionRunHtml = '<div class="flex items-center gap-2">';
    if (sessionName) {
      sessionRunHtml += `<span class="text-[11px] font-medium uppercase tracking-wider text-theme-text-secondary">Session</span>
        <span id="session-name-text" class="copyable font-mono text-[11px] text-theme-text cursor-pointer hover:text-zinc-300">${escapeHtml(sessionName)}</span>`;
    }
    if (runName) {
      if (sessionName) sessionRunHtml += '<span class="text-zinc-600">·</span>';
      sessionRunHtml += `<span class="text-[11px] font-medium uppercase tracking-wider text-theme-text-secondary">Run</span>
        <div class="group flex items-center gap-1">
          <span id="run-name-text" class="copyable font-mono text-[11px] text-accent-link cursor-pointer hover:text-accent-link-hover">${escapeHtml(runName)}</span>
          <button class="edit-run-btn flex h-4 w-4 items-center justify-center rounded text-zinc-600 transition hover:text-zinc-400" title="Rename run">
            <svg class="h-2.5 w-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-pencil"></use></svg>
          </button>
        </div>`;
    }
    sessionRunHtml += '</div><div class="h-3 w-px bg-zinc-700"></div>';
  }

  let progressHtml;
  if (notStarted === total) {
    progressHtml = `<div class="flex items-center gap-2"><span class="text-[11px] font-medium uppercase tracking-wider text-theme-text-secondary">Discovered</span><span class="font-mono text-[11px] text-zinc-400">${total} eval${total !== 1 ? 's' : ''}</span></div>`;
  } else if (progressPending > 0) {
    progressHtml = `<div class="flex items-center gap-2"><span class="text-[11px] font-medium uppercase tracking-wider text-theme-text-secondary">Progress</span><div class="h-1 w-6 overflow-hidden rounded-full bg-zinc-800"><div class="h-full rounded-full bg-blue-500" style="width: ${pctDone}%"></div></div><span class="font-mono text-[11px] text-accent-link">${progressCompleted}/${progressTotal}</span></div>`;
  } else {
    const testsDisplay = hasFilters && filteredCount != null ? `${filteredCount}/${total}` : String(total);
    progressHtml = `<div class="flex items-center gap-2"><span class="text-[11px] font-medium uppercase tracking-wider text-theme-text-secondary">Tests</span><span class="font-mono text-[11px] text-accent-link">${testsDisplay}</span></div>`;
  }

  let chipsHtml = '';
  chips.forEach((chip, i) => {
    const { pct, value } = chipStats(chip, 1);
    chipsHtml += `<div class="flex items-center gap-2">
      <span class="text-[10px] font-medium uppercase tracking-wider text-theme-text-secondary">${escapeHtml(chip.key)}</span>
      <div class="h-1 w-5 overflow-hidden rounded-full bg-zinc-800"><div class="h-full rounded-full ${getBgBarColor(pct)}" style="width: ${pct}%"></div></div>
      <span class="font-mono text-[11px] ${getTextColor(pct)}">${value}</span>
    </div>`;
    if (i < chips.length - 1) chipsHtml += '<div class="h-3 w-px bg-zinc-700"></div>';
  });

  let latencyHtml = '';
  if (avgLatency > 0) {
    latencyHtml = `<div class="h-3 w-px bg-zinc-700"></div><div class="flex items-center gap-2"><span class="text-[10px] font-medium uppercase tracking-wider text-theme-text-secondary">Latency</span><span class="font-mono text-[11px] text-zinc-400">${avgLatency.toFixed(2)}s</span></div>`;
  }

  const isCollapsed = localStorage.getItem(STATS_PREF_KEY) === 'false';
  return `
    <div id="stats-compact" class="mb-3 flex flex-wrap items-center gap-3 border-b border-theme-border bg-theme-bg-secondary/50 px-4 py-2${isCollapsed ? '' : ' hidden'}">
      ${sessionRunHtml}
      ${progressHtml}
      <div class="h-3 w-px bg-zinc-700"></div>
      ${chipsHtml}
      ${latencyHtml}
      <div class="ml-auto">
        <button id="stats-expand-btn" class="stats-toggle-btn" title="Expand stats">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-chevron-down"></use></svg>
        </button>
      </div>
    </div>`;
}

function renderRow(r, index, runId) {
  const result = r.result || {};
  const status = result.status || 'completed';
  const isRunning = status === 'running';
  const isNotStarted = status === 'not_started';
  const scores = result.scores || [];
  const hasUrl = !!(result.trace_data?.trace_url);
  const hasMessages = !!(result.trace_data?.messages?.length);
  const hasError = !!result.error;

  const functionCell = isNotStarted
    ? `<span class="font-mono text-[12px] font-medium text-zinc-500">${escapeHtml(r.function)}</span>`
    : `<a href="/runs/${runId}/results/${index}" class="font-mono text-[12px] font-medium text-accent-link hover:text-accent-link-hover">${escapeHtml(r.function)}</a>`;

  let statusPill = '';
  if (status === 'running') statusPill = `<span class="status-pill rounded px-1.5 py-0.5 text-[10px] font-medium ${PILL_TONES.running}">running</span>`;
  else if (status === 'error') statusPill = `<span class="status-pill rounded px-1.5 py-0.5 text-[10px] font-medium ${PILL_TONES.error}">err</span>`;

  let labelsHtml = '';
  if (r.labels?.length) {
    labelsHtml = '<span class="text-zinc-700">·</span>' + r.labels.map(la => `<span class="rounded bg-theme-bg-elevated px-1 py-0.5 text-[9px] text-theme-text-muted">${escapeHtml(la)}</span>`).join('');
  }

  let outputCell;
  if (isNotStarted) outputCell = '<span class="text-zinc-600">—</span>';
  else if (isRunning) outputCell = '<div class="space-y-1"><div class="h-2.5 w-3/4 animate-pulse rounded bg-zinc-800"></div><div class="h-2.5 w-1/2 animate-pulse rounded bg-zinc-800"></div></div>';
  else if (result.output != null) outputCell = `<div class="line-clamp-4 text-[12px] text-theme-text">${escapeHtml(formatValue(result.output))}</div>`;
  else outputCell = '<span class="text-zinc-600">—</span>';

  let scoresCell;
  if (isNotStarted) scoresCell = '<span class="text-zinc-600">—</span>';
  else if (isRunning) scoresCell = '<div class="flex gap-1"><div class="h-4 w-14 animate-pulse rounded bg-zinc-800"></div><div class="h-4 w-10 animate-pulse rounded bg-zinc-800"></div></div>';
  else if (scores.length) {
    const badgesHtml = scores.map((s) => {
      let badgeClass = 'bg-theme-bg-elevated text-theme-text-muted';
      if (s.passed === true) badgeClass = 'bg-accent-success-bg text-accent-success';
      else if (s.passed === false) badgeClass = 'bg-accent-error-bg text-accent-error';
      const val = s.value != null ? `:${typeof s.value === 'number' ? s.value.toFixed(1) : s.value}` : '';
      const title = `${s.key}${s.value != null ? ': ' + (typeof s.value === 'number' ? s.value.toFixed(3) : s.value) : ''}${s.notes ? ' — ' + s.notes : ''}`;
      return `<span class="score-badge shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${badgeClass}" title="${escapeHtml(title)}">${escapeHtml(s.key)}${val}</span>`;
    }).join('');
    scoresCell = `<div class="flex flex-wrap gap-1">${badgesHtml}</div>`;
  } else scoresCell = '<span class="text-zinc-600">—</span>';

  // Compute sort value for scores (first score's value or pass/fail status)
  let scoresSortValue = '';
  if (scores.length) {
    const firstScore = scores[0];
    if (firstScore.value != null) scoresSortValue = firstScore.value;
    else if (firstScore.passed === true) scoresSortValue = 1;
    else if (firstScore.passed === false) scoresSortValue = 0;
  }

  let latencyCell;
  if (result.latency != null) {
    const lat = result.latency;
    const latColor = lat <= 1 ? 'text-accent-success' : (lat <= 5 ? 'text-theme-text-muted' : 'text-accent-error');
    latencyCell = `<span class="latency-value font-mono text-[11px] ${latColor}">${lat.toFixed(2)}s</span>`;
  } else if (isRunning) latencyCell = '<div class="latency-skeleton ml-auto h-3 w-8 animate-pulse rounded bg-zinc-800"></div>';
  else latencyCell = '<span class="text-zinc-600">—</span>';

  return `
    <tr data-row="main" data-row-id="${index}" data-status="${status}" data-scores='${JSON.stringify(scores)}' data-annotation="${escapeHtml(result.annotation || '')}" data-dataset="${escapeHtml(r.dataset || '')}" data-labels='${JSON.stringify(r.labels || [])}' data-has-url="${hasUrl}" data-has-messages="${hasMessages}" data-has-error="${hasError}" class="group cursor-pointer hover:bg-theme-bg-elevated/50 transition-colors${isNotStarted ? ' opacity-60' : ''}" onclick="if(!event.target.closest('input,button,a')) this.classList.toggle('expanded')">
      <td class="px-2 py-3 text-center align-middle" onclick="event.stopPropagation()">
        <input type="checkbox" class="row-checkbox" data-row-id="${index}" />
      </td>
      <td data-col="function" class="px-3 py-3 align-middle">
        <div class="flex flex-col gap-0.5">
          <div class="flex items-center gap-2">${functionCell}${statusPill}</div>
          <div class="flex items-center gap-1.5 text-[10px] text-zinc-500"><span>${escapeHtml(r.dataset || '')}</span>${labelsHtml}</div>
        </div>
      </td>
      <td data-col="input" title="${escapeHtml(formatValue(result.input))}" class="px-3 py-3 align-middle">
        <div class="line-clamp-4 text-[12px] text-theme-text">${escapeHtml(formatValue(result.input))}</div>
      </td>
      <td data-col="reference" title="${escapeHtml(formatValue(result.reference))}" class="px-3 py-3 align-middle">
        ${result.reference != null ? `<div class="line-clamp-4 text-[12px] text-theme-text">${escapeHtml(formatValue(result.reference))}</div>` : '<span class="text-zinc-600">—</span>'}
      </td>
      <td data-col="output" title="${escapeHtml(formatValue(result.output))}" class="px-3 py-3 align-middle">${outputCell}</td>
      <td data-col="error" title="${escapeHtml(result.error || '')}" class="px-3 py-3 align-middle">
        ${result.error ? `<div class="line-clamp-4 text-[12px] text-accent-error">${escapeHtml(result.error)}</div>` : '<span class="text-zinc-600">—</span>'}
      </td>
      <td data-col="scores" data-value="${scoresSortValue}" class="px-3 py-3 align-middle">${scoresCell}</td>
      <td data-col="latency" data-value="${result.latency ?? ''}" class="px-3 py-3 align-middle text-right">${latencyCell}</td>
      <td class="px-1 py-3 align-middle">
        <span class="expand-chevron text-zinc-700 group-hover:text-zinc-400">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-chevron-right"></use></svg>
        </span>
      </td>
    </tr>`;
}

function renderResultsTable(data, runId) {
  const results = data.results || [];
  const rowsHtml = results.map((r, i) => renderRow(r, i, runId)).join('');
  return `
    <table id="results-table" data-run-id="${runId}" class="w-full table-fixed border-collapse text-sm text-theme-text">
      <thead>
        <tr class="border-b border-theme-border">
          <th style="width:32px" class="bg-theme-bg px-2 py-2 text-center align-middle"><input type="checkbox" id="select-all-checkbox" class="accent-emerald-500" /></th>
          <th data-col="function" style="width:15%" class="bg-theme-bg px-3 py-2 text-left text-[10px] font-medium uppercase tracking-wider text-theme-text-muted">Eval</th>
          <th data-col="input" style="width:18%" class="bg-theme-bg px-3 py-2 text-left text-[10px] font-medium uppercase tracking-wider text-theme-text-muted">Input</th>
          <th data-col="reference" style="width:18%" class="bg-theme-bg px-3 py-2 text-left text-[10px] font-medium uppercase tracking-wider text-theme-text-muted">Reference</th>
          <th data-col="output" style="width:18%" class="bg-theme-bg px-3 py-2 text-left text-[10px] font-medium uppercase tracking-wider text-theme-text-muted">Output</th>
          <th data-col="error" style="width:18%" class="bg-theme-bg px-3 py-2 text-left text-[10px] font-medium uppercase tracking-wider text-theme-text-muted">Error</th>
          <th data-col="scores" data-type="number" style="width:140px" class="bg-theme-bg px-3 py-2 text-left text-[10px] font-medium uppercase tracking-wider text-theme-text-muted">Scores</th>
          <th data-col="latency" data-type="number" style="width:70px" class="bg-theme-bg px-3 py-2 text-right text-[10px] font-medium uppercase tracking-wider text-theme-text-muted">Time</th>
          <th style="width:28px" class="bg-theme-bg px-1 py-2"></th>
        </tr>
      </thead>
      <tbody class="divide-y divide-theme-border-subtle">${rowsHtml}</tbody>
    </table>`;
}

function renderResults(data) {
  _currentData = data;
  _currentRunId = data.run_id;

  // Check if any results have been run (not "not_started")
  // Don't reset _hasRunBefore to false once it's true (avoids race conditions)
  _hasRunBefore = _hasRunBefore || (data.results || []).some(r => r.result?.status && r.result.status !== 'not_started');

  const container = document.getElementById('results');
  container.innerHTML = renderStatsExpanded(data) + renderStatsCompact(data) + renderResultsTable(data, data.run_id);
  onResultsRendered();
}

function onResultsRendered() {
  const table = document.getElementById('results-table');
  if (table) { applySortState(table); applyColumnWidths(table); initResizableColumns(table); }
  applyColumnVisibility();
  initScrollRestoration();
  wireExportButtons();
  restoreFiltersAndSearch();
  try { populateScoreKeySelects(); populateDatasetLabelPills(); updateTraceFilterButtons(); updateAnnotationButton(); renderActiveFilters(); applyAllFilters(); } catch {}
  syncCheckboxesToSelection();
  checkRunningState();
  scheduleLiveRefresh();
  initStatsToggle();
  animateInitialBars();
}

function animateInitialBars() {
  const bars = document.querySelectorAll('.stats-bar-col');
  const labels = document.querySelectorAll('.stats-chart-label');
  const values = document.querySelectorAll('.stats-chart-value');

  bars.forEach((bar, i) => {
    const fill = bar.querySelector('.stats-chart-fill');
    const targetHeight = fill?.dataset.targetHeight;
    setTimeout(() => {
      bar.style.opacity = '';
      bar.style.transform = '';
      if (fill && targetHeight) {
        fill.style.height = targetHeight + '%';
      }
    }, 50 + i * 80);
  });

  labels.forEach((label, i) => {
    setTimeout(() => { label.style.opacity = ''; }, 100 + i * 80);
  });

  values.forEach((val, i) => {
    setTimeout(() => { val.style.opacity = ''; }, 150 + i * 80);
  });
}

function updateRowInPlace(index, newResult) {
  const row = document.querySelector(`tr[data-row="main"][data-row-id="${index}"]`);
  if (!row || !_currentData) return;

  const oldResult = _currentData.results[index].result || {};
  const oldStatus = oldResult.status || 'completed';
  const newStatus = newResult.status || 'completed';
  const statusChanged = oldStatus !== newStatus;

  // Update the data
  _currentData.results[index].result = newResult;

  // Update data attributes
  row.dataset.status = newStatus;
  row.dataset.scores = JSON.stringify(newResult.scores || []);
  row.dataset.annotation = newResult.annotation || '';
  row.dataset.hasUrl = !!(newResult.trace_data?.trace_url);
  row.dataset.hasMessages = !!(newResult.trace_data?.messages?.length);
  row.dataset.hasError = !!newResult.error;

  // Update opacity for not_started transition
  if (oldStatus === 'not_started' && newStatus !== 'not_started') {
    row.classList.remove('opacity-60');
  }

  // Update status pill with animation
  const functionCell = row.querySelector('td[data-col="function"]');
  if (functionCell && statusChanged) {
    const oldPill = functionCell.querySelector('.status-pill');
    if (oldPill) {
      oldPill.classList.add('fade-out');
      setTimeout(() => oldPill.remove(), 300);
    }

    if (newStatus === 'running') {
      const pill = document.createElement('span');
      pill.className = `status-pill rounded px-1.5 py-0.5 text-[10px] font-medium ${PILL_TONES.running} fade-out`;
      pill.textContent = 'running';
      const fnLink = functionCell.querySelector('a, span');
      if (fnLink) fnLink.parentElement.appendChild(pill);
      requestAnimationFrame(() => pill.classList.remove('fade-out'));
    } else if (newStatus === 'error') {
      const pill = document.createElement('span');
      pill.className = `status-pill rounded px-1.5 py-0.5 text-[10px] font-medium ${PILL_TONES.error} fade-out`;
      pill.textContent = 'err';
      const fnLink = functionCell.querySelector('a, span');
      if (fnLink) fnLink.parentElement.appendChild(pill);
      requestAnimationFrame(() => pill.classList.remove('fade-out'));
    }

    // Update function link (make clickable when completed)
    const fnSpan = functionCell.querySelector('span.font-mono');
    if (fnSpan && newStatus !== 'not_started') {
      const link = document.createElement('a');
      link.href = `/runs/${_currentRunId}/results/${index}`;
      link.className = 'font-mono text-[12px] font-medium text-accent-link hover:text-accent-link-hover';
      link.textContent = fnSpan.textContent;
      fnSpan.replaceWith(link);
    }
  }

  // Update output cell
  const outputCell = row.querySelector('td[data-col="output"]');
  if (outputCell) {
    if (newStatus === 'running') {
      outputCell.innerHTML = '<div class="space-y-1"><div class="h-2.5 w-3/4 animate-pulse rounded bg-zinc-800"></div><div class="h-2.5 w-1/2 animate-pulse rounded bg-zinc-800"></div></div>';
    } else if (newResult.output != null) {
      const content = `<div class="cell-content line-clamp-2 text-[12px] text-theme-text updating">${escapeHtml(formatValue(newResult.output))}</div>`;
      outputCell.innerHTML = content;
      requestAnimationFrame(() => outputCell.querySelector('.cell-content')?.classList.remove('updating'));
    } else {
      // Clear skeleton when output is null (error case)
      outputCell.innerHTML = '<span class="text-zinc-600">—</span>';
    }
    outputCell.title = formatValue(newResult.output) || '';
  }

  // Update reference cell
  const refCell = row.querySelector('td[data-col="reference"]');
  if (refCell && newResult.reference != null) {
    const content = `<div class="cell-content line-clamp-4 text-[12px] text-theme-text updating">${escapeHtml(formatValue(newResult.reference))}</div>`;
    refCell.innerHTML = content;
    refCell.title = formatValue(newResult.reference) || '';
    requestAnimationFrame(() => refCell.querySelector('.cell-content')?.classList.remove('updating'));
  }

  // Update scores cell with staggered animation
  const scoresCell = row.querySelector('td[data-col="scores"]');
  if (scoresCell && newStatus !== 'running' && newResult.scores?.length) {
    const scores = newResult.scores;
    const badgesHtml = scores.map((s, i) => {
      let badgeClass = 'bg-theme-bg-elevated text-theme-text-muted';
      if (s.passed === true) badgeClass = 'bg-accent-success-bg text-accent-success';
      else if (s.passed === false) badgeClass = 'bg-accent-error-bg text-accent-error';
      const val = s.value != null ? `:${typeof s.value === 'number' ? s.value.toFixed(1) : s.value}` : '';
      const title = `${s.key}${s.value != null ? ': ' + (typeof s.value === 'number' ? s.value.toFixed(3) : s.value) : ''}${s.notes ? ' — ' + s.notes : ''}`;
      return `<span class="score-badge entering shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${badgeClass}" title="${escapeHtml(title)}" style="transition-delay: ${i * 60}ms">${escapeHtml(s.key)}${val}</span>`;
    }).join('');
    scoresCell.innerHTML = `<div class="flex flex-wrap gap-1">${badgesHtml}</div>`;
    // Update sort value for scores column
    const firstScore = scores[0];
    let sortVal = '';
    if (firstScore.value != null) sortVal = firstScore.value;
    else if (firstScore.passed === true) sortVal = 1;
    else if (firstScore.passed === false) sortVal = 0;
    scoresCell.dataset.value = sortVal;
    requestAnimationFrame(() => {
      scoresCell.querySelectorAll('.score-badge').forEach(badge => badge.classList.remove('entering'));
    });
  }

  // Update latency cell with pop-in animation
  const latencyCell = row.querySelector('td[data-col="latency"]');
  if (latencyCell && newResult.latency != null) {
    const lat = newResult.latency;
    const latColor = lat <= 1 ? 'text-accent-success' : (lat <= 5 ? 'text-theme-text-muted' : 'text-accent-error');
    latencyCell.innerHTML = `<span class="latency-value entering font-mono text-[11px] ${latColor}">${lat.toFixed(2)}s</span>`;
    latencyCell.dataset.value = lat;
    requestAnimationFrame(() => latencyCell.querySelector('.latency-value')?.classList.remove('entering'));
  }

  // Update error cell
  const errorCell = row.querySelector('td[data-col="error"]');
  if (errorCell) {
    if (newResult.error) {
      errorCell.innerHTML = `<div class="cell-content line-clamp-2 text-[12px] text-accent-error updating">${escapeHtml(newResult.error)}</div>`;
      requestAnimationFrame(() => errorCell.querySelector('.cell-content')?.classList.remove('updating'));
    }
    errorCell.title = newResult.error || '';
  }

  // Re-sync checkbox
  const cb = row.querySelector('.row-checkbox');
  if (cb) cb.checked = selectedIndices.has(index);
}

function hasRunningResults(data) {
  // Poll when there are running/pending results OR not_started (might be auto-started via --run)
  return (data.results || []).some(r => ['pending', 'running', 'not_started'].includes(r.result?.status));
}
function getFilters() { return _filters; }
function setFilters(f) { _filters = f || defaultFilters(); sessionStorage.setItem('ezvals:filters', JSON.stringify(_filters)); renderActiveFilters(); applyAllFilters(); }
function isFilterActive() {
  const f = getFilters();
  const dsCount = (f.selectedDatasets?.include?.length || 0) + (f.selectedDatasets?.exclude?.length || 0);
  const lblCount = (f.selectedLabels?.include?.length || 0) + (f.selectedLabels?.exclude?.length || 0);
  const traceCount = (f.hasError !== null ? 1 : 0) + (f.hasUrl !== null ? 1 : 0) + (f.hasMessages !== null ? 1 : 0);
  const hasFilterRules = (f.valueRules.length + f.passedRules.length + dsCount + lblCount + traceCount + (f.annotation !== 'any' ? 1 : 0)) > 0;
  const hasSearch = (document.getElementById('search-input')?.value || '').trim().length > 0;
  return hasFilterRules || hasSearch;
}

let _isRunning = false;
function updateSelectionUI() {
  const count = selectedIndices.size;
  updateSelectAllState();
  if (typeof updateRunButtonState === 'function') updateRunButtonState();
}
function setRunningState(running) {
  _isRunning = running;
  const btn = document.getElementById('play-btn');
  const playIcon = btn?.querySelector('.play-icon');
  const stopIcon = btn?.querySelector('.stop-icon');
  if (running) {
    btn?.classList.remove('bg-emerald-600', 'hover:bg-emerald-500');
    btn?.classList.add('bg-rose-600', 'hover:bg-rose-500');
    playIcon?.classList.add('hidden'); stopIcon?.classList.remove('hidden');
  } else {
    btn?.classList.remove('bg-rose-600', 'hover:bg-rose-500');
    btn?.classList.add('bg-emerald-600', 'hover:bg-emerald-500');
    playIcon?.classList.remove('hidden'); stopIcon?.classList.add('hidden');
  }
  // Add/remove pulsing animation on progress bar when running
  const progressBar = document.querySelector('.stats-progress-bar');
  const progressFill = document.querySelector('.stats-progress-fill');
  if (running) {
    progressBar?.classList.add('ring-2', 'ring-emerald-400/50', 'ring-offset-1', 'ring-offset-zinc-900');
    progressFill?.classList.add('progress-active');
  } else {
    progressBar?.classList.remove('ring-2', 'ring-emerald-400/50', 'ring-offset-1', 'ring-offset-zinc-900');
    progressFill?.classList.remove('progress-active');
    // Show success animation if we were running (progress bar exists with fill at 100%)
    const progressContainer = document.querySelector('.stats-progress');
    if (progressContainer && progressFill && parseFloat(progressFill.style.width) >= 100) {
      progressContainer.innerHTML = `<span class="text-emerald-400 text-lg animate-success-flash flex justify-center w-full">✓</span>`;
      setTimeout(() => progressContainer.remove(), 2000);
    }
  }
  if (typeof updateRunButtonState === 'function') updateRunButtonState();
}
function checkRunningState() { setRunningState(!!document.querySelector('[data-status="pending"], [data-status="running"]')); }
function updateSelectAllState() {
  const selectAll = document.getElementById('select-all-checkbox');
  if (!selectAll) return;
  const visibleRows = getVisibleMainRows();
  if (visibleRows.length === 0) { selectAll.checked = false; selectAll.indeterminate = false; return; }
  const visibleSelected = visibleRows.filter(r => selectedIndices.has(parseInt(r.dataset.rowId))).length;
  selectAll.checked = visibleSelected === visibleRows.length;
  selectAll.indeterminate = visibleSelected > 0 && visibleSelected < visibleRows.length;
}
function getVisibleMainRows() { return Array.from(document.querySelectorAll('tr[data-row="main"]:not(.hidden)')); }
function syncCheckboxesToSelection() { document.querySelectorAll('.row-checkbox').forEach(cb => { cb.checked = selectedIndices.has(parseInt(cb.dataset.rowId)); }); updateSelectionUI(); }

function setupDropdown(toggleId, menuId) {
  const toggle = document.getElementById(toggleId);
  const menu = document.getElementById(menuId);
  if (!toggle || !menu) return;
  toggle.addEventListener('click', (e) => {
    e.stopPropagation();
    const isActive = menu.classList.contains('active');
    document.querySelectorAll('.filters-panel.active, .columns-panel.active').forEach(m => m.classList.remove('active'));
    if (!isActive) menu.classList.add('active');
  });
}
document.addEventListener('click', (e) => {
  if (!e.target.closest('.dropdown') && !e.target.closest('.filters-panel') && !e.target.closest('.columns-panel'))
    document.querySelectorAll('.filters-panel.active, .columns-panel.active').forEach(m => m.classList.remove('active'));
});
setupDropdown('filters-toggle', 'filters-menu');
setupDropdown('columns-toggle', 'columns-menu');

function renderActiveFilters() {
  const f = getFilters();
  const ct = document.getElementById('active-filters');
  const badge = document.getElementById('filters-count-badge');
  if (!ct) return;
  ct.innerHTML = '';
  let count = 0;
  f.valueRules.forEach((r, idx) => { count++; const el = document.createElement('span'); el.className = 'inline-flex items-center gap-1 rounded bg-blue-500/20 px-2 py-0.5 text-[10px] text-blue-300'; el.innerHTML = `${r.key} ${r.op} ${r.value}<button class="ml-1 hover:text-white" onclick="removeValueRule(${idx})">×</button>`; ct.appendChild(el); });
  f.passedRules.forEach((r, idx) => { count++; const el = document.createElement('span'); el.className = 'inline-flex items-center gap-1 rounded bg-blue-500/20 px-2 py-0.5 text-[10px] text-blue-300'; el.innerHTML = `${r.key} = ${r.value ? 'pass' : 'fail'}<button class="ml-1 hover:text-white" onclick="removePassedRule(${idx})">×</button>`; ct.appendChild(el); });
  if (f.annotation && f.annotation !== 'any') { count++; const el = document.createElement('span'); el.className = 'inline-flex items-center gap-1 rounded bg-blue-500/20 px-2 py-0.5 text-[10px] text-blue-300'; el.innerHTML = `note: ${f.annotation}<button class="ml-1 hover:text-white" onclick="removeAnnotationFilter()">×</button>`; ct.appendChild(el); }
  (f.selectedDatasets?.include || []).forEach((ds) => { count++; const el = document.createElement('span'); el.className = 'inline-flex items-center gap-1 rounded bg-emerald-500/20 px-2 py-0.5 text-[10px] text-emerald-300'; el.innerHTML = `${ds}<button class="ml-1 hover:text-white" onclick="removeDatasetFilter('${ds}', 'include')">×</button>`; ct.appendChild(el); });
  (f.selectedDatasets?.exclude || []).forEach((ds) => { count++; const el = document.createElement('span'); el.className = 'inline-flex items-center gap-1 rounded bg-rose-500/20 px-2 py-0.5 text-[10px] text-rose-300'; el.innerHTML = `✕ ${ds}<button class="ml-1 hover:text-white" onclick="removeDatasetFilter('${ds}', 'exclude')">×</button>`; ct.appendChild(el); });
  (f.selectedLabels?.include || []).forEach((la) => { count++; const el = document.createElement('span'); el.className = 'inline-flex items-center gap-1 rounded bg-amber-500/20 px-2 py-0.5 text-[10px] text-amber-300'; el.innerHTML = `${la}<button class="ml-1 hover:text-white" onclick="removeLabelFilter('${la}', 'include')">×</button>`; ct.appendChild(el); });
  (f.selectedLabels?.exclude || []).forEach((la) => { count++; const el = document.createElement('span'); el.className = 'inline-flex items-center gap-1 rounded bg-rose-500/20 px-2 py-0.5 text-[10px] text-rose-300'; el.innerHTML = `✕ ${la}<button class="ml-1 hover:text-white" onclick="removeLabelFilter('${la}', 'exclude')">×</button>`; ct.appendChild(el); });
  if (f.hasError !== null) { count++; const el = document.createElement('span'); el.className = f.hasError ? 'inline-flex items-center gap-1 rounded bg-rose-500/20 px-2 py-0.5 text-[10px] text-rose-300' : 'inline-flex items-center gap-1 rounded bg-emerald-500/20 px-2 py-0.5 text-[10px] text-emerald-300'; el.innerHTML = `${f.hasError ? 'has' : 'no'} error<button class="ml-1 hover:text-white" onclick="removeTraceFilter('hasError')">×</button>`; ct.appendChild(el); }
  if (f.hasUrl !== null) { count++; const el = document.createElement('span'); el.className = f.hasUrl ? 'inline-flex items-center gap-1 rounded bg-cyan-500/20 px-2 py-0.5 text-[10px] text-cyan-300' : 'inline-flex items-center gap-1 rounded bg-rose-500/20 px-2 py-0.5 text-[10px] text-rose-300'; el.innerHTML = `${f.hasUrl ? 'has' : 'no'} URL<button class="ml-1 hover:text-white" onclick="removeTraceFilter('hasUrl')">×</button>`; ct.appendChild(el); }
  if (f.hasMessages !== null) { count++; const el = document.createElement('span'); el.className = f.hasMessages ? 'inline-flex items-center gap-1 rounded bg-cyan-500/20 px-2 py-0.5 text-[10px] text-cyan-300' : 'inline-flex items-center gap-1 rounded bg-rose-500/20 px-2 py-0.5 text-[10px] text-rose-300'; el.innerHTML = `${f.hasMessages ? 'has' : 'no'} messages<button class="ml-1 hover:text-white" onclick="removeTraceFilter('hasMessages')">×</button>`; ct.appendChild(el); }
  if (badge) { badge.textContent = count; badge.classList.toggle('active', count > 0); }
}

window.removeValueRule = (idx) => { const f = getFilters(); f.valueRules.splice(idx, 1); setFilters(f); };
window.removePassedRule = (idx) => { const f = getFilters(); f.passedRules.splice(idx, 1); setFilters(f); };
window.removeAnnotationFilter = () => { const f = getFilters(); f.annotation = 'any'; setFilters(f); };
window.removeDatasetFilter = (ds, type) => { const f = getFilters(); const idx = f.selectedDatasets[type].indexOf(ds); if (idx >= 0) f.selectedDatasets[type].splice(idx, 1); setFilters(f); populateDatasetLabelPills(); };
window.removeLabelFilter = (lbl, type) => { const f = getFilters(); const idx = f.selectedLabels[type].indexOf(lbl); if (idx >= 0) f.selectedLabels[type].splice(idx, 1); setFilters(f); populateDatasetLabelPills(); };
window.removeTraceFilter = (key) => { const f = getFilters(); f[key] = null; setFilters(f); updateTraceFilterButtons(); };

function applyColumnVisibility() {
  const toggles = Array.from(document.querySelectorAll('#columns-menu input[data-col]'));
  if (!toggles.length) return;
  const cols = toggles.map((cb) => cb.getAttribute("data-col"));
  const stored = getHiddenCols();
  const hidden = new Set(stored.filter((c) => cols.includes(c)));
  if (hidden.size !== stored.length) setHiddenCols([...hidden]);
  cols.forEach((col) => { document.querySelectorAll(`#results-table [data-col="${col}"]`).forEach((el) => { el.classList.toggle('hidden', hidden.has(col)); }); });
  toggles.forEach((cb) => { cb.checked = !hidden.has(cb.getAttribute("data-col")); });
}
document.querySelectorAll('#columns-menu input[data-col]').forEach((cb) => {
  cb.addEventListener("change", (e) => { const col = e.target.getAttribute("data-col"); const hidden = new Set(getHiddenCols()); if (e.target.checked) hidden.delete(col); else hidden.add(col); setHiddenCols([...hidden]); applyColumnVisibility(); });
});
document.getElementById("reset-columns")?.addEventListener("click", () => { setHiddenCols(DEFAULT_HIDDEN_COLS); applyColumnVisibility(); });
document.getElementById("reset-sorting")?.addEventListener("click", () => { setSortState([]); const table = document.getElementById("results-table"); if (table) applySortState(table); });
document.getElementById("reset-widths")?.addEventListener("click", () => { setColWidths({}); document.querySelectorAll('#results-table thead th[data-col]').forEach((th) => { th.style.width = ''; }); });
document.getElementById('clear-filters')?.addEventListener('click', () => { setFilters(defaultFilters()); populateDatasetLabelPills(); });

(function wireFilters() {
  const keySelect = document.getElementById('key-select');
  const addFv = document.getElementById('add-fv');
  const fvOp = document.getElementById('fv-op');
  const fvVal = document.getElementById('fv-val');
  const addFp = document.getElementById('add-fp');
  const fpVal = document.getElementById('fp-val');
  if (addFv) addFv.addEventListener('click', () => { const k = (keySelect?.value || '').trim(); const v = parseFloat(fvVal.value); if (!k || Number.isNaN(v)) return; const f = getFilters(); f.valueRules.push({ key: k, op: fvOp.value, value: v }); setFilters(f); fvVal.value = ''; });
  if (addFp) addFp.addEventListener('click', () => { const k = (keySelect?.value || '').trim(); if (!k) return; const f = getFilters(); f.passedRules.push({ key: k, value: fpVal.value === 'true' }); setFilters(f); });
  renderActiveFilters();
})();

function computeScoreKeys() {
  const tbody = document.querySelector('#results-table tbody');
  if (!tbody) return { all: [], meta: {} };
  const keys = new Set();
  const meta = {};
  tbody.querySelectorAll("tr[data-row='main']").forEach(tr => {
    let scores = []; try { scores = JSON.parse(tr.getAttribute('data-scores') || '[]') || []; } catch {}
    (scores || []).forEach(s => { const k = s && s.key; if (!k) return; keys.add(k); const m = meta[k] || (meta[k] = { hasNumeric: false, hasPassed: false }); if (!Number.isNaN(parseFloat(s.value))) m.hasNumeric = true; if (s.passed === true || s.passed === false) m.hasPassed = true; });
  });
  return { all: Array.from(keys).sort(), meta };
}
function populateScoreKeySelects() {
  const ks = computeScoreKeys();
  const sel = document.getElementById('key-select');
  if (!sel) return;
  const current = sel.value;
  sel.innerHTML = '';
  ks.all.forEach(k => { const opt = document.createElement('option'); opt.value = k; opt.textContent = k; sel.appendChild(opt); });
  if (current && ks.all.includes(current)) sel.value = current; else if (ks.all.length) sel.value = ks.all[0];
  updateFilterSectionsVisibility();
}
function updateFilterSectionsVisibility() {
  const sel = document.getElementById('key-select');
  const ks = computeScoreKeys();
  const k = sel?.value || '';
  const m = ks.meta[k] || { hasNumeric: false, hasPassed: false };
  document.getElementById('value-section')?.classList.toggle('hidden', !m.hasNumeric);
  document.getElementById('passed-section')?.classList.toggle('hidden', !m.hasPassed);
}
document.getElementById('key-select')?.addEventListener('change', updateFilterSectionsVisibility);

function computeDatasetLabels() {
  const tbody = document.querySelector('#results-table tbody');
  if (!tbody) return { datasets: [], labels: [] };
  const datasets = new Set();
  const labels = new Set();
  tbody.querySelectorAll("tr[data-row='main']").forEach(tr => {
    const ds = (tr.getAttribute('data-dataset') || '').trim();
    if (ds) datasets.add(ds);
    try { const lbls = JSON.parse(tr.getAttribute('data-labels') || '[]') || []; lbls.forEach(l => labels.add(l)); } catch {}
  });
  return { datasets: Array.from(datasets).sort(), labels: Array.from(labels).sort() };
}
function populateDatasetLabelPills() {
  const { datasets, labels } = computeDatasetLabels();
  const f = getFilters();
  const dsCt = document.getElementById('dataset-pills');
  const laCt = document.getElementById('label-pills');
  const base = 'rounded px-2 py-0.5 text-[10px] font-medium cursor-pointer ';
  const gray = 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700';
  const blue = 'bg-blue-600 text-white';
  const rose = 'bg-rose-500/30 text-rose-300';
  if (dsCt) { dsCt.innerHTML = ''; if (datasets.length === 0) { dsCt.innerHTML = '<span class="text-[10px] text-zinc-600 italic">None</span>'; } else { datasets.forEach(ds => { const isInc = f.selectedDatasets?.include?.includes(ds); const isExc = f.selectedDatasets?.exclude?.includes(ds); const pill = document.createElement('button'); pill.className = base + (isInc ? blue : isExc ? rose : gray); pill.textContent = isExc ? '✕ ' + ds : ds; pill.onclick = (e) => { e.stopPropagation(); toggleDatasetFilter(ds); }; dsCt.appendChild(pill); }); } }
  if (laCt) { laCt.innerHTML = ''; if (labels.length === 0) { laCt.innerHTML = '<span class="text-[10px] text-zinc-600 italic">None</span>'; } else { labels.forEach(la => { const isInc = f.selectedLabels?.include?.includes(la); const isExc = f.selectedLabels?.exclude?.includes(la); const pill = document.createElement('button'); pill.className = base + (isInc ? blue : isExc ? rose : gray); pill.textContent = isExc ? '✕ ' + la : la; pill.onclick = (e) => { e.stopPropagation(); toggleLabelFilter(la); }; laCt.appendChild(pill); }); } }
}
function toggleDatasetFilter(ds) { const f = getFilters(); if (!f.selectedDatasets) f.selectedDatasets = { include: [], exclude: [] }; const incIdx = f.selectedDatasets.include.indexOf(ds); const excIdx = f.selectedDatasets.exclude.indexOf(ds); if (incIdx >= 0) { f.selectedDatasets.include.splice(incIdx, 1); f.selectedDatasets.exclude.push(ds); } else if (excIdx >= 0) { f.selectedDatasets.exclude.splice(excIdx, 1); } else { f.selectedDatasets.include.push(ds); } setFilters(f); populateDatasetLabelPills(); }
function toggleLabelFilter(la) { const f = getFilters(); if (!f.selectedLabels) f.selectedLabels = { include: [], exclude: [] }; const incIdx = f.selectedLabels.include.indexOf(la); const excIdx = f.selectedLabels.exclude.indexOf(la); if (incIdx >= 0) { f.selectedLabels.include.splice(incIdx, 1); f.selectedLabels.exclude.push(la); } else if (excIdx >= 0) { f.selectedLabels.exclude.splice(excIdx, 1); } else { f.selectedLabels.include.push(la); } setFilters(f); populateDatasetLabelPills(); }
function toggleTraceFilter(key) { const f = getFilters(); if (f[key] === null) f[key] = true; else if (f[key] === true) f[key] = false; else f[key] = null; setFilters(f); updateTraceFilterButtons(); }
function updateTraceFilterButtons() {
  const f = getFilters();
  [['hasError', 'filter-has-error'], ['hasUrl', 'filter-has-url'], ['hasMessages', 'filter-has-messages']].forEach(([key, id]) => {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.className = 'rounded px-2 py-0.5 text-[10px] font-medium ';
    if (f[key] === true) btn.className += 'bg-blue-600 text-white';
    else if (f[key] === false) btn.className += 'bg-rose-500/30 text-rose-300';
    else btn.className += 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-300';
  });
}
document.getElementById('filter-has-error')?.addEventListener('click', () => toggleTraceFilter('hasError'));
document.getElementById('filter-has-url')?.addEventListener('click', () => toggleTraceFilter('hasUrl'));
document.getElementById('filter-has-messages')?.addEventListener('click', () => toggleTraceFilter('hasMessages'));
function updateAnnotationButton() {
  const f = getFilters();
  const btn = document.getElementById('filter-has-annotation');
  if (!btn) return;
  btn.className = 'rounded px-2 py-0.5 text-[10px] font-medium ';
  if (f.annotation === 'yes') { btn.className += 'bg-blue-600 text-white'; btn.textContent = 'Has Note'; }
  else if (f.annotation === 'no') { btn.className += 'bg-rose-500/30 text-rose-300'; btn.textContent = 'No Note'; }
  else { btn.className += 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-300'; btn.textContent = 'Has Note'; }
}
document.getElementById('filter-has-annotation')?.addEventListener('click', () => { const f = getFilters(); if (f.annotation === 'any') f.annotation = 'yes'; else if (f.annotation === 'yes') f.annotation = 'no'; else f.annotation = 'any'; setFilters(f); updateAnnotationButton(); });

const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
function getCellValue(tr, col) { const td = tr.querySelector(`td[data-col="${col}"]`); if (!td) return ""; const dv = td.getAttribute("data-value"); return dv !== null ? dv : td.textContent.trim(); }
function parseValue(value, type) { if (type === "number") { const num = parseFloat(value); return isNaN(num) ? Number.POSITIVE_INFINITY : num; } return value; }
function compareValues(a, b, type, col) {
  if (type === "number") {
    // For scores column, empty/unscored values should ALWAYS sort to bottom
    if (col === 'scores') {
      const aEmpty = !isFinite(a);
      const bEmpty = !isFinite(b);
      if (aEmpty && !bEmpty) return 1; // a (empty) goes after b
      if (!aEmpty && bEmpty) return -1; // b (empty) goes after a
      if (aEmpty && bEmpty) return 0; // both empty, equal
    }
    return a - b;
  }
  return collator.compare(a, b);
}
function applySortState(table) {
  const state = getSortState();
  const headers = table.querySelectorAll("thead th[data-col]");
  headers.forEach((th) => th.setAttribute("aria-sort", "none"));
  const tbody = table.querySelector("tbody");
  const mainRows = Array.from(tbody.querySelectorAll("tr[data-row='main']"));
  mainRows.forEach((tr, i) => { if (!tr.hasAttribute("data-orig-index")) tr.setAttribute("data-orig-index", String(i)); });
  if (!state.length) {
    mainRows
      .slice()
      .sort((a, b) => Number(a.getAttribute("data-orig-index")) - Number(b.getAttribute("data-orig-index")))
      .forEach((tr) => tbody.appendChild(tr));
    return;
  }
  state.forEach((s) => { const th = table.querySelector(`thead th[data-col="${s.col}"]`); if (th) th.setAttribute("aria-sort", s.dir === "asc" ? "ascending" : "descending"); });
  mainRows
    .slice()
    .sort((ra, rb) => {
      for (const s of state) {
        const type = s.type || "string";
        const va = parseValue(getCellValue(ra, s.col), type);
        const vb = parseValue(getCellValue(rb, s.col), type);
        const cmp = compareValues(va, vb, type, s.col);
        // For scores, empty values always at bottom (cmp handles this), so don't negate
        if (cmp !== 0) {
          if (s.col === 'scores' && (!isFinite(va) || !isFinite(vb))) return cmp;
          return s.dir === "asc" ? cmp : -cmp;
        }
      }
      return Number(ra.getAttribute("data-orig-index")) - Number(rb.getAttribute("data-orig-index"));
    })
    .forEach((tr) => tbody.appendChild(tr));
}
function toggleSort(table, col, type, multi) {
  let state = getSortState();
  const idx = state.findIndex((s) => s.col === col);
  if (multi) { if (idx === -1) state.push({ col, dir: "asc", type }); else if (state[idx].dir === "asc") state[idx].dir = "desc"; else state.splice(idx, 1); }
  else { if (idx === 0 && state[0].dir === "asc") state = [{ col, dir: "desc", type }]; else if (idx === 0 && state[0].dir === "desc") state = []; else state = [{ col, dir: "asc", type }]; }
  setSortState(state);
  applySortState(table);
}
document.addEventListener("click", function (e) { const th = e.target.closest("#results thead th[data-col]"); if (!th) return; const col = th.getAttribute("data-col"); const table = document.getElementById("results-table"); if (!table) return; const type = th.getAttribute("data-type") || "string"; toggleSort(table, col, type, e.shiftKey); });

function applyColumnWidths(table) { if (!table) return; const widths = getColWidths(); Object.keys(widths).forEach((col) => { const w = widths[col]; if (!w) return; const th = table.querySelector(`thead th[data-col="${col}"]`); if (th) th.style.width = `${w}px`; }); }
function initResizableColumns(table) {
  if (!table) return;
  const widths = getColWidths();
  const ths = table.querySelectorAll('thead th[data-col]');
  ths.forEach((th) => {
    if (getComputedStyle(th).position === 'static') th.style.position = 'relative';
    if (th.querySelector('.col-resizer')) return;
    const handle = document.createElement('div'); handle.className = 'col-resizer'; th.appendChild(handle);
    let startX = 0, startWidth = 0; const colKey = th.getAttribute('data-col'); const minWidth = 50, maxWidth = 500;
    function onMouseMove(e) { const dx = e.clientX - startX; let newW = Math.max(minWidth, Math.min(maxWidth, startWidth + dx)); th.style.width = `${newW}px`; }
    function onMouseUp() { document.removeEventListener('mousemove', onMouseMove); document.removeEventListener('mouseup', onMouseUp); document.body.classList.remove('ezvals-col-resize'); const map = getColWidths(); map[colKey] = Math.round(th.getBoundingClientRect().width); setColWidths(map); }
    handle.addEventListener('mousedown', (e) => { e.preventDefault(); e.stopPropagation(); startX = e.clientX; startWidth = th.getBoundingClientRect().width; document.addEventListener('mousemove', onMouseMove); document.addEventListener('mouseup', onMouseUp); document.body.classList.add('ezvals-col-resize'); });
    handle.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); });
    const saved = widths[colKey]; if (saved) th.style.width = `${saved}px`;
  });
}

const searchInput = document.getElementById('search-input');
if (searchInput) { let timer; searchInput.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => { sessionStorage.setItem('ezvals:search', searchInput.value); applyAllFilters(); }, 120); }); }
function compare(op, a, b) { if (op === '>') return a > b; if (op === '>=') return a >= b; if (op === '<') return a < b; if (op === '<=') return a <= b; if (op === '==') return a === b; if (op === '!=') return a !== b; return false; }
function rowMatchesFilters(mainTr) {
  const f = getFilters();
  if (f.annotation && f.annotation !== 'any') { const ann = (mainTr?.getAttribute('data-annotation') || '').trim(); const has = !!ann; if (f.annotation === 'yes' && !has) return false; if (f.annotation === 'no' && has) return false; }
  const ds = (mainTr?.getAttribute('data-dataset') || '').trim();
  if (f.selectedDatasets?.include?.length > 0) { if (!f.selectedDatasets.include.includes(ds)) return false; }
  if (f.selectedDatasets?.exclude?.includes(ds)) return false;
  let rowLabels = []; try { rowLabels = JSON.parse(mainTr?.getAttribute('data-labels') || '[]') || []; } catch {}
  if (f.selectedLabels?.include?.length > 0) { if (!f.selectedLabels.include.some(l => rowLabels.includes(l))) return false; }
  if (f.selectedLabels?.exclude?.length > 0) { if (f.selectedLabels.exclude.some(l => rowLabels.includes(l))) return false; }
  if (f.hasError === true) { if (mainTr?.getAttribute('data-has-error') !== 'true') return false; } else if (f.hasError === false) { if (mainTr?.getAttribute('data-has-error') === 'true') return false; }
  if (f.hasUrl === true) { if (mainTr?.getAttribute('data-has-url') !== 'true') return false; } else if (f.hasUrl === false) { if (mainTr?.getAttribute('data-has-url') === 'true') return false; }
  if (f.hasMessages === true) { if (mainTr?.getAttribute('data-has-messages') !== 'true') return false; } else if (f.hasMessages === false) { if (mainTr?.getAttribute('data-has-messages') === 'true') return false; }
  let scores = []; try { scores = JSON.parse(mainTr?.getAttribute('data-scores') || '[]') || []; } catch {}
  for (const vr of (f.valueRules || [])) { const s = scores.find(x => x && x.key === vr.key); if (!s) return false; const val = parseFloat(s.value); if (Number.isNaN(val)) return false; if (!compare(vr.op, val, vr.value)) return false; }
  for (const pr of (f.passedRules || [])) { const s = scores.find(x => x && x.key === pr.key); if (!s) return false; if ((s.passed === true) !== (pr.value === true)) return false; }
  return true;
}
function applyAllFilters() {
  const q = (document.getElementById('search-input')?.value || '').toLowerCase().trim();
  const tbody = document.querySelector('#results-table tbody');
  if (!tbody) return;
  tbody.querySelectorAll("tr[data-row='main']").forEach((tr) => { let show = true; if (q) { if (!tr.textContent.toLowerCase().includes(q)) show = false; } if (show) show = rowMatchesFilters(tr); tr.classList.toggle('hidden', !show); });
  updateStatsForFilters();
}
function initScrollRestoration() { const savedY = sessionStorage.getItem('ezvals:scrollY'); if (savedY !== null) { window.scrollTo(0, parseInt(savedY, 10)); sessionStorage.removeItem('ezvals:scrollY'); } const params = new URLSearchParams(window.location.search); if (params.has('scroll')) { history.replaceState(null, '', window.location.pathname); } }
document.addEventListener('click', (e) => { const link = e.target.closest('a[href*="/runs/"][href*="/results/"]'); if (link) { sessionStorage.setItem('ezvals:scrollY', window.scrollY.toString()); } });
function wireExportButtons() { const table = document.getElementById('results-table'); const runId = table ? (table.getAttribute('data-run-id') || 'latest') : 'latest'; document.getElementById('export-json-btn')?.addEventListener('click', () => { window.location.href = `/api/runs/${runId}/export/json`; }); document.getElementById('export-csv-btn')?.addEventListener('click', () => { window.location.href = `/api/runs/${runId}/export/csv`; }); }

// Click on .copyable elements to copy their text
document.addEventListener('click', async (e) => {
  const el = e.target.closest('.copyable');
  if (!el || el.querySelector('input')) return;
  try {
    await navigator.clipboard.writeText(el.innerText);
    // Show "Copied!" tooltip
    const tooltip = document.createElement('span');
    tooltip.textContent = 'Copied!';
    tooltip.className = 'absolute -top-6 left-1/2 -translate-x-1/2 rounded bg-zinc-700 px-2 py-0.5 text-[10px] text-white whitespace-nowrap';
    el.style.position = 'relative';
    el.appendChild(tooltip);
    setTimeout(() => tooltip.remove(), 1000);
  } catch { /* ignore */ }
});

// Edit run name inline (works for both compact and expanded views)
document.addEventListener('click', (e) => {
  const btn = e.target.closest('.edit-run-btn') || e.target.closest('.edit-run-btn-expanded');
  if (!btn) return;
  const isExpanded = btn.classList.contains('edit-run-btn-expanded');
  const span = document.getElementById(isExpanded ? 'run-name-expanded' : 'run-name-text');
  if (!span || span.querySelector('input')) return;
  const originalText = span.textContent;
  const input = document.createElement('input');
  input.type = 'text';
  input.value = originalText;
  input.className = isExpanded
    ? 'font-mono text-sm bg-zinc-800 border border-zinc-600 rounded px-1 w-28 text-white outline-none focus:border-zinc-500'
    : 'font-mono text-[11px] bg-zinc-800 border border-zinc-600 rounded px-1 w-24 text-accent-link outline-none focus:border-zinc-500';
  span.textContent = '';
  span.appendChild(input);
  input.focus();
  input.select();
  // Turn pencil into checkmark
  const svg = btn.querySelector('svg use');
  if (svg) svg.setAttribute('href', '#icon-check');
  btn.classList.add('text-emerald-500', 'opacity-100');
  btn.classList.remove('text-zinc-600', 'opacity-0');
  let done = false;
  let savingViaButton = false;
  const save = async () => {
    if (done) return;
    done = true;
    const newName = input.value.trim();
    if (newName && newName !== originalText && _currentRunId) {
      try {
        await fetch(`/api/runs/${_currentRunId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ run_name: newName })
        });
      } catch (err) {
        console.error('Rename failed:', err);
      }
    }
    loadResults();
  };
  const cancel = () => { if (!done && !savingViaButton) { done = true; loadResults(); } };
  input.addEventListener('blur', () => setTimeout(cancel, 100));
  input.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') { ev.preventDefault(); save(); }
    if (ev.key === 'Escape') { ev.preventDefault(); done = true; loadResults(); }
  });
  // Clicking checkmark saves (use mousedown to fire before blur)
  btn.addEventListener('mousedown', (ev) => { ev.preventDefault(); savingViaButton = true; save(); }, { once: true });
});

// Run button mode: 'run' (fresh), 'rerun', or 'new'
const RUN_MODE_KEY = 'ezvals:runMode';
let _runMode = localStorage.getItem(RUN_MODE_KEY) || 'rerun';
let _hasRunBefore = false;

function updateRunButtonState() {
  const playBtn = document.getElementById('play-btn');
  const playBtnText = document.getElementById('play-btn-text');
  const dropdownToggle = document.getElementById('run-dropdown-toggle');
  const rerunCheck = document.getElementById('rerun-check');
  const newCheck = document.getElementById('new-check');

  if (!playBtn) return;

  // Determine button state based on context
  const hasSelections = selectedIndices.size > 0;

  if (_isRunning) {
    // Running state - show Stop
    playBtnText.textContent = 'Stop';
    playBtn.classList.remove('rounded-l');
    playBtn.classList.add('rounded');
    dropdownToggle?.classList.add('hidden');
    dropdownToggle?.classList.remove('flex');
  } else if (!_hasRunBefore) {
    // Fresh session - just "Run", no dropdown
    playBtnText.textContent = 'Run';
    playBtn.classList.remove('rounded-l');
    playBtn.classList.add('rounded');
    dropdownToggle?.classList.add('hidden');
    dropdownToggle?.classList.remove('flex');
  } else if (hasSelections) {
    // Checkboxes selected - just "Rerun", no dropdown
    playBtnText.textContent = 'Rerun';
    playBtn.classList.remove('rounded-l');
    playBtn.classList.add('rounded');
    dropdownToggle?.classList.add('hidden');
    dropdownToggle?.classList.remove('flex');
  } else {
    // Previous runs exist, no selection - split button
    playBtnText.textContent = _runMode === 'new' ? 'New Run' : 'Rerun';
    playBtn.classList.remove('rounded');
    playBtn.classList.add('rounded-l');
    dropdownToggle?.classList.remove('hidden');
    dropdownToggle?.classList.add('flex');

    // Update check marks
    if (rerunCheck) rerunCheck.classList.toggle('invisible', _runMode !== 'rerun');
    if (newCheck) newCheck.classList.toggle('invisible', _runMode !== 'new');
  }
}

async function executeRun(mode) {
  if (_isRunning) {
    try { await fetch('/api/runs/stop', { method: 'POST' }); } catch (e) { console.error('Stop failed:', e); }
    await loadResults();
    return;
  }

  try {
    let endpoint = '/api/runs/rerun';
    let body = {};

    if (selectedIndices.size > 0) {
      // Selective rerun - always use rerun endpoint
      body = { indices: Array.from(selectedIndices) };
    } else if (mode === 'new') {
      // New run - auto-generated name, no prompt
      endpoint = '/api/runs/new';
      body = {};
    }

    const resp = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });

    if (!resp.ok) {
      let msg = '';
      try { const data = await resp.json(); msg = data?.detail || data?.message || ''; }
      catch { msg = await resp.text(); }
      throw new Error(msg || `HTTP ${resp.status}`);
    }

    _hasRunBefore = true;
    setRunningState(true);
    await loadResults();
  } catch (e) { alert('Run failed: ' + e); }
}

document.getElementById('play-btn')?.addEventListener('click', async () => {
  const hasSelections = selectedIndices.size > 0;
  if (!_hasRunBefore || hasSelections) {
    // Fresh session or selective rerun
    await executeRun('rerun');
  } else {
    // Use current mode
    await executeRun(_runMode);
  }
});

// Dropdown toggle
document.getElementById('run-dropdown-toggle')?.addEventListener('click', (e) => {
  e.stopPropagation();
  const menu = document.getElementById('run-dropdown-menu');
  menu?.classList.toggle('hidden');
});

// Dropdown option handlers - just toggle setting, don't trigger run
document.getElementById('run-rerun-option')?.addEventListener('click', () => {
  _runMode = 'rerun';
  localStorage.setItem(RUN_MODE_KEY, 'rerun');
  document.getElementById('run-dropdown-menu')?.classList.add('hidden');
  updateRunButtonState();
});

document.getElementById('run-new-option')?.addEventListener('click', () => {
  _runMode = 'new';
  localStorage.setItem(RUN_MODE_KEY, 'new');
  document.getElementById('run-dropdown-menu')?.classList.add('hidden');
  updateRunButtonState();
});

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
  if (!e.target.closest('#run-dropdown-toggle') && !e.target.closest('#run-dropdown-menu')) {
    document.getElementById('run-dropdown-menu')?.classList.add('hidden');
  }
});

let lastCheckedIdx = null;
let pendingShiftClick = null;
document.addEventListener('click', (e) => { if (e.target.classList.contains('row-checkbox') && e.shiftKey && lastCheckedIdx !== null) { pendingShiftClick = { idx: parseInt(e.target.dataset.rowId), checked: !e.target.checked }; } }, true);
document.addEventListener('change', (e) => {
  if (e.target.id === 'select-all-checkbox') { const visibleRows = getVisibleMainRows(); visibleRows.forEach(row => { const idx = parseInt(row.dataset.rowId); const cb = row.querySelector('.row-checkbox'); if (e.target.checked) { selectedIndices.add(idx); if (cb) cb.checked = true; } else { selectedIndices.delete(idx); if (cb) cb.checked = false; } }); updateSelectionUI(); }
  if (e.target.classList.contains('row-checkbox')) {
    const idx = parseInt(e.target.dataset.rowId);
    const shouldCheck = e.target.checked;
    if (pendingShiftClick && pendingShiftClick.idx === idx) { const visibleRows = getVisibleMainRows(); const visibleIndices = visibleRows.map(r => parseInt(r.dataset.rowId)); const lastPos = visibleIndices.indexOf(lastCheckedIdx); const currentPos = visibleIndices.indexOf(idx); if (lastPos !== -1 && currentPos !== -1) { const start = Math.min(lastPos, currentPos); const end = Math.max(lastPos, currentPos); for (let i = start; i <= end; i++) { const rowIdx = visibleIndices[i]; const row = visibleRows[i]; const cb = row.querySelector('.row-checkbox'); if (shouldCheck) { selectedIndices.add(rowIdx); if (cb) cb.checked = true; } else { selectedIndices.delete(rowIdx); if (cb) cb.checked = false; } } } pendingShiftClick = null; } else { if (shouldCheck) { selectedIndices.add(idx); } else { selectedIndices.delete(idx); } }
    lastCheckedIdx = idx;
    updateSelectionUI();
  }
});

let liveUpdateTimer = null;
function scheduleLiveRefresh() {
  if (liveUpdateTimer) { clearTimeout(liveUpdateTimer); liveUpdateTimer = null; }
  if (!hasRunningResults(_currentData)) return;
  liveUpdateTimer = setTimeout(async () => {
    try {
      const resp = await fetch('/results');
      if (!resp.ok) return;
      const data = await resp.json();
      // Update rows in place
      data.results.forEach((r, i) => {
        const oldResult = _currentData?.results?.[i]?.result;
        const newResult = r.result;
        // Only update if something changed
        if (JSON.stringify(oldResult) !== JSON.stringify(newResult)) {
          updateRowInPlace(i, newResult);
        }
      });
      // Re-apply column visibility to newly replaced rows
      applyColumnVisibility();
      // Update stats
      _currentData = data;
      updateStatsInPlace(data);
      checkRunningState();
      scheduleLiveRefresh();
    } catch (e) { console.error('Live refresh failed:', e); }
  }, 500);
}

function updateStatsInPlace(data) {
  const expandedPanel = document.getElementById('stats-expanded');
  const compactBar = document.getElementById('stats-compact');
  if (!expandedPanel || !compactBar) return;

  const stats = summarizeStats(data);
  const { chips, total, pctDone, progressCompleted, progressTotal } = stats;
  // Always recalculate latency from visible rows for accurate live updates
  const computedStats = computeFilteredStats();
  const avgLatency = computedStats ? computedStats.avgLatency : stats.avgLatency;

  updateChartBars(expandedPanel, chips);

  // Update test count
  const testMetric = expandedPanel.querySelector('.stats-metric-value');
  if (testMetric && testMetric.textContent !== String(total)) {
    testMetric.textContent = total;
  }

  // Update progress bar
  const progressFill = expandedPanel.querySelector('.stats-progress-fill');
  const progressText = expandedPanel.querySelector('.stats-progress-text');
  if (progressFill) progressFill.style.width = pctDone + '%';
  if (progressText) progressText.textContent = `${progressCompleted}/${progressTotal}`;

  updateLatencyDisplay(expandedPanel, avgLatency);

  // Update compact bar (simpler, just re-render)
  const wasExpanded = !expandedPanel.classList.contains('hidden');
  const temp = document.createElement('div');
  temp.innerHTML = renderStatsCompact(data);
  const newCompact = temp.querySelector('#stats-compact');
  if (wasExpanded) {
    newCompact.classList.add('hidden');
  } else {
    newCompact.classList.remove('hidden');
  }
  compactBar.replaceWith(newCompact);
  initStatsToggle();
}

function updateStatsForFilters() {
  const expandedPanel = document.getElementById('stats-expanded');
  const compactBar = document.getElementById('stats-compact');
  if (!expandedPanel || !compactBar || !_currentData) return;

  const hasFilters = isFilterActive();
  const filteredStats = hasFilters ? computeFilteredStats() : null;

  // Get original stats from _currentData
  const originalStats = summarizeStats(_currentData);
  const total = originalStats.total;

  // Use filtered stats if available, otherwise original
  const displayChips = filteredStats ? filteredStats.chips : originalStats.chips;
  const displayLatency = filteredStats ? filteredStats.avgLatency : originalStats.avgLatency;
  const filtered = filteredStats ? filteredStats.filtered : total;

  // Update test count with filtered/total format
  const testMetricContainer = expandedPanel.querySelector('.stats-metric');
  if (testMetricContainer) {
    const metricValue = testMetricContainer.querySelector('.stats-metric-value');
    if (metricValue) {
      const newContent = hasFilters
        ? `${filtered}<span class="stats-metric-divisor">/${total}</span>`
        : String(total);
      if (metricValue.innerHTML !== newContent) {
        metricValue.classList.add('updating');
        setTimeout(() => {
          metricValue.innerHTML = newContent;
          metricValue.classList.remove('updating');
        }, 100);
      }
    }
  }

  updateLatencyDisplay(expandedPanel, displayLatency, true);
  updateChartBars(expandedPanel, displayChips);

  // Update compact bar - re-render with filtered stats
  const wasExpanded = !expandedPanel.classList.contains('hidden');
  const compactData = {
    ..._currentData,
    total_evaluations: total,
    average_latency: displayLatency,
    score_chips: displayChips,
    _filtered: filtered,
    _hasFilters: hasFilters
  };
  const temp = document.createElement('div');
  temp.innerHTML = renderStatsCompact(compactData, hasFilters, filtered);
  const newCompact = temp.querySelector('#stats-compact');
  if (wasExpanded) {
    newCompact.classList.add('hidden');
  } else {
    newCompact.classList.remove('hidden');
  }
  compactBar.replaceWith(newCompact);
  initStatsToggle();
}

(function wireSettingsModal() {
  const modal = document.getElementById('settings-modal');
  const toggle = document.getElementById('settings-toggle');
  const close = document.getElementById('settings-close');
  const cancel = document.getElementById('settings-cancel');
  const backdrop = document.getElementById('settings-backdrop');
  const form = document.getElementById('settings-form');
  function openModal() { modal?.classList.remove('hidden'); loadConfig(); }
  function closeModal() { modal?.classList.add('hidden'); }
  async function loadConfig() { try { const resp = await fetch('/api/config'); const config = await resp.json(); form.querySelector('[name="concurrency"]').value = config.concurrency ?? ''; form.querySelector('[name="results_dir"]').value = config.results_dir ?? ''; form.querySelector('[name="timeout"]').value = config.timeout ?? ''; } catch (e) { console.error('Failed to load config:', e); } }
  async function saveConfig(e) { e.preventDefault(); const data = {}; const concurrency = parseInt(form.querySelector('[name="concurrency"]').value); if (!isNaN(concurrency)) data.concurrency = concurrency; const results_dir = form.querySelector('[name="results_dir"]').value.trim(); if (results_dir) data.results_dir = results_dir; const timeout = parseFloat(form.querySelector('[name="timeout"]').value); if (!isNaN(timeout)) data.timeout = timeout; try { const resp = await fetch('/api/config', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }); if (!resp.ok) throw new Error('Save failed'); closeModal(); } catch (e) { alert('Failed to save settings: ' + e.message); } }
  toggle?.addEventListener('click', openModal);
  close?.addEventListener('click', closeModal);
  cancel?.addEventListener('click', closeModal);
  backdrop?.addEventListener('click', closeModal);
  form?.addEventListener('submit', saveConfig);
})();

function restoreFiltersAndSearch() { const savedFilters = sessionStorage.getItem('ezvals:filters'); if (savedFilters) { try { _filters = JSON.parse(savedFilters); } catch {} } const savedSearch = sessionStorage.getItem('ezvals:search'); const searchEl = document.getElementById('search-input'); if (savedSearch && searchEl) { searchEl.value = savedSearch; } }

// Initial load
async function loadResults() {
  try {
    const resp = await fetch('/results');
    if (!resp.ok) throw new Error('Failed to load results');
    const data = await resp.json();
    renderResults(data);
  } catch (e) {
    console.error('Failed to load results:', e);
    document.getElementById('results').innerHTML = '<div class="p-4 text-theme-text-muted">Failed to load results. Please refresh the page.</div>';
  }
}
loadResults();

/* Stats panel expand/collapse */
function initStatsToggle() {
  const expandBtn = document.getElementById('stats-expand-btn');
  const collapseBtn = document.getElementById('stats-collapse-btn');
  const expandedPanel = document.getElementById('stats-expanded');
  const compactBar = document.getElementById('stats-compact');
  if (!expandBtn || !expandedPanel || !compactBar) return;

  expandBtn.addEventListener('click', () => {
    expandedPanel.classList.remove('hidden');
    compactBar.classList.add('hidden');
    localStorage.setItem(STATS_PREF_KEY, 'true');
  });

  collapseBtn?.addEventListener('click', () => {
    expandedPanel.classList.add('hidden');
    compactBar.classList.remove('hidden');
    localStorage.setItem(STATS_PREF_KEY, 'false');
  });

  // Restore state (expanded by default, collapse only if explicitly set to false)
  if (localStorage.getItem(STATS_PREF_KEY) === 'false') {
    expandedPanel.classList.add('hidden');
    compactBar.classList.remove('hidden');
  }
}
