const $ = (selector) => document.querySelector(selector);
const state = { seeded: false, busy: false };

function textNode(tag, text, className = "") {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `请求失败（${response.status}）`);
  return data;
}

function setFeedback(message, isError = false) {
  const node = $("#upload-feedback");
  node.textContent = message;
  node.classList.toggle("error", isError);
}

async function refreshStatus() {
  try {
    const [health, info] = await Promise.all([api("/health"), api("/collection_info")]);
    $("#api-status").textContent = "在线";
    $("#api-status").style.color = "var(--teal)";
    $(".status-light").classList.add("ok");
    $("#mode-pill").innerHTML = '<i class="dot ok"></i>本地服务正常';
    $("#chunk-count").textContent = info.entity_count ?? 0;
    $("#top-k").textContent = info.default_top_k ?? 5;
    $("#provider-label").textContent = info.answer_provider || health.version || "demo";
    $("#doc-label").textContent = `${info.entity_count ?? 0} chunks`;
  } catch (error) {
    $("#api-status").textContent = "不可用";
    $("#mode-pill").innerHTML = '<i class="dot"></i>连接失败';
    setFeedback(error.message, true);
  }
}

async function seedDemo() {
  if (state.busy) return;
  state.busy = true;
  const button = $("#seed-btn");
  button.disabled = true;
  button.textContent = "正在准备演示资料…";
  try {
    const result = await api("/demo/seed", { method: "POST" });
    state.seeded = true;
    setFeedback(`已载入 ${result.source}，可开始提问。`);
    await refreshStatus();
  } catch (error) { setFeedback(error.message, true); }
  finally { button.disabled = false; button.innerHTML = "<span>✦</span>载入演示知识库"; state.busy = false; }
}

function addMessage(role, answer, sources = []) {
  const row = document.createElement("div");
  row.className = `message ${role}`;
  row.appendChild(textNode("div", role === "assistant" ? "D" : "你", "avatar"));
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.appendChild(textNode("p", answer));
  if (sources.length) {
    const evidence = document.createElement("div"); evidence.className = "evidence";
    evidence.appendChild(textNode("div", `⌁ 证据来源 · ${sources.length} 条`, "evidence-title"));
    sources.forEach((source, index) => {
      const chunk = source.chunk || source;
      const card = document.createElement("article"); card.className = "source-card";
      const head = document.createElement("header");
      head.appendChild(textNode("span", `[${index + 1}] ${chunk.source || "文档片段"}`));
      head.appendChild(textNode("span", `${Math.round((source.score || 0) * 100)}% 匹配`, "score"));
      card.appendChild(head);
      card.appendChild(textNode("p", (chunk.text || "").slice(0, 260)));
      evidence.appendChild(card);
    });
    bubble.appendChild(evidence);
  }
  row.appendChild(bubble); $("#conversation").appendChild(row);
  $("#conversation").scrollTop = $("#conversation").scrollHeight;
}

async function ask(question) {
  const clean = question.trim();
  if (!clean || state.busy) return;
  state.busy = true; $("#question").value = ""; $("#question").style.height = "auto";
  addMessage("user", clean); $("#typing").hidden = false;
  try {
    const result = await api("/query", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: clean, similarity_threshold: 0, top_k: 5 }) });
    addMessage("assistant", result.answer, result.sources || []);
    $("#provider-label").textContent = result.provider || "demo";
  } catch (error) { addMessage("assistant", `暂时无法完成检索：${error.message}`); }
  finally { $("#typing").hidden = true; state.busy = false; }
}

async function upload(file) {
  if (!file || state.busy) return;
  state.busy = true; $("#upload-progress").hidden = false; setFeedback(`正在解析 ${file.name}…`);
  const form = new FormData(); form.append("file", file);
  try { const result = await api("/upload_file", { method: "POST", body: form }); setFeedback(`已索引 ${result.source} · ${result.chunks_indexed} 个切片`); await refreshStatus(); }
  catch (error) { setFeedback(error.message, true); }
  finally { $("#upload-progress").hidden = true; state.busy = false; $("#file-input").value = ""; }
}

async function clearCollection() {
  if (state.busy || !window.confirm("确认清空当前知识库吗？此操作会删除已索引切片。")) return;
  state.busy = true;
  try {
    await api("/clear_collection", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirm: true }) });
    setFeedback("知识库已清空，可以重新上传资料。", false);
    await refreshStatus();
  } catch (error) { setFeedback(error.message, true); }
  finally { state.busy = false; }
}

function mountWorkspaceActions() {
  const heading = document.querySelector(".upload-panel .panel-heading");
  if (!heading || document.querySelector("#clear-collection")) return;
  const actions = document.createElement("div");
  actions.className = "panel-heading-actions";
  const label = document.createElement("span");
  label.textContent = "LOCAL";
  label.className = "count-badge";
  const clear = document.createElement("button");
  clear.id = "clear-collection";
  clear.className = "clear-action";
  clear.type = "button";
  clear.textContent = "清空";
  clear.addEventListener("click", clearCollection);
  actions.append(label, clear);
  const existingBadge = heading.querySelector(".count-badge");
  if (existingBadge) existingBadge.remove();
  heading.appendChild(actions);
}

mountWorkspaceActions(); $("#seed-btn").addEventListener("click", seedDemo); $("#refresh-btn").addEventListener("click", refreshStatus);
$("#file-input").addEventListener("change", (event) => upload(event.target.files[0]));
$("#dropzone").addEventListener("dragover", (event) => { event.preventDefault(); $("#dropzone").classList.add("drag"); });
$("#dropzone").addEventListener("dragleave", () => $("#dropzone").classList.remove("drag"));
$("#dropzone").addEventListener("drop", (event) => { event.preventDefault(); $("#dropzone").classList.remove("drag"); upload(event.dataTransfer.files[0]); });
$("#chat-form").addEventListener("submit", (event) => { event.preventDefault(); ask($("#question").value); });
$("#question").addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); ask(event.target.value); } });
$("#question").addEventListener("input", (event) => { event.target.style.height = "auto"; event.target.style.height = `${Math.min(event.target.scrollHeight, 110)}px`; });
document.querySelectorAll(".tip").forEach((tip) => tip.addEventListener("click", () => { $("#question").value = tip.dataset.question; ask(tip.dataset.question); }));

refreshStatus().then(async () => {
  try { const info = await api("/collection_info"); if (!info.entity_count) await seedDemo(); }
  catch (_) { /* status panel already shows the actionable error */ }
});
