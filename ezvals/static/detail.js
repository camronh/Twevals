const pathMatch = window.location.pathname.match(/\/runs\/([^/]+)\/results\/(\d+)/);
const runId = pathMatch ? pathMatch[1] : null;
const currentIndex = pathMatch ? parseInt(pathMatch[2]) : 0;

let dataPayloads = {};
let total = 0;
let evalPath = '';
let functionName = '';

function escapeHtml(str) {
  if (str == null) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function looksLikeMarkdown(text) {
  if (!text) return false;
  return [/^#{1,6}\s+\S/m, /^\s*[-*+]\s+\S/m, /^\s*\d+\.\s+\S/m, /^>+\s+\S/m, /`{3,}[\s\S]*?`{3,}/m, /\[.+?\]\(.+?\)/m].some(re => re.test(text));
}

function highlightWithin(container) {
  if (typeof hljs === 'undefined' || !container) return;
  container.querySelectorAll('pre code').forEach(code => hljs.highlightElement(code));
}

function highlightJson(rawText) {
  if (typeof hljs !== 'undefined') { try { return hljs.highlight(rawText, { language: 'json' }).value; } catch {} }
  return escapeHtml(rawText);
}

function renderDataViewer(targetId, content, options = {}) {
  const container = document.getElementById(targetId);
  if (!container) return;
  if (content === null || content === undefined || content === '') {
    container.innerHTML = `<div class="data-surface text-xs text-zinc-400">${options.placeholder || '—'}</div>`;
    container.dataset.raw = '';
    return;
  }
  let rawText, mode = 'text';
  if (typeof content === 'string') rawText = content;
  else if (typeof content === 'number' || typeof content === 'boolean') rawText = String(content);
  else { try { rawText = JSON.stringify(content, null, 2); mode = 'json'; } catch { rawText = String(content); } }
  const trimmed = rawText.trim();
  if (mode !== 'json' && trimmed) {
    try { JSON.parse(rawText); rawText = JSON.stringify(JSON.parse(rawText), null, 2); mode = 'json'; }
    catch { if (looksLikeMarkdown(trimmed)) mode = 'markdown'; }
  }
  container.dataset.mode = mode;
  if (mode === 'json') {
    container.innerHTML = `<div class="data-surface"><pre class="data-pre"><code class="hljs language-json">${highlightJson(rawText)}</code></pre></div>`;
    container.dataset.raw = rawText;
    return;
  }
  if (mode === 'markdown' && typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
    container.innerHTML = `<div class="data-surface markdown-body text-sm">${DOMPurify.sanitize(marked.parse(rawText))}</div>`;
    container.dataset.raw = rawText;
    highlightWithin(container);
    return;
  }
  container.innerHTML = `<div class="data-surface"><pre class="data-pre">${escapeHtml(rawText)}</pre></div>`;
  container.dataset.raw = rawText;
}

function navigateTo(idx) {
  if (idx >= 0 && idx < total) window.location.href = `/runs/${runId}/results/${idx}`;
}

function toggleCollapse(id) {
  document.getElementById(id + '-content')?.classList.toggle('open');
  document.getElementById(id + '-icon')?.classList.toggle('open');
}

function toggleMessagesPane() {
  const pane = document.getElementById('messages-pane');
  if (pane) pane.classList.toggle('translate-x-full');
}

function closeMessagesPane() {
  document.getElementById('messages-pane')?.classList.add('translate-x-full');
}

function renderMessages(messages) {
  const container = document.getElementById('data-messages');
  if (!container || !messages || !Array.isArray(messages)) return;
  container.dataset.raw = JSON.stringify(messages, null, 2);

  const isKnownSchema = messages.length > 0 && messages.every(msg =>
    (msg.role || msg.type) && (msg.content !== undefined || msg.text !== undefined || msg.message !== undefined || msg.tool_calls)
  );

  if (!isKnownSchema) {
    container.innerHTML = `<pre class="data-pre text-zinc-300 text-xs p-2">${escapeHtml(JSON.stringify(messages, null, 2))}</pre>`;
    return;
  }

  const html = messages.map(msg => {
    const role = (msg.role || msg.type || 'unknown').toLowerCase();
    let content = msg.content || msg.text || msg.message || '';

    if (msg.tool_calls && Array.isArray(msg.tool_calls)) {
      const toolCallsContent = msg.tool_calls.map(tc => {
        const fn = tc.function || tc;
        const name = fn.name || tc.name || 'tool';
        // Handle various tool call formats: fn.arguments, tc.args, tc.input
        let args = fn.arguments || tc.args || tc.input || {};
        let argsStr;
        if (typeof args === 'string') {
          // Try to parse and re-format stringified JSON
          try { argsStr = JSON.stringify(JSON.parse(args), null, 2); }
          catch { argsStr = args; }
        } else {
          argsStr = JSON.stringify(args, null, 2);
        }
        return `${name}(${argsStr})`;
      }).join('\n\n');
      return `<div class="msg-box msg-tool_calls">
        <div class="msg-box-header">Tool Calls</div>
        <div class="msg-box-content"><pre style="white-space: pre-wrap; margin: 0;">${escapeHtml(toolCallsContent)}</pre></div>
      </div>`;
    }

    if (role === 'tool' || role === 'tool_result' || role === 'function') {
      // Look up tool name from corresponding tool call by tool_call_id
      let toolName = msg.name;
      if (!toolName && msg.tool_call_id) {
        for (const m of messages) {
          if (m.tool_calls) {
            const tc = m.tool_calls.find(t => t.id === msg.tool_call_id);
            if (tc) {
              toolName = tc.function?.name || tc.name;
              break;
            }
          }
        }
      }
      toolName = toolName || 'tool';
      // Format content as JSON if possible
      if (typeof content === 'object') {
        content = JSON.stringify(content, null, 2);
      } else if (typeof content === 'string') {
        // Try JSON first
        try { content = JSON.stringify(JSON.parse(content), null, 2); }
        catch {
          // Try converting Python dict syntax to JSON (single quotes -> double quotes)
          try {
            const jsonified = content
              .replace(/'/g, '"')
              .replace(/True/g, 'true')
              .replace(/False/g, 'false')
              .replace(/None/g, 'null')
              .replace(/datetime\.date\([^)]+\)/g, '"[date]"')
              .replace(/datetime\.datetime\([^)]+\)/g, '"[datetime]"');
            content = JSON.stringify(JSON.parse(jsonified), null, 2);
          } catch { /* keep original */ }
        }
      }
      return `<div class="msg-box msg-tool_result">
        <div class="msg-box-header">${escapeHtml(toolName)} Result</div>
        <div class="msg-box-content"><pre style="white-space: pre-wrap; margin: 0;">${escapeHtml(String(content))}</pre></div>
      </div>`;
    }

    if (Array.isArray(content)) {
      content = content.map(c => typeof c === 'string' ? c : (c.text || c.content || JSON.stringify(c))).join('\n');
    }
    if (typeof content === 'object' && content !== null) {
      content = JSON.stringify(content, null, 2);
    }

    const normalizedRole = role === 'human' ? 'user' : role === 'ai' ? 'assistant' : role;
    const displayRole = normalizedRole.charAt(0).toUpperCase() + normalizedRole.slice(1);

    return `<div class="msg-box msg-${normalizedRole}">
      <div class="msg-box-header">${escapeHtml(displayRole)}</div>
      <div class="msg-box-content">${escapeHtml(String(content))}</div>
    </div>`;
  }).join('');

  container.innerHTML = html;
}

function initResizable() {
  const handles = document.querySelectorAll('.resize-handle-v, .resize-handle-h');
  handles.forEach(handle => {
    let startX, startY, startWidth, startHeight, target1, target2, isVertical;

    handle.addEventListener('mousedown', e => {
      e.preventDefault();
      isVertical = handle.classList.contains('resize-handle-h');
      handle.classList.add('dragging');
      document.body.classList.add('resizing');
      if (isVertical) document.body.classList.add('resizing-v');

      const resizeType = handle.dataset.resize;
      if (resizeType === 'input-output') {
        target1 = document.getElementById('input-panel');
        target2 = document.getElementById('output-panel');
        startX = e.clientX;
        startWidth = target1.offsetWidth;
      } else if (resizeType === 'main-sidebar') {
        target1 = document.getElementById('main-panel');
        target2 = document.getElementById('sidebar-panel');
        startX = e.clientX;
        startWidth = target2.offsetWidth;
      } else if (resizeType === 'io-ref') {
        target1 = document.getElementById('io-row');
        target2 = document.getElementById('ref-panel');
        startY = e.clientY;
        startHeight = target2.offsetHeight;
      }

      const onMouseMove = ev => {
        if (resizeType === 'input-output') {
          const delta = ev.clientX - startX;
          const parentWidth = target1.parentElement.offsetWidth - 5;
          const newWidth = Math.max(100, Math.min(parentWidth - 100, startWidth + delta));
          target1.style.width = newWidth + 'px';
        } else if (resizeType === 'main-sidebar') {
          const delta = startX - ev.clientX;
          const containerWidth = target1.parentElement.offsetWidth - 5;
          const newSidebarWidth = Math.max(200, Math.min(containerWidth - 300, startWidth + delta));
          target2.style.width = newSidebarWidth + 'px';
          target1.style.width = `calc(100% - ${newSidebarWidth}px)`;
        } else if (resizeType === 'io-ref') {
          const delta = startY - ev.clientY;
          const containerHeight = target1.parentElement.offsetHeight - 5;
          const newHeight = Math.max(60, Math.min(containerHeight - 100, startHeight + delta));
          target2.style.height = newHeight + 'px';
        }
      };

      const onMouseUp = () => {
        handle.classList.remove('dragging');
        document.body.classList.remove('resizing', 'resizing-v');
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        saveResizeSizes();
      };

      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    });
  });
}

function initMessagesPaneResize() {
  const handle = document.getElementById('messages-resize-handle');
  const pane = document.getElementById('messages-pane');
  if (!handle || !pane) return;

  let startX, startWidth;
  handle.addEventListener('mousedown', e => {
    e.preventDefault();
    startX = e.clientX;
    startWidth = pane.offsetWidth;
    document.body.style.cursor = 'ew-resize';
    document.body.style.userSelect = 'none';

    const onMouseMove = ev => {
      const delta = startX - ev.clientX;
      const newWidth = Math.max(300, Math.min(window.innerWidth - 100, startWidth + delta));
      pane.style.width = newWidth + 'px';
    };

    const onMouseUp = () => {
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      localStorage.setItem('ezvals:messagesPaneWidth', pane.style.width);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  });

  const savedWidth = localStorage.getItem('ezvals:messagesPaneWidth');
  if (savedWidth) pane.style.width = savedWidth;
}

function saveResizeSizes() {
  const sizes = {};
  const inputPanel = document.getElementById('input-panel');
  const sidebarPanel = document.getElementById('sidebar-panel');
  const refPanel = document.getElementById('ref-panel');
  if (inputPanel) sizes.inputWidth = inputPanel.style.width;
  if (sidebarPanel) sizes.sidebarWidth = sidebarPanel.style.width;
  if (refPanel) sizes.refHeight = refPanel.style.height;
  localStorage.setItem('ezvals:detailSizes', JSON.stringify(sizes));
}

function restoreResizeSizes() {
  try {
    const sizes = JSON.parse(localStorage.getItem('ezvals:detailSizes') || '{}');
    const inputPanel = document.getElementById('input-panel');
    const mainPanel = document.getElementById('main-panel');
    const sidebarPanel = document.getElementById('sidebar-panel');
    const refPanel = document.getElementById('ref-panel');
    if (sizes.inputWidth && inputPanel) inputPanel.style.width = sizes.inputWidth;
    if (sizes.sidebarWidth && sidebarPanel && mainPanel) {
      sidebarPanel.style.width = sizes.sidebarWidth;
      mainPanel.style.width = `calc(100% - ${sizes.sidebarWidth})`;
    }
    if (sizes.refHeight && refPanel) refPanel.style.height = sizes.refHeight;
  } catch {}
}

function initCopyButtons() {
  document.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', async e => {
      e.stopPropagation();
      const el = document.getElementById(btn.dataset.copy);
      if (!el) return;
      try {
        await navigator.clipboard.writeText(el.dataset?.raw ?? el.textContent);
        btn.querySelector('.copy-icon').classList.add('hidden');
        btn.querySelector('.check-icon').classList.remove('hidden');
        setTimeout(() => { btn.querySelector('.copy-icon').classList.remove('hidden'); btn.querySelector('.check-icon').classList.add('hidden'); }, 1500);
      } catch {}
    });
  });

  document.getElementById('copy-cmd-btn')?.addEventListener('click', async () => {
    const cmd = evalPath ? `ezvals run ${evalPath}::${functionName}` : `ezvals run ${functionName || ''}`.trim();
    try {
      await navigator.clipboard.writeText(cmd);
      const btn = document.getElementById('copy-cmd-btn');
      btn.querySelector('.copy-icon').classList.add('hidden');
      btn.querySelector('.check-icon').classList.remove('hidden');
      setTimeout(() => { btn.querySelector('.copy-icon').classList.remove('hidden'); btn.querySelector('.check-icon').classList.add('hidden'); }, 1500);
    } catch {}
  });
}

function render(data) {
  const r = data.result;
  const result = r.result || {};
  functionName = r.function;
  evalPath = data.eval_path || '';
  total = data.total;

  const status = result.status || 'completed';
  const hasReference = result.reference != null && result.reference !== '—';
  const hasMetadata = result.metadata != null && result.metadata !== '—';
  const hasTraceData = result.trace_data != null;
  const hasMessages = hasTraceData && result.trace_data.messages && result.trace_data.messages.length > 0;
  const hasScores = result.scores && result.scores.length > 0;
  const hasError = result.error != null;

  dataPayloads = {
    input: result.input,
    output: result.output,
    reference: hasReference ? result.reference : null,
    metadata: hasMetadata ? result.metadata : null,
    trace: hasTraceData ? result.trace_data : null,
    messages: hasMessages ? result.trace_data.messages : null
  };

  const pillTones = {
    'pending': 'text-blue-600 bg-blue-500/10 border border-blue-500/30 dark:text-blue-400',
    'running': 'text-cyan-600 bg-cyan-500/10 border border-cyan-500/30 dark:text-cyan-400 animate-pulse',
    'completed': 'text-emerald-600 bg-emerald-500/10 border border-emerald-500/30 dark:text-emerald-400',
    'error': 'text-rose-600 bg-rose-500/10 border border-rose-500/30 dark:text-rose-400',
    'cancelled': 'text-amber-600 bg-amber-500/10 border border-amber-500/30 dark:text-amber-400'
  };

  const copyBtnHtml = `
    <svg class="copy-icon h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
    <svg class="check-icon hidden h-3.5 w-3.5 text-emerald-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>`;

  let scoresHtml = '';
  if (hasScores) {
    scoresHtml = result.scores.map(s => {
      let cls = 'border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-800/50';
      let textCls = 'text-zinc-700 dark:text-zinc-300';
      let valueCls = 'text-zinc-500';
      if (s.passed === true) {
        cls = 'border-emerald-200 bg-emerald-50 dark:border-emerald-500/30 dark:bg-emerald-500/10';
        textCls = 'text-emerald-700 dark:text-emerald-300';
        valueCls = 'text-emerald-600 dark:text-emerald-400';
      } else if (s.passed === false) {
        cls = 'border-rose-200 bg-rose-50 dark:border-rose-500/30 dark:bg-rose-500/10';
        textCls = 'text-rose-700 dark:text-rose-300';
        valueCls = 'text-rose-600 dark:text-rose-400';
      }
      let passedIcon = '';
      if (s.passed === true) passedIcon = `<span class="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500 text-white"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6L9 17l-5-5"/></svg></span>`;
      else if (s.passed === false) passedIcon = `<span class="flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-white"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M18 6L6 18M6 6l12 12"/></svg></span>`;

      return `<div class="rounded border px-2.5 py-1.5 ${cls}">
        <div class="flex items-center justify-between gap-2">
          <span class="font-mono text-xs font-medium ${textCls}">${escapeHtml(s.key)}</span>
          <div class="flex items-center gap-1.5">
            ${s.value != null ? `<span class="font-mono text-xs ${valueCls}">${s.value}</span>` : ''}
            ${passedIcon}
          </div>
        </div>
        ${s.notes ? `<div class="mt-1 text-[11px] ${valueCls}">${escapeHtml(s.notes)}</div>` : ''}
      </div>`;
    }).join('');
  }

  let filteredTrace = null;
  if (hasTraceData) {
    filteredTrace = Object.fromEntries(
      Object.entries(result.trace_data).filter(([k]) => k !== 'messages' && k !== 'trace_url')
    );
    if (Object.keys(filteredTrace).length === 0) filteredTrace = null;
  }

  const latencyColor = result.latency != null
    ? (result.latency <= 1 ? 'text-emerald-600 dark:text-emerald-400' : result.latency <= 5 ? 'text-blue-600 dark:text-blue-400' : 'text-amber-600 dark:text-amber-400')
    : '';

  document.getElementById('app').innerHTML = `
    <header class="flex-shrink-0 flex items-center justify-between gap-4 border-b border-blue-200/60 bg-white px-4 py-2 dark:border-zinc-800 dark:bg-zinc-900">
      <div class="flex items-center gap-3 min-w-0">
        <a href="/" class="flex h-7 w-7 items-center justify-center rounded border border-zinc-200 text-zinc-500 hover:border-blue-300 hover:text-blue-600 dark:border-zinc-700 dark:hover:border-blue-500 dark:hover:text-blue-400" title="Back (Esc)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
        </a>
        <div class="flex items-center gap-2 text-sm min-w-0">
          <span class="font-mono font-semibold text-zinc-900 dark:text-zinc-100 truncate">${escapeHtml(functionName)}</span>
          <button id="copy-cmd-btn" class="copy-btn flex h-6 w-6 items-center justify-center rounded text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800" title="Copy run command">
            ${copyBtnHtml}
          </button>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button id="rerun-btn" class="flex h-7 items-center gap-1.5 rounded border border-emerald-500/30 bg-emerald-500/10 px-2.5 text-xs font-medium text-emerald-400 hover:bg-emerald-500/20 hover:text-emerald-300" title="Rerun this evaluation">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/></svg>
          Rerun
        </button>
        <span class="text-xs text-zinc-500">${currentIndex + 1}/${total}</span>
        <button id="prev-btn" class="flex h-7 w-7 items-center justify-center rounded border border-zinc-200 text-zinc-500 hover:border-blue-300 hover:text-blue-600 disabled:opacity-40 dark:border-zinc-700 dark:hover:border-blue-500" title="Up" ${currentIndex <= 0 ? 'disabled' : ''}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 15l-6-6-6 6"/></svg>
        </button>
        <button id="next-btn" class="flex h-7 w-7 items-center justify-center rounded border border-zinc-200 text-zinc-500 hover:border-blue-300 hover:text-blue-600 disabled:opacity-40 dark:border-zinc-700 dark:hover:border-blue-500" title="Down" ${currentIndex >= total - 1 ? 'disabled' : ''}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
        </button>
      </div>
    </header>

    ${hasError ? `
    <div class="flex-shrink-0 bg-rose-50 border-b border-rose-200 px-4 py-2 dark:bg-rose-500/10 dark:border-rose-500/30">
      <div class="flex items-start gap-2 text-sm">
        <svg class="mt-0.5 shrink-0 text-rose-500" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <pre id="data-error" class="flex-1 text-rose-600 dark:text-rose-300 whitespace-pre-wrap font-mono text-xs">${escapeHtml(result.error)}</pre>
        <button class="copy-btn shrink-0 text-rose-400 hover:text-rose-600" data-copy="data-error" title="Copy">${copyBtnHtml}</button>
      </div>
    </div>` : ''}

    <div class="flex-1 flex min-h-0 overflow-hidden">
      <div id="main-panel" class="flex flex-col min-w-0" style="width: calc(100% - 320px);">
        <div id="io-row" class="flex min-h-0" style="flex: 1 1 auto;">
          <div id="input-panel" class="flex flex-col min-w-0" style="width: 50%;">
            <div class="data-panel-header flex items-center justify-between border-b border-blue-100 bg-blue-50/50 px-3 py-1.5 dark:border-zinc-800/60 dark:bg-zinc-900/50">
              <span class="text-[10px] font-semibold uppercase tracking-wider text-blue-600 dark:text-blue-400">Input</span>
              <button class="copy-btn text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300" data-copy="data-input" title="Copy">${copyBtnHtml}</button>
            </div>
            <div class="data-panel-body p-3 bg-white dark:bg-zinc-900/30">
              <div id="data-input" class="data-viewer"></div>
            </div>
          </div>

          <div class="resize-handle-v" data-resize="input-output"></div>

          <div id="output-panel" class="flex flex-col min-w-0" style="flex: 1;">
            <div class="data-panel-header flex items-center justify-between border-b border-blue-100 bg-emerald-50/50 px-3 py-1.5 dark:border-zinc-800/60 dark:bg-zinc-900/50">
              <span class="text-[10px] font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">Output</span>
              <button class="copy-btn text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300" data-copy="data-output" title="Copy">${copyBtnHtml}</button>
            </div>
            <div class="data-panel-body p-3 bg-white dark:bg-zinc-900/30">
              <div id="data-output" class="data-viewer"></div>
            </div>
          </div>
        </div>

        ${hasReference ? `
        <div class="resize-handle-h" data-resize="io-ref"></div>
        <div id="ref-panel" class="flex flex-col flex-shrink-0" style="height: 150px; min-height: 60px;">
          <div class="data-panel-header flex items-center justify-between border-b border-amber-200/40 bg-amber-50/50 px-3 py-1.5 dark:border-amber-500/10 dark:bg-amber-500/5">
            <span class="text-[10px] font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">Reference</span>
            <button class="copy-btn text-amber-500 hover:text-amber-700 dark:hover:text-amber-300" data-copy="data-ref" title="Copy">${copyBtnHtml}</button>
          </div>
          <div class="data-panel-body p-3 overflow-auto bg-amber-50/30 dark:bg-amber-500/5">
            <div id="data-ref" class="data-viewer"></div>
          </div>
        </div>` : ''}
      </div>

      <div class="resize-handle-v" data-resize="main-sidebar"></div>

      <div id="sidebar-panel" class="flex flex-col min-h-0 overflow-auto bg-zinc-50 dark:bg-zinc-900/50" style="width: 320px; min-width: 200px;">
        <div class="border-b border-blue-200/60 dark:border-zinc-800 p-3 space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">Status</span>
            <span class="rounded px-1.5 py-0.5 text-[10px] font-medium ${pillTones[status] || pillTones['completed']}">${status}</span>
          </div>
          ${result.latency != null ? `
          <div class="flex items-center justify-between">
            <span class="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">Latency</span>
            <span class="font-mono text-xs ${latencyColor}">${result.latency.toFixed(2)}s</span>
          </div>` : ''}
          ${r.dataset ? `
          <div class="flex items-center justify-between">
            <span class="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">Dataset</span>
            <span class="text-xs text-zinc-600 dark:text-zinc-300">${escapeHtml(r.dataset)}</span>
          </div>` : ''}
          ${r.labels && r.labels.length ? `
          <div class="flex items-center justify-between">
            <span class="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">Labels</span>
            <div class="flex gap-1">${r.labels.map(la => `<span class="rounded bg-zinc-200 px-1.5 py-0.5 text-[10px] text-zinc-600 dark:bg-zinc-700 dark:text-zinc-300">${escapeHtml(la)}</span>`).join('')}</div>
          </div>` : ''}
          ${hasTraceData && result.trace_data.trace_url ? `
          <div class="flex items-center justify-between">
            <span class="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">Trace</span>
            <a href="${escapeHtml(result.trace_data.trace_url)}" target="_blank" class="flex items-center gap-1.5 rounded border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-xs font-medium text-cyan-400 hover:bg-cyan-500/20 hover:text-cyan-300">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              View Trace
            </a>
          </div>` : ''}
        </div>

        ${hasMessages ? `
        <div class="border-b border-blue-200/60 dark:border-zinc-800">
          <button onclick="toggleMessagesPane()" class="w-full flex items-center justify-between px-3 py-2 bg-zinc-100/50 hover:bg-zinc-100 dark:bg-zinc-800/30 dark:hover:bg-zinc-800/50 text-left">
            <span class="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Messages</span>
            <span class="flex items-center gap-1.5">
              <span class="rounded-full bg-zinc-200 px-1.5 py-0.5 text-[10px] font-medium text-zinc-600 dark:bg-zinc-600 dark:text-zinc-200">${result.trace_data.messages.length}</span>
              <svg class="h-3.5 w-3.5 text-zinc-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
            </span>
          </button>
        </div>` : ''}

        ${hasScores ? `
        <div class="border-b border-blue-200/60 dark:border-zinc-800">
          <div class="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-500 bg-zinc-100/50 dark:bg-zinc-800/30">Scores</div>
          <div class="p-2 space-y-1.5">${scoresHtml}</div>
        </div>` : ''}

        ${hasMetadata ? `
        <div class="border-b border-blue-200/60 dark:border-zinc-800">
          <div role="button" tabindex="0" onclick="toggleCollapse('metadata')" onkeydown="if(event.key==='Enter')toggleCollapse('metadata')" class="flex cursor-pointer items-center justify-between px-3 py-2 bg-zinc-100/50 hover:bg-zinc-100 dark:bg-zinc-800/30 dark:hover:bg-zinc-800/50">
            <span class="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Metadata</span>
            <svg id="metadata-icon" class="collapse-icon open h-3.5 w-3.5 text-zinc-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
          </div>
          <div id="metadata-content" class="collapsible-content open">
            <div>
              <div class="p-2 max-h-40 overflow-auto">
                <div id="data-meta" class="data-viewer"></div>
              </div>
            </div>
          </div>
        </div>` : ''}

        ${filteredTrace ? `
        <div class="border-b border-blue-200/60 dark:border-zinc-800">
          <div role="button" tabindex="0" onclick="toggleCollapse('trace-data')" onkeydown="if(event.key==='Enter')toggleCollapse('trace-data')" class="flex cursor-pointer items-center justify-between px-3 py-2 bg-zinc-100/50 hover:bg-zinc-100 dark:bg-zinc-800/30 dark:hover:bg-zinc-800/50">
            <span class="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Trace Data</span>
            <svg id="trace-data-icon" class="collapse-icon open h-3.5 w-3.5 text-zinc-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
          </div>
          <div id="trace-data-content" class="collapsible-content open">
            <div>
              <div class="p-2 max-h-48 overflow-auto">
                <div id="data-trace" class="data-viewer"></div>
              </div>
            </div>
          </div>
        </div>` : ''}

        <div class="flex-1">
          <div class="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-500 bg-zinc-100/50 dark:bg-zinc-800/30">Annotation</div>
          <div class="p-3">
            ${result.annotation ? `<div class="whitespace-pre-wrap text-xs text-zinc-700 dark:text-zinc-300">${escapeHtml(result.annotation)}</div>` : `<div class="text-xs italic text-zinc-400 dark:text-zinc-500">No annotation</div>`}
          </div>
        </div>

        <div class="flex-shrink-0 px-3 py-2 border-t border-blue-200/60 bg-zinc-100/30 dark:border-zinc-800 dark:bg-zinc-800/20">
          <div class="flex items-center gap-4 text-[10px] text-zinc-400">
            <span><kbd class="rounded border border-zinc-300 bg-white px-1 font-mono dark:border-zinc-600 dark:bg-zinc-800">↑↓</kbd> nav</span>
            <span><kbd class="rounded border border-zinc-300 bg-white px-1 font-mono dark:border-zinc-600 dark:bg-zinc-800">Esc</kbd> back</span>
          </div>
        </div>
      </div>
    </div>

    ${hasMessages ? `
    <div id="messages-pane" class="fixed top-0 right-0 bottom-0 z-50 translate-x-full border-l border-zinc-200 bg-white shadow-xl transition-transform duration-200 dark:border-zinc-700 dark:bg-zinc-900" style="width: 700px;">
      <div id="messages-resize-handle" class="absolute left-0 top-0 bottom-0 w-1 cursor-ew-resize hover:bg-blue-500/50 active:bg-blue-500/70"></div>
      <div class="flex items-center justify-between border-b border-zinc-200 px-3 py-2 dark:border-zinc-700">
        <span class="text-sm font-medium text-zinc-700 dark:text-zinc-200">Messages <span class="text-zinc-400">(${result.trace_data.messages.length})</span></span>
        <button onclick="toggleMessagesPane()" class="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800">
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
        </button>
      </div>
      <div class="h-[calc(100%-41px)] overflow-auto">
        <div id="data-messages" class="space-y-1 p-2"></div>
      </div>
    </div>` : ''}
  `;

  // Initialize after DOM is ready
  if (typeof marked !== 'undefined') marked.setOptions({ breaks: true, gfm: true });
  renderDataViewer('data-input', dataPayloads.input);
  renderDataViewer('data-output', dataPayloads.output, { placeholder: '—' });
  if (dataPayloads.reference !== null) renderDataViewer('data-ref', dataPayloads.reference);
  if (dataPayloads.metadata !== null) renderDataViewer('data-meta', dataPayloads.metadata);
  if (filteredTrace) renderDataViewer('data-trace', filteredTrace);
  if (dataPayloads.messages !== null) renderMessages(dataPayloads.messages);

  initResizable();
  restoreResizeSizes();
  initMessagesPaneResize();
  initCopyButtons();

  document.getElementById('prev-btn')?.addEventListener('click', () => navigateTo(currentIndex - 1));
  document.getElementById('next-btn')?.addEventListener('click', () => navigateTo(currentIndex + 1));

  // Rerun button (#6)
  document.getElementById('rerun-btn')?.addEventListener('click', async () => {
    const btn = document.getElementById('rerun-btn');
    if (!btn || btn.disabled) return;
    btn.disabled = true;
    btn.innerHTML = '<svg class="animate-spin h-3 w-3" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/></svg> Running...';
    try {
      const resp = await fetch('/api/runs/rerun', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ indices: [currentIndex] })
      });
      if (resp.ok) {
        // Poll until this eval completes
        const pollForCompletion = async () => {
          const r = await fetch(`/api${window.location.pathname}`);
          if (r.ok) {
            const data = await r.json();
            const status = data.result?.result?.status;
            if (status === 'completed' || status === 'error') {
              render(data);
              return;
            }
          }
          setTimeout(pollForCompletion, 500);
        };
        setTimeout(pollForCompletion, 500);
      }
    } catch (e) {
      console.error('Rerun failed:', e);
      btn.disabled = false;
      btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/></svg> Rerun';
    }
  });
}

async function loadDetail() {
  try {
    const resp = await fetch(`/api${window.location.pathname}`);
    if (!resp.ok) throw new Error('Not found');
    const data = await resp.json();
    render(data);
  } catch (e) {
    document.getElementById('app').innerHTML = '<div class="flex-1 flex items-center justify-center text-rose-500">Failed to load result</div>';
  }
}

// Click outside messages pane to close it (#16)
document.addEventListener('click', e => {
  const pane = document.getElementById('messages-pane');
  if (!pane || pane.classList.contains('translate-x-full')) return;
  // Don't close if clicking inside the pane or on the toggle button
  if (pane.contains(e.target)) return;
  if (e.target.closest('[onclick*="toggleMessagesPane"]') || e.target.closest('button[onclick*="Messages"]')) return;
  closeMessagesPane();
});

document.addEventListener('keydown', e => {
  if (e.target.matches('input, textarea, select')) return;
  if (e.key === 'ArrowUp') { e.preventDefault(); navigateTo(currentIndex - 1); }
  else if (e.key === 'ArrowDown') { e.preventDefault(); navigateTo(currentIndex + 1); }
  else if (e.key === 'Escape') {
    const pane = document.getElementById('messages-pane');
    if (pane && !pane.classList.contains('translate-x-full')) { closeMessagesPane(); }
    else { window.location.href = '/'; }
  }
});

loadDetail();
