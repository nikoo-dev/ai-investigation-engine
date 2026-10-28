"use strict";

const $ = (id) => document.getElementById(id);
const state = { answer: null, streamedAnswer: "", offset: 0, pageSize: 25, replaceId: null, busy: false, timer: null, started: 0, sourceSequence: 0, token: sessionStorage.getItem("investigation-management-token") || "" };

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined && text !== null) element.textContent = String(text);
  if (className) element.className = className;
  return element;
}

function show(element, visible = true) { element.classList.toggle("hidden", !visible); }
function clear(element) { element.replaceChildren(); }
function managementHeaders() { return state.token ? { Authorization: `Bearer ${state.token}` } : {}; }

async function api(path, options = {}) {
  let response;
  try { response = await fetch(path, options); }
  catch { throw new Error("The workspace could not be reached. If the free demo is waking up, wait a minute and try again."); }
  if (!response.ok) {
    let body = {};
    try { body = await response.json(); } catch { /* The hosting service may return its own cold-start page. */ }
    let message = body.error?.message || body.detail;
    if (Array.isArray(message)) message = message.map((item) => item.msg || "Invalid input").join("; ");
    if (typeof message !== "string") message = response.status === 503 ? "The service is preparing its sources. Please try again shortly." : `The request could not be completed (${response.status}).`;
    if (response.status === 401) message += " Open Management access to enter the token.";
    throw new Error(message);
  }
  return response;
}

function errorMessage(id, error) { $(id).textContent = error.message || String(error); show($(id)); }
let toastTimer;
function toast(message) { $("toast").textContent = message; show($("toast")); clearTimeout(toastTimer); toastTimer = setTimeout(() => show($("toast"), false), 3500); }

async function refreshStatus() {
  try {
    const status = await (await api("/api/v1/status")).json();
    const corpus = status.corpus || {};
    $("corpus-count").textContent = Number(corpus.documents || 0).toLocaleString();
    $("corpus-detail").textContent = `${Number(corpus.chunks || 0).toLocaleString()} searchable passages`;
    $("search-mode").textContent = `${status.retrieval_mode === "hybrid" ? "Dense + keyword" : status.retrieval_mode} search`;
    $("system-status").textContent = "Workspace ready";
    $("upload-size").textContent = status.max_upload_mb;
    if (status.provider === "extractive") {
      $("provider-notice").textContent = "Evidence preview mode: this workspace returns retrieved source excerpts without LLM synthesis. A configured language model is required for the full investigation workflow.";
      show($("provider-notice"));
    } else {
      $("provider-notice").textContent = `${status.model} · grounded synthesis with source citations`;
      show($("provider-notice"));
    }
  } catch (error) {
    $("system-status").textContent = "Connection unavailable";
    $("corpus-detail").textContent = "Reconnect to load your sources";
    errorMessage("investigation-error", error);
  }
}

function switchView(view) {
  document.querySelectorAll(".nav-button").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
  show($("investigate-view"), view === "investigate");
  show($("library-view"), view === "library");
  $("breadcrumb-current").textContent = view === "library" ? "Document library" : "Investigation";
  if (view === "library") loadDocuments();
}

document.querySelectorAll(".nav-button").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
document.querySelectorAll(".suggestion").forEach((button) => button.addEventListener("click", () => {
  $("question").value = button.dataset.question;
  $("question").focus();
}));

function setBusy(busy) {
  state.busy = busy;
  $("investigate-button").disabled = busy;
  $("question").readOnly = busy;
  $("investigate-button").firstChild.textContent = busy ? "Investigating… " : "Start investigation ";
  show($("progress-panel"), busy);
  if (busy) {
    state.streamedAnswer = "";
    $("answer-preview").textContent = "";
    show($("answer-preview"), false);
    state.started = performance.now();
    $("progress-time").textContent = "0s";
    state.timer = setInterval(() => $("progress-time").textContent = `${Math.round((performance.now() - state.started) / 1000)}s`, 1000);
  } else clearInterval(state.timer);
}

function progress(data, event) {
  const detail = typeof data === "string" ? data : data.detail || data.message || data.stage || event;
  if (!detail) return;
  const text = String(detail);
  $("progress-label").textContent = text;
  if (text !== $("progress-steps").lastChild?.textContent) $("progress-steps").append(node("li", text));
}

function dispatchEvent(event, data) {
  if (event === "error") throw new Error(data.message || data.error?.message || "The investigation could not be completed.");
  if (event === "answer_fragment") {
    if (typeof data.text === "string") {
      state.streamedAnswer += data.text;
      $("answer-preview").textContent = state.streamedAnswer;
      show($("answer-preview"));
      $("progress-label").textContent = "Receiving verified findings";
      $("answer-preview").scrollTop = $("answer-preview").scrollHeight;
    }
    return;
  }
  if (["final", "answer", "result"].includes(event)) renderAnswer(data);
  else progress(data, event);
}

async function readEvents(response) {
  if (!response.body) throw new Error("Streaming is unavailable in this browser.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  function consume(block) {
    let event = "progress";
    const data = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (data.length) dispatchEvent(event, JSON.parse(data.join("\n")));
  }
  try {
    while (true) {
      const { value, done } = await reader.read();
      pending += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
      let boundary;
      while ((boundary = pending.indexOf("\n\n")) !== -1) {
        const block = pending.slice(0, boundary);
        pending = pending.slice(boundary + 2);
        consume(block);
      }
      if (done) break;
    }
    if (pending.trim()) consume(pending);
  } finally { reader.releaseLock(); }
}

$("investigation-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = $("question").value.trim();
  if (state.busy || question.length < 3) return;
  show($("investigation-error"), false);
  show($("answer-panel"), false);
  show($("empty-state"), false);
  clear($("progress-steps"));
  state.answer = null;
  setBusy(true);
  try {
    const response = await api("/api/v1/investigations/stream", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) });
    await readEvents(response);
    if (!state.answer) throw new Error("The response ended before verified findings were returned. Please try again.");
  } catch (error) { errorMessage("investigation-error", error); }
  finally { setBusy(false); }
});

$("question").addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    $("investigation-form").requestSubmit();
  }
});

function citationButton(id, citations) {
  const button = node("button", `[${id}]`, "citation-button");
  button.type = "button";
  const citation = citations.find((item) => item.id === id);
  if (citation) {
    button.setAttribute("aria-label", `Inspect source ${id}: ${citation.title}`);
    button.addEventListener("click", () => openCitation(citation));
  } else button.disabled = true;
  return button;
}

function renderAnswer(answer) {
  state.answer = answer;
  show($("answer-preview"), false);
  $("answer-question").textContent = answer.question;
  $("answer-text").textContent = answer.answer;
  const status = $("answer-status");
  status.className = "result-status";
  if (answer.status === "conflicting_evidence") { status.textContent = "CONFLICTING EVIDENCE"; status.classList.add("conflict"); }
  else if (answer.status === "insufficient_evidence") { status.textContent = "INSUFFICIENT EVIDENCE"; status.classList.add("insufficient"); }
  else if (answer.status === "error") { status.textContent = "INVESTIGATION INCOMPLETE"; status.classList.add("insufficient"); }
  else status.textContent = "EVIDENCE-BASED FINDINGS";
  $("answer-time").textContent = `${(Number(answer.elapsed_ms || 0) / 1000).toFixed(1)}s${answer.cached ? " · cached" : ""}`;
  const citations = answer.citations || [];
  clear($("answer-claims"));
  for (const claim of answer.claims || []) {
    const row = node("div", null, "claim-row");
    const text = node("span", claim.text);
    for (const id of claim.citation_ids || []) text.append(citationButton(id, citations));
    row.append(text);
    $("answer-claims").append(row);
  }
  show($("claims-section"), Boolean(answer.claims?.length));
  clear($("answer-conflicts"));
  for (const conflict of answer.conflicts || []) {
    const box = node("div", null, "conflict-box");
    box.append(node("strong", "CONFLICT IN THE SOURCES"), node("p", conflict.description));
    for (const id of conflict.citation_ids || []) box.append(citationButton(id, citations));
    $("answer-conflicts").append(box);
  }
  show($("answer-conflicts"), Boolean(answer.conflicts?.length));
  clear($("answer-warnings"));
  for (const warning of answer.warnings || []) $("answer-warnings").append(node("p", warning, "notice"));
  show($("answer-warnings"), Boolean(answer.warnings?.length));
  clear($("answer-sources"));
  $("source-count").textContent = citations.length;
  for (const citation of citations) {
    const button = node("button", null, "source-card");
    button.type = "button";
    const top = node("div", null, "source-card-top");
    top.append(node("span", citation.id), node("span", locationLabel(citation.location)), node("span", "↗"));
    button.append(top, node("strong", citation.title), node("p", citation.quote));
    button.addEventListener("click", () => openCitation(citation));
    $("answer-sources").append(button);
  }
  if (!citations.length) $("answer-sources").append(node("p", "No supporting source passages were established.", "demo-note"));
  clear($("answer-plan"));
  const plan = answer.plan || {};
  $("answer-plan").append(node("p", `${plan.kind || "Investigation"} · ${answer.provider} / ${answer.model}`, "trace-plan"));
  for (const [index, question] of (plan.subquestions || []).entries()) $("answer-plan").append(node("p", `${index + 1}. ${question}`, "trace-plan"));
  clear($("answer-trace"));
  for (const step of answer.trace || []) {
    const item = node("li");
    item.append(node("strong", `${step.stage}: `), node("span", step.detail), node("span", ` (${Math.round(step.duration_ms || 0)} ms)`));
    $("answer-trace").append(item);
  }
  show($("answer-panel"));
  $("answer-heading").tabIndex = -1;
  $("answer-heading").focus({ preventScroll: true });
}

function locationLabel(location) {
  if (!location) return "Source passage";
  const parts = [];
  if (location.page) parts.push(`Page ${location.page}`);
  if (location.section) parts.push(location.section);
  if (location.sentence_ids?.length) parts.push(`Sentences ${location.sentence_ids.map((i) => i + 1).join(", ")}`);
  return parts.join(" · ") || "Source passage";
}

function originalLink(uri) {
  const anchor = $("source-original");
  anchor.removeAttribute("href");
  show(anchor, false);
  if (!uri) return;
  try {
    const url = new URL(uri);
    if (["https:", "http:"].includes(url.protocol)) { anchor.href = url.href; show(anchor); }
  } catch { /* Dataset source identifiers need not be URLs. */ }
}

async function openCitation(citation) {
  const sequence = ++state.sourceSequence;
  $("source-title").textContent = citation.title;
  $("source-meta").textContent = `${citation.id} · DOCUMENT REVISION ${citation.revision}`;
  $("source-location").textContent = locationLabel(citation.location);
  $("source-quote").textContent = citation.quote;
  show($("source-quote"));
  $("source-content").textContent = "Loading the stored source passage…";
  $("source-content").classList.remove("source-error");
  originalLink(citation.source_uri);
  $("source-dialog").showModal();
  try {
    const passage = await (await api(`/api/v1/passages/${encodeURIComponent(citation.passage_id)}`)).json();
    if (sequence !== state.sourceSequence) return;
    $("source-content").textContent = passage.text;
  } catch (error) { if (sequence === state.sourceSequence) { $("source-content").textContent = error.message; $("source-content").classList.add("source-error"); } }
}

async function openDocument(id) {
  const sequence = ++state.sourceSequence;
  $("source-title").textContent = "Loading document…";
  $("source-meta").textContent = "DOCUMENT INSPECTOR";
  $("source-location").textContent = "";
  $("source-content").textContent = "Loading the stored document…";
  $("source-content").classList.remove("source-error");
  show($("source-quote"), false);
  originalLink(null);
  $("source-dialog").showModal();
  try {
    const doc = await (await api(`/api/v1/documents/${encodeURIComponent(id)}`)).json();
    if (sequence !== state.sourceSequence) return;
    $("source-title").textContent = doc.title;
    $("source-meta").textContent = `${doc.format.toUpperCase()} · REVISION ${doc.revision} · ${doc.chunk_count} PASSAGES`;
    $("source-location").textContent = doc.filename;
    $("source-content").textContent = doc.text;
    originalLink(doc.source_uri);
  } catch (error) { if (sequence === state.sourceSequence) { $("source-content").textContent = error.message; $("source-content").classList.add("source-error"); } }
}

$("close-source").addEventListener("click", () => $("source-dialog").close());
$("copy-answer").addEventListener("click", async () => {
  if (!state.answer) return;
  const answer = state.answer;
  const sources = (answer.citations || []).map((citation) => `[${citation.id}] ${citation.title} (revision ${citation.revision}, ${locationLabel(citation.location)})`).join("\n");
  try { await navigator.clipboard.writeText(`${answer.question}\n\n${answer.answer}\n\n${sources}`); toast("Findings copied with source references."); }
  catch { toast("Clipboard access is unavailable. Select the findings to copy them."); }
});

async function loadDocuments() {
  show($("library-error"), false);
  try {
    const result = await (await api(`/api/v1/documents?limit=${state.pageSize}&offset=${state.offset}`)).json();
    const docs = result.items || [];
    clear($("document-list"));
    for (const doc of docs) {
      const row = node("tr");
      const titleCell = node("td");
      const title = node("button", doc.title, "document-title");
      title.title = doc.title;
      title.addEventListener("click", () => openDocument(doc.id));
      titleCell.append(title, node("small", doc.filename));
      const formatCell = node("td"); formatCell.append(node("span", doc.format, "doc-format"));
      const statusCell = node("td"); statusCell.append(node("span", doc.status, `doc-status ${doc.status}`));
      const actions = node("td");
      const group = node("div", null, "doc-actions");
      const replace = node("button", "Replace");
      replace.title = `Replace ${doc.title}`;
      replace.addEventListener("click", () => { state.replaceId = doc.id; $("replace-file").click(); });
      const remove = node("button", "Delete", "delete-action");
      remove.title = `Delete ${doc.title}`;
      remove.addEventListener("click", () => deleteDocument(doc));
      group.append(replace, remove); actions.append(group);
      row.append(titleCell, formatCell, node("td", `v${doc.revision}`), node("td", doc.chunk_count), statusCell, actions);
      $("document-list").append(row);
    }
    show($("library-empty"), !docs.length);
    $("library-range").textContent = docs.length ? `${state.offset + 1}–${state.offset + docs.length}` : "No sources";
    $("page-number").textContent = `Page ${Math.floor(state.offset / state.pageSize) + 1}`;
    $("previous-page").disabled = state.offset === 0;
    $("next-page").disabled = docs.length < state.pageSize;
  } catch (error) { errorMessage("library-error", error); }
}

$("refresh-library").addEventListener("click", () => { loadDocuments(); refreshStatus(); });
$("previous-page").addEventListener("click", () => { state.offset = Math.max(0, state.offset - state.pageSize); loadDocuments(); });
$("next-page").addEventListener("click", () => { state.offset += state.pageSize; loadDocuments(); });

async function uploadDocument(file, documentId) {
  show($("library-error"), false);
  show($("library-message"), false);
  const payload = new FormData(); payload.append("file", file);
  $("upload-button").disabled = true;
  $("library-message").textContent = "Extracting, indexing, and checking document revisions…"; show($("library-message"));
  try {
    const path = documentId ? `/api/v1/documents/${encodeURIComponent(documentId)}` : "/api/v1/documents";
    const result = await (await api(path, { method: documentId ? "PUT" : "POST", body: payload, headers: managementHeaders() })).json();
    const statusText = { created: "Document indexed", updated: "Document revision updated", duplicate: "Exact duplicate already indexed", near_duplicate: "Document indexed; similar content detected" };
    $("library-message").textContent = `${statusText[result.status] || "Document processed"}: ${result.document.title}. ${(result.warnings || []).join(" ")}`;
    if (!documentId) $("upload-file").value = "";
    state.offset = 0; await loadDocuments(); await refreshStatus();
  } catch (error) { show($("library-message"), false); errorMessage("library-error", error); }
  finally { $("upload-button").disabled = false; }
}

$("upload-form").addEventListener("submit", async (event) => { event.preventDefault(); const file = $("upload-file").files[0]; if (file) await uploadDocument(file); });
$("replace-file").addEventListener("change", async () => { const file = $("replace-file").files[0]; const id = state.replaceId; $("replace-file").value = ""; if (file && id) await uploadDocument(file, id); });

async function deleteDocument(doc) {
  if (!window.confirm(`Delete “${doc.title}” and its searchable passages? This action cannot be undone.`)) return;
  try { await api(`/api/v1/documents/${encodeURIComponent(doc.id)}`, { method: "DELETE", headers: managementHeaders() }); toast("Document removed from the corpus."); await loadDocuments(); await refreshStatus(); }
  catch (error) { errorMessage("library-error", error); }
}

$("settings-button").addEventListener("click", () => { $("management-token").value = state.token; $("settings-dialog").showModal(); });
$("mobile-settings-button").addEventListener("click", () => { $("management-token").value = state.token; $("settings-dialog").showModal(); });
$("close-settings").addEventListener("click", () => $("settings-dialog").close());
$("settings-form").addEventListener("submit", (event) => { event.preventDefault(); state.token = $("management-token").value.trim(); if (state.token) sessionStorage.setItem("investigation-management-token", state.token); else sessionStorage.removeItem("investigation-management-token"); $("settings-dialog").close(); toast("Management access saved for this tab."); });
$("clear-token").addEventListener("click", () => { state.token = ""; sessionStorage.removeItem("investigation-management-token"); $("management-token").value = ""; toast("Management token cleared."); });

refreshStatus();
