"use strict";

const SAMPLES = {
  valid: `{
  "name": "JSONLint+",
  "version": "1.0.0",
  "enabled": true,
  "port": 8080,
  "tags": ["json", "compiler"],
  "metadata": null
}`,
  trailingComma: `{
  "name": "JSONLint+",
  "port": 8080,
}`,
  unterminated: `{
  "name": "JSONLint+,
  "port": 8080
}`,
  badNumber: `{
  "port": 01,
  "ratio": 1.2.3
}`,
  badChar: `{
  "name": "JSONLint+",
  "flag": @true
}`,
};

const TOKEN_CLASS = {
  LBRACE: "tok-punct", RBRACE: "tok-punct",
  LBRACKET: "tok-punct", RBRACKET: "tok-punct",
  COLON: "tok-punct", COMMA: "tok-punct",
  STRING: "tok-string", NUMBER: "tok-number",
  TRUE: "tok-keyword", FALSE: "tok-keyword", NULL: "tok-keyword",
  EOF: "tok-eof",
};

const $ = (sel) => document.querySelector(sel);

const editor = $("#editor");
const stat = $("#stat");
const timeline = $("#timeline");
const summary = $("#summary");
const verdict = $("#verdict");
const diagnosticsBox = $("#diagnostics");
const diagCount = $("#diag-count");
const tokensBody = $("#tokens-body");
const astTree = $("#ast-tree");
const diffBox = $("#diff");
const rawBox = $("#raw");
const runBtn = $("#run");
const runtime = $("#runtime");

let lastReport = null;
let lastApplied = null;
let requestId = 0;

function updateStat() {
  const text = editor.value;
  const lines = text.length ? text.split("\n").length : 0;
  stat.textContent = `${lines} lines \u00b7 ${text.length} chars`;
}

function setEditor(text) {
  editor.value = text;
  updateStat();
  markInputChanged();
}

function markInputChanged() {
  if (lastReport && editor.value !== lastReport.source) {
    astTree.replaceChildren();
    const message = document.createElement("p");
    message.className = "empty";
    message.textContent = "Input changed. Run JSONLint+ again to update the tree.";
    astTree.appendChild(message);
    diagnosticsBox.querySelectorAll("[data-fix-index]").forEach(button => { button.disabled = true; });
  }
}

editor.addEventListener("input", () => {
  lastApplied = null;
  updateStat();
  markInputChanged();
});
editor.addEventListener("keydown", (event) => {
  if (event.key === "Tab") {
    event.preventDefault();
    const start = editor.selectionStart;
    const end = editor.selectionEnd;
    lastApplied = null;
    editor.value = editor.value.slice(0, start) + "  " + editor.value.slice(end);
    editor.selectionStart = editor.selectionEnd = start + 2;
    updateStat();
    markInputChanged();
  }
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    run();
  }
});

document.querySelectorAll("[data-sample]").forEach((btn) => {
  btn.addEventListener("click", () => {
    lastApplied = null;
    setEditor(SAMPLES[btn.dataset.sample] ?? "");
    run();
  });
});

$("#clear").addEventListener("click", () => {
  lastApplied = null;
  setEditor("");
  editor.focus();
});

runBtn.addEventListener("click", run);

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    $(`.tab-panel[data-panel="${tab.dataset.tab}"]`).classList.add("active");
  });
});

async function run() {
  runBtn.disabled = true;
  runBtn.innerHTML = '<span class="spinner"></span> Running\u2026';
  const started = performance.now();
  const currentRequest = ++requestId;
  const source = editor.value;
  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "text/plain; charset=utf-8" },
      body: source,
    });
    const report = await response.json();
    if (!response.ok) throw new Error(report.error || `HTTP ${response.status}`);
    if (currentRequest !== requestId || editor.value !== source) return;
    render(report);
  } catch (err) {
    if (currentRequest === requestId) verdict.innerHTML = `<div class="box bad">Could not reach the server: ${escapeHtml(String(err))}</div>`;
  } finally {
    const elapsed = performance.now() - started;
    runtime.textContent = `${elapsed.toFixed(1)} ms round-trip`;
    if (currentRequest === requestId) { runBtn.disabled = false; runBtn.innerHTML = "&#9654; Run JSONLint+"; }
  }
}

function render(report) {
  lastReport = report;
  $("#chip-python").textContent = `python: ${report.python_version ?? "?"}`;
  $("#chip-version").textContent = `jsonlint-plus: ${report.package_version ?? "?"}`;

  renderTimeline(report);
  renderSummary(report);
  renderVerdict(report);
  renderTokens(report);
  renderAst(report);
  renderDiagnostics(report);
  renderOutput(report);
  rawBox.textContent = JSON.stringify(report, null, 2);
}

function renderTimeline(report) {
  timeline.innerHTML = "";
  for (const stage of report.stages ?? []) {
    const li = document.createElement("li");
    li.className = stage.status ?? "neutral";
    const detail = stageDetail(stage);
    li.innerHTML = `
      <div class="stage-top">
        <span class="stage-name">${escapeHtml(stage.name)}</span>
        <span class="stage-time">${(stage.duration_ms ?? 0).toFixed(2)} ms</span>
      </div>
      <div class="stage-detail ${stage.status === "error" ? "err" : ""}">${detail}</div>`;
    timeline.appendChild(li);
  }
}

function stageDetail(stage) {
  if (stage.status === "ok") {
    if (stage.id === "lexer") return `Produced ${stage.token_count} tokens.`;
    if (stage.id === "repair") {
      const count = stage.suggestion_count ?? 0;
      return count === 1 ? "1 suggested fix available." : `${count} suggested fixes available.`;
    }
    return "Completed successfully.";
  }
  if (stage.status === "error") {
    const e = stage.error ?? {};
    const loc = e.line != null ? ` (line ${e.line}, col ${e.column ?? "?"})` : "";
    return `Failed: ${escapeHtml(e.message ?? "error")}${loc}`;
  }
  if (stage.status === "blocked") return escapeHtml(stage.message ?? "Skipped.");
  if (stage.status === "missing") return escapeHtml(stage.message ?? "Not implemented yet.");
  return "";
}

function reportSource() {
  return lastReport?.source;
}

function renderSummary(report) {
  const stages = report.stages ?? [];
  const okCount = stages.filter((s) => s.status === "ok").length;
  const errCount = stages.filter((s) => s.status === "error").length;
  const missingCount = stages.filter((s) => s.status === "missing").length;
  const tokens = stages.find((s) => s.id === "lexer")?.token_count;

  summary.innerHTML = `
    <span class="pill neutral">${stages.length} stages</span>
    <span class="pill ok">${okCount} ok</span>
    ${errCount ? `<span class="pill bad">${errCount} failed</span>` : ""}
    ${missingCount ? `<span class="pill warn">${missingCount} not implemented</span>` : ""}
    ${tokens != null ? `<span class="pill neutral">${tokens} tokens</span>` : ""}`;
}

function renderVerdict(report) {
  const errors = (report.diagnostics ?? []).length;
  if (errors === 0) {
    verdict.innerHTML = `<div class="box ok">All active stages completed without syntax errors.</div>`;
  } else {
    const fixCount = report.diagnostics.filter(item => item.fix).length;
    verdict.innerHTML = `<div class="box bad">${errors} diagnostic${errors > 1 ? "s" : ""} reported.${fixCount ? ` <button class="verdict-link" type="button">View ${fixCount} suggested fix${fixCount > 1 ? "es" : ""}</button>` : ""}</div>`;
    verdict.querySelector(".verdict-link")?.addEventListener("click", () => {
      document.querySelector('[data-tab="diagnostics"]').click();
      diagnosticsBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  }
}

function renderTokens(report) {
  const lexer = (report.stages ?? []).find((s) => s.id === "lexer");
  tokensBody.innerHTML = "";
  const tokens = lexer?.tokens ?? [];
  if (lexer?.status !== "ok" || tokens.length === 0) {
    const message = lexer?.status === "error"
      ? "Lexing failed before any token could be produced."
      : "No tokens.";
    tokensBody.innerHTML = `<tr><td colspan="5" class="empty">${escapeHtml(message)}</td></tr>`;
    return;
  }
  tokens.forEach((tok, index) => {
    const tr = document.createElement("tr");
    const cls = TOKEN_CLASS[tok.type] ?? "tok-value";
    const value = tok.type === "EOF" ? "\u25a0 end of input" : tok.value;
    tr.innerHTML = `
      <td class="tok-value">${index}</td>
      <td><span class="tok-type ${cls}">${escapeHtml(tok.type)}</span></td>
      <td class="${cls}">${escapeHtml(String(value))}</td>
      <td class="tok-value">${tok.line}</td>
      <td class="tok-value">${tok.column}</td>`;
    tokensBody.appendChild(tr);
  });
}

function renderAst(report) {
  astTree.replaceChildren();
  const stage = (report.stages ?? []).find((item) => item.id === "parser");
  if (!stage || stage.status !== "ok" || !stage.ast) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "The tree is available after the JSON is valid. Check Diagnostics and run again.";
    astTree.appendChild(empty);
    return;
  }

  function nodeView(node, depth = 0) {
    const branch = document.createElement("li");
    const children = node.children ?? [];
    const row = document.createElement("div");
    row.className = "ast-row";
    if (children.length) {
      const toggle = document.createElement("button");
      toggle.className = "ast-toggle";
      toggle.type = "button";
      toggle.textContent = "\u25be";
      toggle.setAttribute("aria-label", "Collapse " + node.type);
      toggle.setAttribute("aria-expanded", "true");
      toggle.addEventListener("click", () => setExpanded(branch, toggle.getAttribute("aria-expanded") !== "true"));
      row.appendChild(toggle);
    } else {
      const spacer = document.createElement("span");
      spacer.className = "ast-toggle-spacer";
      row.appendChild(spacer);
    }
    const select = document.createElement("button");
    select.type = "button";
    select.className = "ast-node";
    const type = document.createElement("span");
    type.className = "ast-type ast-type-" + node.type;
    type.textContent = node.type;
    select.appendChild(type);
    if (node.type === "property") {
      const key = document.createElement("span");
      key.className = "ast-key";
      key.textContent = JSON.stringify(node.key);
      select.appendChild(key);
    } else if (Object.hasOwn(node, "value")) {
      const value = document.createElement("span");
      value.className = "ast-value";
      value.textContent = JSON.stringify(node.value);
      select.appendChild(value);
    } else if (node.type === "object" || node.type === "array") {
      const count = document.createElement("span");
      count.className = "ast-count";
      count.textContent = children.length + (children.length === 1 ? " child" : " children");
      select.appendChild(count);
    }
    const location = document.createElement("span");
    location.className = "ast-location";
    location.textContent = "L" + node.line + ":" + node.column;
    select.appendChild(location);
    select.title = "Go to line " + node.line + ", column " + node.column;
    select.addEventListener("click", () => {
      const lines = editor.value.split("\n");
      const before = lines.slice(0, node.line - 1).reduce((total, line) => total + line.length + 1, 0);
      const offset = before + Array.from(lines[node.line - 1] ?? "").slice(0, node.column - 1).join("").length;
      editor.focus();
      editor.setSelectionRange(offset, offset);
      editor.scrollTop = Math.max(0, (node.line - 2) * parseFloat(getComputedStyle(editor).lineHeight));
    });
    row.appendChild(select);
    branch.appendChild(row);
    if (children.length) {
      const list = document.createElement("ul");
      list.className = "ast-children";
      for (const child of children) list.appendChild(nodeView(child, depth + 1));
      branch.appendChild(list);
    }
    return branch;
  }

  const root = document.createElement("ul");
  root.className = "ast-root";
  root.appendChild(nodeView(stage.ast));
  astTree.appendChild(root);
}

function setExpanded(branch, expanded) {
  const toggle = branch.querySelector(":scope > .ast-row > .ast-toggle");
  const children = branch.querySelector(":scope > .ast-children");
  if (!toggle || !children) return;
  children.hidden = !expanded;
  toggle.textContent = expanded ? "\u25be" : "\u25b8";
  toggle.setAttribute("aria-expanded", String(expanded));
  toggle.setAttribute("aria-label", (expanded ? "Collapse " : "Expand ") + branch.querySelector(":scope > .ast-row .ast-type").textContent);
}

$("#ast-expand").addEventListener("click", () => astTree.querySelectorAll("li").forEach((branch) => setExpanded(branch, true)));
$("#ast-collapse").addEventListener("click", () => astTree.querySelectorAll("li").forEach((branch) => setExpanded(branch, false)));

function renderDiagnostics(report) {
  const list = report.diagnostics ?? [];
  diagCount.textContent = String(list.length);
  diagnosticsBox.replaceChildren();
  if (list.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No diagnostics.";
    diagnosticsBox.appendChild(empty);
    return;
  }
  list.forEach((diagnostic, index) => {
    const item = document.createElement("div");
    item.className = "diag";
    const heading = document.createElement("div");
    heading.className = "diag-title";
    heading.textContent = diagnostic.type ?? "Error";
    if (diagnostic.line != null) {
      const location = document.createElement("span");
      location.className = "diag-loc";
      location.textContent = `line ${diagnostic.line}, col ${diagnostic.column ?? "?"}`;
      heading.appendChild(location);
    }
    const message = document.createElement("p");
    message.className = "diag-desc";
    message.textContent = diagnostic.message;
    item.append(heading, message);
    if (diagnostic.fix) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "apply-fix";
      button.dataset.fixIndex = String(index);
      button.textContent = `Apply fix: ${diagnostic.fix.title}`;
      button.addEventListener("click", () => applyFix(report, diagnostic.fix));
      item.appendChild(button);
    } else {
      const note = document.createElement("p");
      note.className = "diag-no-fix";
      note.textContent = "No automatic fix available for this error.";
      item.appendChild(note);
    }
    diagnosticsBox.appendChild(item);
  });
}

function applyFix(report, fix) {
  if (editor.value !== report.source) {
    markInputChanged();
    return;
  }
  // Python offsets count Unicode code points; JavaScript strings use UTF-16.
  const characters = Array.from(report.source);
  const after = characters.slice(0, fix.start).join("") + fix.text + characters.slice(fix.end).join("");
  lastApplied = { before: report.source, after };
  setEditor(after);
  run();
}

function renderOutput(report) {
  const applied = lastApplied && lastApplied.after === report.source ? lastApplied : null;
  const before = applied?.before ?? report.source ?? "";
  const repaired = applied?.after ?? null;

  if (repaired == null) {
    diffBox.innerHTML = `
      <div style="grid-column:1/-1" class="note">
        <b>No fix applied yet.</b><br />
        Choose a suggestion in Diagnostics to compare the text before and after.
      </div>
      ${pane("before", "Input", before, [])}`;
    return;
  }

  if (repaired === before) {
    diffBox.innerHTML = `
      <div style="grid-column:1/-1" class="note"><b>No changes.</b> The repaired file is identical to the input.</div>
      ${pane("before", "Input", before, [])}
      ${pane("after", "Repaired", repaired, [])}`;
    return;
  }

  const beforeLines = before.split("\n");
  const afterLines = repaired.split("\n");
  const diff = computeDiff(beforeLines, afterLines);
  const beforeRows = diff.filter((d) => d.type !== "ins");
  const afterRows = diff.filter((d) => d.type !== "del");

  diffBox.innerHTML =
    pane("before", "Input", before, beforeRows) +
    pane("after", "Repaired", repaired, afterRows);
}

function pane(kind, title, rawText, rows) {
  const tag = kind === "before" ? "before" : "after";
  if (!rows || rows.length === 0) {
    return `<div class="diff-col ${kind}">
      <h3>${title} <span class="tag">${tag}</span></h3>
      <div class="diff-body">${lineHtml(rawText.split("\n"), "eq")}</div>
    </div>`;
  }
  let n = 0;
  const body = rows.map((row) => {
    const cls = row.type === "del" ? "del" : row.type === "ins" ? "ins" : "eq";
    if (row.type !== "ins" || kind === "after") n++;
    return `<div class="dl ${cls === "eq" ? "" : cls}"><span class="ln">${row.no ?? ""}</span>${escapeHtml(row.text)}</div>`;
  }).join("");
  return `<div class="diff-col ${kind}">
    <h3>${title} <span class="tag">${tag}</span></h3>
    <div class="diff-body">${body}</div>
  </div>`;
}

function lineHtml(lines, cls) {
  return lines.map((line, i) =>
    `<div class="dl ${cls === "eq" ? "" : cls}"><span class="ln">${i + 1}</span>${escapeHtml(line)}</div>`
  ).join("");
}

function computeDiff(before, after) {
  const n = before.length, m = after.length;
  if (n * m > 4_000_000) {
    return before.map((t, i) => ({ type: "eq", text: t, no: i + 1 }))
      .concat(after.map(() => null)).filter(Boolean);
  }
  const dp = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = before[i] === after[j]
        ? dp[i + 1][j + 1] + 1
        : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (before[i] === after[j]) {
      out.push({ type: "eq", text: before[i], no: i + 1 });
      i++; j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ type: "del", text: before[i], no: i + 1 });
      i++;
    } else {
      out.push({ type: "ins", text: after[j], no: j + 1 });
      j++;
    }
  }
  while (i < n) { out.push({ type: "del", text: before[i], no: i + 1 }); i++; }
  while (j < m) { out.push({ type: "ins", text: after[j], no: j + 1 }); j++; }
  return out;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

setEditor(SAMPLES.trailingComma);
run();
