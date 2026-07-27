// LunaShop Agente — frontend estático en JavaScript puro (sin frameworks,
// sin React) alojado como Streamlit Custom Component.
//
// Este archivo implementa dos cosas:
//   1. El protocolo mínimo de comunicación Streamlit <-> Componente
//      (basado en postMessage), documentado por el equipo de Streamlit
//      para componentes sin herramientas de build.
//   2. La lógica de la interfaz (chat + gestor de documentos).

// ============ 1. Protocolo Streamlit Component (sin build tools) ============

function sendMessageToStreamlitClient(type, data) {
  const outData = Object.assign({ isStreamlitMessage: true, type }, data);
  window.parent.postMessage(outData, "*");
}

function initStreamlitComponent() {
  sendMessageToStreamlitClient("streamlit:componentReady", { apiVersion: 1 });
}

function setFrameHeight() {
  const height = document.documentElement.scrollHeight;
  sendMessageToStreamlitClient("streamlit:setFrameHeight", { height });
}

function sendValueToPython(value) {
  sendMessageToStreamlitClient("streamlit:setComponentValue", { value });
}

let currentArgs = { history: [], documents: [], status: {} };

function onMessageFromStreamlit(event) {
  if (!event.data || event.data.type !== "streamlit:render") return;
  currentArgs = event.data.args || currentArgs;
  render();
}

window.addEventListener("message", onMessageFromStreamlit);
window.addEventListener("load", () => {
  initStreamlitComponent();
  setTimeout(setFrameHeight, 50);
});

function nonce() {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

// ============ 2. Estado local de UI ============

let pendingQuestion = null; // pregunta en curso, mientras esperamos respuesta de Python
let feedbackGiven = {}; // índice de mensaje -> "positivo"/"negativo"

// ============ 3. Render principal ============

function render() {
  renderStatusBadges(currentArgs.status || {});
  renderMessages(currentArgs.history || []);
  renderDocuments(currentArgs.documents || []);
  setTimeout(setFrameHeight, 30);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML;
}

// ---- Cuadritos de estado (modelo / base de datos) ----

function renderStatusBadges(status) {
  const el = document.getElementById("statusBadges");
  const chunkInfo = status.indexed_chunks != null ? `${status.indexed_chunks} fragmentos` : "—";
  el.innerHTML = `
    <div class="badge">
      <span class="badge-label">Modelo (LLM)</span>
      <span class="badge-value">${escapeHtml(status.llm_provider || "—")} · ${escapeHtml(status.llm_model || "—")}</span>
    </div>
    <div class="badge">
      <span class="badge-label">Embeddings</span>
      <span class="badge-value dim">${escapeHtml(status.embedding_model || "—")}</span>
    </div>
    <div class="badge">
      <span class="badge-label">Base de datos vectorial</span>
      <span class="badge-value dim">${escapeHtml(status.vector_db || "—")} · ${chunkInfo}</span>
    </div>
  `;
}

// ---- Chat ----

function renderMessages(history) {
  const el = document.getElementById("messages");

  if (history.length === 0 && !pendingQuestion) {
    el.innerHTML = `
      <div class="msg msg-agent">
        <div class="msg-avatar">☾</div>
        <div class="msg-bubble">
          <p>Hola, soy el agente de soporte de LunaShop. Pregúntame sobre políticas, envíos, pagos o devoluciones.</p>
        </div>
      </div>
    `;
    return;
  }

  let html = "";
  history.forEach((turn, i) => {
    html += `
      <div class="msg msg-user">
        <div class="msg-avatar">🙂</div>
        <div class="msg-bubble"><p>${escapeHtml(turn.question)}</p></div>
      </div>
      <div class="msg msg-agent">
        <div class="msg-avatar">☾</div>
        <div class="msg-bubble">
          <p>${escapeHtml(turn.answer)}</p>
          ${renderSources(turn.sources)}
          ${renderFeedback(i, turn)}
        </div>
      </div>
    `;
  });

  if (pendingQuestion) {
    html += `
      <div class="msg msg-user">
        <div class="msg-avatar">🙂</div>
        <div class="msg-bubble"><p>${escapeHtml(pendingQuestion)}</p></div>
      </div>
      <div class="msg msg-agent">
        <div class="msg-avatar">☾</div>
        <div class="msg-bubble">
          <div class="typing"><span></span><span></span><span></span></div>
        </div>
      </div>
    `;
  }

  el.innerHTML = html;
  el.scrollTop = el.scrollHeight;

  // Si la respuesta ya llegó (el historial creció), limpiamos el pendiente.
  if (pendingQuestion && history.length && history[history.length - 1].question === pendingQuestion) {
    pendingQuestion = null;
  }

  document.getElementById("sendBtn").disabled = false;
  document.getElementById("questionInput").disabled = false;
}

function renderSources(sources) {
  if (!sources || sources.length === 0) return "";
  const items = sources
    .map(
      (s) =>
        `<div class="source-item"><span>${escapeHtml(s.archivo)} · ${escapeHtml(s.categoria)}</span><span>${s.relevancia}</span></div>`
    )
    .join("");
  return `
    <details class="sources">
      <summary>📎 Fuentes utilizadas (${sources.length})</summary>
      ${items}
    </details>
  `;
}

function renderFeedback(index, turn) {
  const given = feedbackGiven[index];
  return `
    <div class="feedback-row">
      <button type="button" class="feedback-btn ${given === "positivo" ? "chosen" : ""}" onclick="sendFeedback(${index}, 'positivo')">👍 Útil</button>
      <button type="button" class="feedback-btn ${given === "negativo" ? "chosen" : ""}" onclick="sendFeedback(${index}, 'negativo')">👎 No útil</button>
    </div>
  `;
}

function sendFeedback(index, value) {
  const turn = currentArgs.history[index];
  if (!turn) return;
  feedbackGiven[index] = value;
  renderMessages(currentArgs.history);
  sendValueToPython({
    action: "feedback",
    question: turn.question,
    answer: turn.answer,
    sources: turn.sources,
    feedback: value,
    nonce: nonce(),
  });
}

function askQuestion(question) {
  pendingQuestion = question;
  document.getElementById("sendBtn").disabled = true;
  document.getElementById("questionInput").disabled = true;
  renderMessages(currentArgs.history || []);
  sendValueToPython({ action: "ask", question, nonce: nonce() });
}

document.addEventListener("DOMContentLoaded", () => {
  const composer = document.getElementById("composer");
  composer.addEventListener("submit", (e) => {
    e.preventDefault();
    const input = document.getElementById("questionInput");
    const q = input.value.trim();
    if (!q || pendingQuestion) return;
    input.value = "";
    askQuestion(q);
  });

  // Tabs
  document.getElementById("tabChatBtn").addEventListener("click", () => switchTab("chat"));
  document.getElementById("tabDocsBtn").addEventListener("click", () => switchTab("docs"));

  // Upload zone
  const uploadZone = document.getElementById("uploadZone");
  const fileInput = document.getElementById("fileInput");
  uploadZone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length) handleUpload(e.target.files[0]);
  });
  uploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadZone.classList.add("dragover");
  });
  uploadZone.addEventListener("dragleave", () => uploadZone.classList.remove("dragover"));
  uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadZone.classList.remove("dragover");
    if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files[0]);
  });
});

function switchTab(tab) {
  document.getElementById("tabChatBtn").classList.toggle("active", tab === "chat");
  document.getElementById("tabDocsBtn").classList.toggle("active", tab === "docs");
  document.getElementById("panelChat").hidden = tab !== "chat";
  document.getElementById("panelDocs").hidden = tab !== "docs";
  setTimeout(setFrameHeight, 30);
}

// ---- Documentos ----

const SUPPORTED_EXT = [".md", ".pdf", ".docx", ".xlsx", ".csv", ".json", ".html", ".htm", ".pptx"];

function handleUpload(file) {
  const ext = "." + file.name.split(".").pop().toLowerCase();
  if (!SUPPORTED_EXT.includes(ext)) {
    showToast(`Formato no soportado: ${ext}`);
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    const base64 = reader.result.split(",")[1];
    showToast(`Subiendo e indexando "${file.name}"…`);
    sendValueToPython({
      action: "upload",
      filename: file.name,
      content_b64: base64,
      nonce: nonce(),
    });
  };
  reader.readAsDataURL(file);
}

function deleteDocument(filename) {
  if (!confirm(`¿Eliminar "${filename}" del agente? El índice se actualizará.`)) return;
  showToast(`Eliminando "${filename}"…`);
  sendValueToPython({ action: "delete", filename, nonce: nonce() });
}

function renderDocuments(documents) {
  const list = document.getElementById("docsList");
  const count = document.getElementById("docsCount");
  count.textContent = documents.length;

  if (documents.length === 0) {
    list.innerHTML = `<li class="docs-empty">Aún no hay documentos indexados. Sube el primero arriba.</li>`;
    return;
  }

  list.innerHTML = documents
    .map(
      (d) => `
      <li class="doc-item">
        <div class="doc-info">
          <span class="doc-name">${escapeHtml(d.name)}</span>
          <span class="doc-meta">${d.size_kb} KB</span>
        </div>
        <button type="button" class="doc-delete" onclick="deleteDocument('${d.name.replace(/'/g, "\\'")}')">🗑 Eliminar</button>
      </li>
    `
    )
    .join("");
}

function showToast(message) {
  let toast = document.getElementById("toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    toast.className = "toast";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(window._toastTimeout);
  window._toastTimeout = setTimeout(() => toast.classList.remove("show"), 3500);
}
