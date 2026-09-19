const $ = (q) => document.querySelector(q);
const $$ = (q) => [...document.querySelectorAll(q)];
let attachmentText = "", attachmentName = "", mediaStream = null;

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
}
function markdown(value) {
  let html = escapeHtml(value).replace(/```([\s\S]*?)```/g, "<pre><code>$1</code></pre>");
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  html = html.replace(/^\s*[-*]\s+(.+)$/gm, "<li>$1</li>").replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>");
  return html.split(/\n\n+/).map(block => block.startsWith("<pre>") || block.startsWith("<ul>") ? block : `<p>${block.replace(/\n/g, "<br>")}</p>`).join("");
}
function addMessage(kind, text) {
  $("#empty-chat")?.remove();
  const item = document.createElement("article"); item.className = `message ${kind}`;
  item.innerHTML = `<span class="label">${kind === "user" ? "YOU" : "ZEUS"}</span><div>${kind === "zeus" ? markdown(text) : escapeHtml(text).replace(/\n/g, "<br>")}</div>`;
  $("#messages").append(item); $("#messages").scrollTop = $("#messages").scrollHeight;
}
function toast(text) { const el = $("#toast"); el.textContent = text; el.classList.add("show"); setTimeout(() => el.classList.remove("show"), 2800); }
function setState(state) {
  $("#status").textContent = state.status.toUpperCase(); $("#agent-status").textContent = state.status.toUpperCase();
  $("#status-dot").style.background = state.status === "idle" ? "var(--green)" : "var(--amber)";
  $("#last-action").textContent = state.tools?.length ? state.tools.join(", ") : "NONE";
  $("#agent-sub").textContent = state.status === "idle" ? "Waiting for your next instruction" : "ZEUS is processing your request";
}
async function request(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "The local bridge returned an error");
  return data;
}
async function refresh() {
  try { setState(await request("/api/state")); $("#runtime").textContent = "LOCAL / READY"; renderActivity((await request("/api/state")).tools); }
  catch (e) { $("#status").textContent = "OFFLINE"; $("#runtime").textContent = "BRIDGE OFFLINE"; $("#status-dot").style.background = "#ff727d"; }
}
function renderActivity(tools = []) {
  const html = tools.length ? tools.map(t => `<div class="activity-item"><i>◆</i><span>${escapeHtml(t)}<br><small class="muted">Completed in this session</small></span></div>`).join("") : '<div class="muted">No tool activity yet. Ask ZEUS to inspect or research something.</div>';
  $("#activity-list").innerHTML = html; $("#system-activity").innerHTML = html;
}
async function sendMessage(message) {
  addMessage("user", message); $("#message").value = ""; $("#error").textContent = ""; $("#send").disabled = true; $("#send").textContent = "THINKING…";
  try {
    const data = await request("/api/chat", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({message, attachment:attachmentText}) });
    if (data.tools?.length) { $("#tool-strip").textContent = `● ACTIONS  ${data.tools.join("  ·  ")}`; $("#tool-strip").classList.remove("hidden"); }
    addMessage("zeus", data.reply); attachmentText = ""; attachmentName = ""; $("#attachment").classList.add("hidden"); renderActivity(data.tools);
  } catch (e) { $("#error").textContent = e.message; toast("Request failed"); }
  finally { $("#send").disabled = false; $("#send").textContent = "SEND ↵"; refresh(); }
}
$("#composer").addEventListener("submit", e => { e.preventDefault(); const value = $("#message").value.trim(); if (value) sendMessage(value); });
$("#message").addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#composer").requestSubmit(); }});
$$(".suggestions button").forEach(b => b.addEventListener("click", () => { $("#message").value = b.dataset.prompt; $("#message").focus(); }));
$("#file-input").addEventListener("change", async e => {
  const file = e.target.files[0]; if (!file) return; $("#attachment").textContent = `Uploading ${file.name}…`; $("#attachment").classList.remove("hidden");
  try { const data = await request("/api/upload", {method:"POST", body:(() => { const f = new FormData(); f.append("file", file); return f; })()}); attachmentText = data.content; attachmentName = data.name; $("#attachment").textContent = `Attached: ${data.name} (${Math.round(data.size / 1024)} KB)`; toast("File attached"); }
  catch (err) { $("#attachment").textContent = ""; $("#attachment").classList.add("hidden"); toast(err.message); }
});
async function loadHistory() {
  const box = $("#history-list"); box.innerHTML = '<div class="loading-block">Loading saved context…</div>';
  try { const data = await request("/api/history"); box.innerHTML = data.messages.length ? data.messages.map(m => `<div class="history-item"><span>${m.role.toUpperCase()}</span><p>${escapeHtml(m.content)}</p></div>`).join("") : '<div class="loading-block">No conversation history in this session yet.</div>'; }
  catch (e) { box.innerHTML = `<div class="error">${escapeHtml(e.message)}</div>`; }
}
async function loadMetrics() {
  try { const m = await request("/api/metrics"); [["cpu",m.cpu],["memory",m.memory],["disk",m.disk]].forEach(([name,value]) => { $(`#${name}`).textContent = `${Math.round(value)}%`; $(`#${name}-bar`).style.width = `${value}%`; }); $("#os-label").textContent = `${m.os} · Python ${m.python}`; } catch (_) {}
}
async function loadSettings() {
  try { const s = await request("/api/settings"); $("#settings-list").innerHTML = Object.entries(s).map(([key,value]) => `<div class="setting"><span>${key.replaceAll("_"," ").toUpperCase()}</span><b>${escapeHtml(value)}</b></div>`).join(""); } catch (e) { $("#settings-list").textContent = e.message; }
}
function switchView(view) {
  $$(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === view)); $$(".view").forEach(v => v.classList.toggle("active", v.id === `view-${view}`));
  $("#view-title").textContent = view.replace("-", " ").toUpperCase(); $("#headline").textContent = view === "chat" ? "Good morning, operator." : view === "history" ? "Your context, in one place." : view === "system" ? "Telemetry at a glance." : "Tune your local bridge.";
  if (view === "history") loadHistory(); if (view === "system") loadMetrics(); if (view === "settings") loadSettings(); $("#sidebar")?.classList.remove("open");
}
$$(".nav-item").forEach(b => b.addEventListener("click", () => switchView(b.dataset.view)));
$$("[data-view-target]").forEach(b => b.addEventListener("click", () => switchView(b.dataset.viewTarget)));
$("#history-refresh").addEventListener("click", loadHistory); $("#refresh").addEventListener("click", () => { refresh(); loadMetrics(); });
$("#mobile-menu").addEventListener("click", () => $(".sidebar").classList.toggle("open")); $("#collapse").addEventListener("click", () => $(".sidebar").classList.toggle("open"));
$("#camera-start").addEventListener("click", async () => { try { mediaStream = await navigator.mediaDevices.getUserMedia({video:true}); $("#camera").srcObject = mediaStream; $("#camera-start").classList.add("hidden"); $("#camera-stop").classList.remove("hidden"); $("#camera-state").textContent = "ON"; $("#camera-toggle").classList.add("active"); } catch (_) { toast("Camera permission was not granted"); }});
$("#camera-stop").addEventListener("click", () => { mediaStream?.getTracks().forEach(t => t.stop()); mediaStream = null; $("#camera").srcObject = null; $("#camera-start").classList.remove("hidden"); $("#camera-stop").classList.add("hidden"); $("#camera-state").textContent = "OFF"; $("#camera-toggle").classList.remove("active"); });
$("#camera-toggle").addEventListener("click", () => ($("#camera-start").classList.contains("hidden") ? $("#camera-stop") : $("#camera-start")).click());
$("#mic-toggle").addEventListener("click", () => { if (!("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) return toast("Speech recognition is not supported in this browser"); const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition; const recognition = new Recognition(); recognition.lang = navigator.language; recognition.onstart = () => { $("#mic-toggle").classList.add("active"); toast("Listening…"); }; recognition.onresult = e => { $("#message").value = e.results[0][0].transcript; }; recognition.onend = () => $("#mic-toggle").classList.remove("active"); recognition.onerror = () => toast("Microphone permission or recognition failed"); recognition.start(); });
refresh(); loadMetrics(); setInterval(refresh, 5000); setInterval(loadMetrics, 8000);
