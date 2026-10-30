// AutoEdit Studio: one page, hash routes. Every button calls /api/..., long work runs as a job with a live log.
const $ = (s, el = document) => el.querySelector(s);
const main = $("#main");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fileUrl = (p) => "/api/file?path=" + encodeURIComponent(p);
const mb = (b) => (b / 1e6 >= 1000 ? (b / 1e9).toFixed(1) + " GB" : (b / 1e6).toFixed(1) + " MB");
const when = (t) => new Date(t * 1000).toLocaleString("nl-NL", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const enc = encodeURIComponent;

async function api(path, opts = {}) {
  const o = { ...opts };
  if (o.body && !(o.body instanceof FormData)) { o.headers = { "Content-Type": "application/json" }; o.body = JSON.stringify(o.body); }
  const r = await fetch(path, o);
  const data = r.headers.get("content-type")?.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error(data.error || data || r.statusText);
  return data;
}
function toast(msg, kind = "") {
  const t = document.createElement("div");
  t.className = "toast " + kind; t.textContent = msg; $("#toasts").append(t);
  setTimeout(() => t.remove(), kind === "err" ? 8000 : 4000);
}
async function guard(fn) { try { return await fn(); } catch (e) { toast(e.message, "err"); } }
function confirmDlg(title, html, okLabel = "OK") {
  return new Promise((res) => {
    const d = $("#dlg"); $("#dlgTitle").textContent = title; $("#dlgBody").innerHTML = html; $("#dlgOk").textContent = okLabel;
    d.onclose = () => res(d.returnValue === "ok"); d.showModal();
  });
}

// ------------------------------------------------------------------ jobs: drawer with live log
let watching = null;
async function startJob(path, body, { onDone } = {}) {
  const job = await guard(() => api(path, { method: "POST", body: body || {} }));
  if (job) watchJob(job.id, onDone);
  return job;
}
async function watchJob(id, onDone) {
  const me = (watching = { id, since: 0 });
  const dr = $("#drawer"), log = $("#drawerLog");
  dr.hidden = false; log.textContent = "";
  $("#drawerCancel").onclick = () => guard(() => api(`/api/jobs/${id}/cancel`, { method: "POST" }));
  while (watching === me) {
    const j = await api(`/api/jobs/${id}?since=${me.since}`).catch(() => null);
    if (!j) break;
    me.since = j.log_len;
    if (j.log.length) { log.textContent += j.log.join("\n") + "\n"; log.scrollTop = log.scrollHeight; }
    const st = { queued: "in de wachtrij", running: "bezig…", done: "klaar ✓", failed: "mislukt ✕", cancelled: "gestopt" }[j.status];
    $("#drawerTitle").textContent = `${j.label} — ${st}`;
    $("#drawerCancel").hidden = !["queued", "running"].includes(j.status);
    if (["done", "failed", "cancelled"].includes(j.status)) {
      toast(`${j.label}: ${st}`, j.status === "done" ? "ok" : "err");
      onDone && onDone(j, log.textContent);
      refreshBadge();
      break;
    }
    await new Promise((r) => setTimeout(r, 900));
  }
}
$("#drawerClose").onclick = () => { watching = null; $("#drawer").hidden = true; };
async function refreshBadge() {
  const jobs = await api("/api/jobs").catch(() => []);
  const n = jobs.filter((j) => ["queued", "running"].includes(j.status)).length;
  const b = $("#jobBadge"); b.hidden = !n; b.textContent = n;
}

// ------------------------------------------------------------------ status in the sidebar
async function loadStatus() {
  const s = await api("/api/status").catch(() => null);
  const dot = (on, label) => `<div><span class="dot ${on ? "on" : on === false ? "off" : ""}"></span>${label}</div>`;
  $("#sideStatus").innerHTML = s
    ? dot(true, s.mode === "docker" ? "Docker → Windows-worker" : "Lokaal op deze pc") + dot(s.resolve, "DaVinci Resolve") + dot(s.comfyui, "ComfyUI (lokale AI)")
    : dot(false, "Geen verbinding met de worker");
}

// ------------------------------------------------------------------ router
const routes = { "": home, queue, music, tools, jobs, p: project };
async function route() {
  const [, top = "", ...rest] = location.hash.split("/");
  document.querySelectorAll("nav a").forEach((a) => a.classList.toggle("on", a.dataset.nav === (top || "home") || (top === "p" && a.dataset.nav === "home")));
  main.innerHTML = '<div class="loading">Laden…</div>';
  await guard(() => (routes[top] || home)(...rest.map(decodeURIComponent)));
}
window.addEventListener("hashchange", route);

// ------------------------------------------------------------------ home: projects
async function home() {
  const list = await api("/api/projects");
  main.innerHTML = `
    <div class="head"><div><div class="crumb">AutoEdit Studio</div><h1>Projecten</h1></div><span class="spacer"></span>
      <button id="newBtn">+ Nieuw project</button></div>
    <div class="card" id="newCard" hidden style="margin-bottom:18px"><h2>Nieuw project</h2>
      <div class="form"><label>Naam<input id="npName" placeholder="bijv. Porto 2026"></label>
      <label>Titel in de video<input id="npTitle" placeholder="standaard: de naam"></label></div>
      <div class="row" style="margin-top:12px"><button id="npGo">Aanmaken</button>
      <span class="muted small">Maakt clips/, music/, exports/ en project.yaml in je AutoEdit Projects-map.</span></div></div>
    ${list.length ? `<div class="grid projects">${list.map(pcard).join("")}</div>` : '<div class="empty">Nog geen projecten.</div>'}`;
  $("#newBtn").onclick = () => ($("#newCard").hidden = !$("#newCard").hidden);
  $("#npGo").onclick = () => {
    const name = $("#npName").value.trim();
    if (!name) return toast("Geef het project een naam", "err");
    startJob("/api/projects", { name, title: $("#npTitle").value }, { onDone: (j) => j.status === "done" && (location.hash = "#/p/" + enc(name)) });
  };
}
function pcard(p) {
  const cine = p.cine === "approved" ? '<span class="tag ok">cine: goedgekeurd</span>' : p.cine === "pending" ? '<span class="tag warn">cine: plan wacht</span>' : "";
  return `<a class="pcard" href="#/p/${enc(p.name)}">
    <div class="img" style="${p.thumb ? `background-image:url('${fileUrl(p.thumb)}')` : ""}">${p.thumb ? "" : "▶"}</div>
    <div class="body"><div class="name">${esc(p.name)}</div>
      <div class="row">${p.category ? `<span class="tag">${esc(p.category)}</span>` : ""}<span class="tag">${p.clips} clips</span>
      <span class="tag">${p.exports} exports</span>${cine}</div></div></a>`;
}

// ------------------------------------------------------------------ project
let P = null;
async function project(name, tab = "cine") {
  P = await api("/api/projects/" + enc(name));
  const tabs = [["cine", "Cine montage"], ["autoedit", "AutoEdit (Resolve)"], ["ai", "AI-shot"], ["files", "Bestanden"], ["settings", "Instellingen"]];
  const s = P.settings || {};
  main.innerHTML = `
    <div class="head"><div><div class="crumb"><a href="#/">Projecten</a> / ${esc(P.name)}</div><h1>${esc(s.title || P.name)}</h1></div>
      <span class="spacer"></span>${s.category ? `<span class="tag">${esc(s.category)}</span>` : ""}
      <span class="tag">${P.clips.length} clips</span>${s.song ? `<span class="tag">♫ ${esc(s.song)}</span>` : ""}</div>
    <div class="tabs">${tabs.map(([k, l]) => `<a href="#/p/${enc(name)}/${k}" class="${k === tab ? "on" : ""}">${l}</a>`).join("")}</div>
    <div id="tab"></div>`;
  ({ cine: tabCine, autoedit: tabAutoedit, ai: tabAI, files: tabFiles, settings: tabSettings }[tab] || tabCine)();
}
const reload = () => route();

function tabCine() {
  const c = P.cine, s = P.settings || {};
  const appr = c.approval;
  const approved = appr && appr.status === "approved" && appr.current;
  const cineExports = P.exports.filter((f) => /cine_montage_.*\.mp4$/.test(f.name));
  const counts = c.checks.reduce((a, x) => ((a[x.status] = (a[x.status] || 0) + 1), a), {});
  $("#tab").innerHTML = `
  <div class="grid cols-2">
    <div class="stack">
      <div class="card"><h2>Plan maken</h2>
        <div class="form">
          <label class="full">Titel (één poster-titel)<input id="cTitle" value="${esc(c.title || (s.title || "").toUpperCase())}"></label>
          <label>Lengte (s)<input id="cLen" type="number" min="8" max="30" step="0.5" value="${c.duration || 18}"></label>
          <label>Seed<input id="cSeed" type="number" min="0" value="1"></label>
          <label>Look<select id="cLook"><option value="reference_film">B · film-look</option><option value="clean_warm">C · clean warm (eten)</option><option value="moody">moody</option></select></label>
          <label>Kleur van de beelden<select id="cGrade"><option value="auto">automatisch</option><option value="rec709">Rec.709 (gewoon)</option><option value="slog3">S-Log3</option><option value="none">geen grade</option></select></label>
          <label>Volgorde<select id="cOrder"><option value="best">beste shots</option><option value="story" ${s.order || s.category === "food" ? "selected" : ""}>verhaal / kookvolgorde</option></select></label>
          <label>Grid Flow<select id="cGrid"><option value="auto">automatisch (1×, niet bij eten/kleding)</option><option value="off">uit</option></select></label>
        </div>
        <details><summary>Meer opties</summary><div class="form" style="margin-top:8px">
          <label>Titelshot<input id="cTitleShot" placeholder="C0083:60"></label>
          <label>Laatste shot<input id="cFinalShot" placeholder="C0084:10"></label>
          <label>Accentkleur<input id="cAccent" placeholder="#E70002"></label>
          <label>Liedje (deel van de naam)<input id="cSong" placeholder="${esc(s.song || "")}"></label>
          <label>Witte kaarten<select id="cCard"><option>auto</option><option>on</option><option>off</option></select></label>
          <label>Zwart-wit shot<select id="cBw"><option>auto</option><option>off</option></select></label>
        </div></details>
        <div class="row" style="margin-top:12px"><button id="cPlan">Plan maken</button>
          <span class="muted small">Maakt een nieuw plan + storyboard. Renderen gebeurt pas na je goedkeuring.</span></div>
      </div>
      <div class="card"><h2>Goedkeuren & renderen</h2>
        ${!c.has_plan ? '<div class="muted">Nog geen plan.</div>' : `
        <div class="banner ${approved ? "ok" : "warn"}" style="margin-bottom:10px">${approved ? `Goedgekeurd: “${esc(appr.note)}”` :
          appr && appr.status === "approved" ? "Het plan is gewijzigd na je goedkeuring. Keur het opnieuw goed." : "Wacht op je goedkeuring."}</div>
        <label>Wat keur je goed (in je eigen woorden)<input id="cNote" placeholder="bijv. ja, render met B"></label>
        <div class="row" style="margin-top:10px">
          <button class="dark" id="cApprove">Goedkeuren</button>
          <button id="cRender" ${approved ? "" : "disabled"}>Renderen</button>
          <button class="ghost" id="cPreview">Voorbeeld (half)</button>
          <button class="ghost" id="cQa">QA</button></div>
        <p class="muted small">Renderen gebruikt de look en kleur hierboven.</p>`}
      </div>
      ${c.qa ? `<div class="card"><h2>Laatste QA</h2>${qaView(c.qa.qa)}</div>` : ""}
    </div>
    <div class="stack">
      ${c.has_plan ? `
      <div class="card"><div class="row"><h2 style="margin:0">Plan</h2><span class="spacer"></span>
        <span class="tag">${c.shots.length} shots</span><span class="tag">${(+c.duration).toFixed(1)} s</span>${c.music ? `<span class="tag">♫ ${esc(c.music)}</span>` : ""}
        <span class="tag ok">${counts.ok || 0} ok</span>${counts.warn ? `<span class="tag warn">${counts.warn} let op</span>` : ""}${counts.fail ? `<span class="tag fail">${counts.fail} fout</span>` : ""}
        ${c.sheet ? `<a class="tag blue" target="_blank" href="${fileUrl(c.sheet)}">storyboard ↗</a>` : ""}</div>
        <details style="margin-top:8px"><summary>Stijlchecks</summary><div class="checks">${c.checks.map((x) =>
          `<div><span class="tag ${x.status === "ok" ? "ok" : x.status}">${x.status}</span><b>${esc(x.rule)}</b><span class="muted">${esc(x.msg)}</span></div>`).join("")}</div></details>
      </div>
      <div class="card"><div class="row" style="margin-bottom:12px"><h2 style="margin:0">Shots</h2><span class="spacer"></span>
        <span class="muted small">Schrijf per shot wat anders moet</span><button class="sm" id="cSaveComments">Opmerkingen opslaan</button></div>
        <div class="shots">${c.shots.map((x) => shotCard(x, c.comments[x.n] || "")).join("")}</div></div>` : '<div class="empty">Maak links een plan om de shots te zien.</div>'}
      ${cineExports.length ? `<div class="card"><h2>Renders</h2><div class="media-grid">${cineExports.slice(0, 4).map(videoCard).join("")}</div></div>` : ""}
    </div>
  </div>`;
  $("#cLook").value = "reference_film";
  $("#cPlan").onclick = async () => {
    if (c.has_plan && appr?.status === "approved" && !(await confirmDlg("Nieuw plan maken?", "Het huidige goedgekeurde plan wordt vervangen. Je moet het nieuwe plan opnieuw goedkeuren.", "Nieuw plan")))
      return;
    const v = (id) => $(id).value.trim();
    startJob(`/api/projects/${enc(P.name)}/cine/plan`, {
      title: v("#cTitle"), length: v("#cLen"), seed: v("#cSeed"), look: v("#cLook"), grade: v("#cGrade"), order: v("#cOrder"),
      grid_flow: v("#cGrid"), title_shot: v("#cTitleShot"), final_shot: v("#cFinalShot"), accent: v("#cAccent"), song: v("#cSong"),
      card: v("#cCard"), bw: v("#cBw") }, { onDone: reload });
  };
  if (!c.has_plan) return;
  const grade = () => ({ look: $("#cLook").value, grade: $("#cGrade").value });
  $("#cApprove").onclick = () => {
    const note = $("#cNote").value.trim();
    if (!note) return toast("Schrijf in je eigen woorden wat je goedkeurt", "err");
    startJob(`/api/projects/${enc(P.name)}/cine/approve`, { note }, { onDone: reload });
  };
  $("#cRender").onclick = () => startJob(`/api/projects/${enc(P.name)}/cine/render`, grade(), { onDone: reload });
  $("#cPreview").onclick = () => startJob(`/api/projects/${enc(P.name)}/cine/preview`, grade(), { onDone: reload });
  $("#cQa").onclick = () => startJob(`/api/projects/${enc(P.name)}/cine/qa`, grade(), { onDone: reload });
  $("#cSaveComments").onclick = () => guard(async () => {
    const comments = {};
    document.querySelectorAll(".shot textarea").forEach((t) => (comments[t.dataset.n] = t.value));
    const r = await api(`/api/projects/${enc(P.name)}/comments`, { method: "PUT", body: { comments } });
    toast(`${r.saved} opmerking(en) opgeslagen. Claude leest ze uit cine_montage/comments.json.`, "ok");
  });
  document.querySelectorAll(".shot textarea").forEach((t) => (t.oninput = () => t.closest(".shot").classList.toggle("has-comment", !!t.value.trim())));
}
function shotCard(x, comment) {
  const tr = x.transition !== "T_HARD" ? `<span class="tag ${x.transition === "T_GRID_FLOW" ? "red" : "blue"}">${x.transition.replace("T_", "").toLowerCase()}</span>` : "";
  const fx = x.treatment.map((t) => `<span class="tag">${t.replace("D_", "").replace("CARD_WHITE", "witte kaart").toLowerCase()}</span>`).join("");
  return `<div class="shot ${comment ? "has-comment" : ""}" title="${esc(x.why)}">
    <div class="frame" style="${x.frame ? `background-image:url('${fileUrl(x.frame)}')` : ""}"><span class="n">${x.n}</span></div>
    <div class="meta"><span>${x.start.toFixed(1)}–${x.end.toFixed(1)}s</span><span>· ${esc(x.clip)}</span>${x.role === "title" ? '<span class="tag red">titel</span>' : ""}${x.role === "final" ? '<span class="tag">slot</span>' : ""}${tr}${fx}</div>
    <textarea data-n="${x.n}" placeholder="opmerking…">${esc(comment)}</textarea></div>`;
}
function qaView(q) {
  if (!q) return "";
  const ok = !q.problems?.length;
  return `<div class="banner ${ok ? "ok" : "warn"}">${ok ? "Geen problemen" : esc(q.problems.join("; "))}</div>
    <dl class="kv" style="margin-top:10px"><dt>Formaat</dt><dd>${q.size?.join("×")} · ${q.fps} fps · ${q.duration}s</dd>
    <dt>Loudness</dt><dd>${q.lufs} LUFS · piek ${q.true_peak_dbfs} dBTP</dd><dt>Zwart / bevroren</dt><dd>${q.black?.length || 0} / ${q.frozen?.length || 0}</dd></dl>`;
}
function videoCard(f) {
  return `<div class="stack" style="gap:6px"><video controls preload="metadata" src="${fileUrl(f.path)}"></video>
    <div class="row small"><span class="nm">${esc(f.name)}</span><span class="spacer"></span><span class="muted">${mb(f.size)} · ${when(f.mtime)}</span>
    <a class="tag blue" href="${fileUrl(f.path)}" download="${esc(f.name)}">download</a></div></div>`;
}

function tabAutoedit() {
  const s = P.settings || {};
  $("#tab").innerHTML = `
  <div class="grid cols-2">
    <div class="stack">
      <div class="card"><h2>Bouwen in DaVinci Resolve</h2>
        <p class="muted small" style="margin-top:0">Analyse → edit in Resolve → render → wachtrij voor goedkeuring. Resolve moet open staan.</p>
        <div class="form"><label>Titel<input id="aTitle" value="${esc(s.title || "")}"></label>
          <label>Liedje<input id="aSong" placeholder="${esc(s.song || "uit project.yaml / music/")}"></label>
          <label>Varianten (hook-test)<select id="aVar"><option>A</option><option>AB</option><option>ABC</option></select></label>
          <label>Seed<input id="aSeed" type="number" placeholder="willekeurig"></label></div>
        <div class="row" style="margin-top:12px"><button id="aBuild">Bouwen</button>
          <span class="muted small">Vorm (${esc(s.aspect || "16:9")}) en categorie komen uit Instellingen.</span></div></div>
      <div class="card"><h2>Clips</h2><div class="row"><button class="dark" id="aAnalyze">Clips analyseren</button>
        <input id="aSince" type="date" style="width:auto"><button class="dark" id="aImport">Importeren van SD-kaart</button></div>
        <p class="muted small">Import kopieert nieuwe clips van de Sony-kaart (+ XML) naar clips/.</p></div>
      <div class="card"><h2>Explainer</h2><p class="muted small" style="margin-top:0">Stap-voor-stap video uit script.yaml in het project.</p>
        <button class="dark" id="aExpl">Explainer maken</button></div>
    </div>
    <div class="card"><h2>Exports</h2>${P.exports.filter((f) => f.name.endsWith(".mp4") && !f.name.startsWith("cine_montage")).length
      ? `<div class="media-grid">${P.exports.filter((f) => f.name.endsWith(".mp4") && !f.name.startsWith("cine_montage")).slice(0, 6).map(videoCard).join("")}</div>`
      : '<div class="muted">Nog geen AutoEdit-exports.</div>'}</div>
  </div>`;
  const n = enc(P.name);
  $("#aBuild").onclick = () => startJob(`/api/projects/${n}/autoedit`, { title: $("#aTitle").value, song: $("#aSong").value, variants: $("#aVar").value, seed: $("#aSeed").value }, { onDone: reload });
  $("#aAnalyze").onclick = () => startJob(`/api/projects/${n}/analyze`);
  $("#aImport").onclick = () => startJob(`/api/projects/${n}/import`, { since: $("#aSince").value }, { onDone: reload });
  $("#aExpl").onclick = () => startJob(`/api/projects/${n}/explainer`, {}, { onDone: reload });
}

async function tabAI() {
  const models = await api("/api/ai-models");
  $("#tab").innerHTML = `
  <div class="grid cols-2"><div class="card"><h2>AI-shot maken</h2>
    <div class="form"><label class="full">Prompt (beschrijf ook de camerabeweging)<textarea id="iPrompt" rows="4"></textarea></label>
      <label>Model<select id="iModel">${models.map((m) => `<option value="${m.id}">${m.local ? "🖥 " : "💳 "}${m.id}</option>`).join("")}</select></label>
      <label>Seconden<input id="iSec" type="number" min="2" max="10" value="5"></label>
      <label>Vorm<select id="iAspect"><option>16:9</option><option>9:16</option><option>1:1</option></select></label>
      <label>Rol in het verhaal<select id="iRole"><option>establish</option><option>detail</option><option>subject</option><option>close</option><option>hero_wide</option></select></label></div>
    <p class="muted small" id="iNote"></p>
    <div class="row"><button class="dark" id="iQuote">Prijs vragen</button><button id="iGen">Maken</button></div>
    <p class="muted small">🖥 = je eigen GPU (gratis, 30–45 min). 💳 = Muapi, kost tegoed: eerst de prijs, dan bevestigen. Het budget per project verander je alleen zelf in project.yaml.</p>
  </div><div class="card"><h2>Modellen</h2><div class="files">${models.map((m) => `<div class="file"><span class="nm"><b>${m.id}</b> <span class="muted">${esc(m.note)}</span></span>${m.local ? '<span class="tag ok">gratis</span>' : '<span class="tag warn">betaald</span>'}</div>`).join("")}</div></div></div>`;
  const body = () => ({ prompt: $("#iPrompt").value, model: $("#iModel").value, seconds: $("#iSec").value, aspect: $("#iAspect").value, role: $("#iRole").value });
  const isLocal = () => $("#iModel").value.startsWith("local");
  const note = () => ($("#iNote").textContent = isLocal() ? "Lokaal model: geen kosten." : "Betaald model: vraag eerst de prijs.");
  $("#iModel").onchange = note; note();
  let quoted = null;
  $("#iQuote").onclick = () => startJob(`/api/projects/${enc(P.name)}/ai/quote`, body(), { onDone: (j, log) => {
    const m = log.match(/\$\s?(\d+\.\d\d)/); quoted = m ? { price: m[1], ...body() } : null;
    $("#iNote").textContent = m ? `Prijs: $${m[1]} — ${log.trim().split("\n").pop()}` : "Geen prijs gevonden, zie de log.";
  } });
  $("#iGen").onclick = async () => {
    const b = body();
    if (!isLocal()) {
      if (!quoted || quoted.prompt !== b.prompt || quoted.model !== b.model || quoted.seconds !== b.seconds) return toast("Vraag eerst de prijs voor precies deze shot", "err");
      if (!(await confirmDlg("AI-shot betalen?", `<p>${esc(b.model)}, ${b.seconds}s: <b>$${quoted.price}</b> van je Muapi-tegoed.</p>`, `Ja, $${quoted.price} betalen`))) return;
      b.confirmed_price = quoted.price;
    }
    startJob(`/api/projects/${enc(P.name)}/ai/generate`, b, { onDone: reload });
  };
}

function tabFiles() {
  const vids = P.exports.filter((f) => /\.(mp4|mov)$/i.test(f.name));
  $("#tab").innerHTML = `
  <div class="stack">
    <div class="card"><h2>Exports (${P.exports.length})</h2>${vids.length ? `<div class="media-grid">${vids.map(videoCard).join("")}</div>` : '<div class="muted">Nog niets gerenderd.</div>'}
      ${P.exports.filter((f) => /\.(jpg|png)$/i.test(f.name)).map((f) => `<a class="tag blue" target="_blank" href="${fileUrl(f.path)}">${esc(f.name)}</a>`).join(" ")}</div>
    <div class="grid cols-2">
      <div class="card"><h2>Clips (${P.clips.length})</h2>${P.clips_link && !P.clips_link.startsWith(P.path) ? `<p class="muted small">Gekoppeld aan ${esc(P.clips_link)}</p>` : ""}
        <div class="files">${P.clips.map((f) => `<div class="file"><span class="nm">${esc(f.name)}</span><span class="muted">${mb(f.size)}</span>
          <a class="tag blue" target="_blank" href="${fileUrl(f.path)}">bekijk</a></div>`).join("") || '<div class="muted">Geen clips.</div>'}</div></div>
      <div class="card"><h2>Muziek in dit project</h2>${P.music.map((f) => `<div class="stack" style="gap:4px;margin-bottom:10px"><span class="small">${esc(f.name)}</span><audio controls preload="none" src="${fileUrl(f.path)}"></audio></div>`).join("") || '<div class="muted">Geen eigen muziek, het liedje uit Instellingen wordt gebruikt.</div>'}</div>
    </div></div>`;
}

function tabSettings() {
  $("#tab").innerHTML = `<div class="grid cols-2"><div class="card"><h2>project.yaml</h2>
    <textarea id="sYaml" class="mono" rows="22" spellcheck="false">${esc(P.yaml)}</textarea>
    <div class="row" style="margin-top:10px"><button id="sSave">Opslaan</button><span class="muted small">${esc(P.path)}</span></div></div>
    <div class="card"><h2>Uitleg</h2><dl class="kv">
      <dt>title</dt><dd>titel in de video</dd><dt>category</dt><dd>food / fashion / travel / fitness / lifestyle — bij food en fashion geen Grid Flow</dd>
      <dt>aspect</dt><dd>null = 16:9, of "9:16" voor Reels/TikTok</dd><dt>song</dt><dd>deel van de naam van een liedje in je muziekmap</dd>
      <dt>order</dt><dd>clips in verhaalvolgorde, NAAM:a-b = alleen die seconden</dd><dt>ai_budget_usd</dt><dd>alleen omlaag vanuit de app; omhoog doe je zelf</dd></dl></div></div>`;
  $("#sSave").onclick = () => guard(async () => {
    await api(`/api/projects/${enc(P.name)}/settings`, { method: "PUT", body: { yaml: $("#sYaml").value } });
    toast("Opgeslagen", "ok");
  });
}

// ------------------------------------------------------------------ queue
async function queue() {
  const q = await api("/api/queue");
  const stat = { pending_approval: ["warn", "wacht op jou"], approved: ["ok", "goedgekeurd, gepland"], posted: ["blue", "gepost"], failed: ["fail", "mislukt"] };
  main.innerHTML = `<div class="head"><div><div class="crumb">AutoEdit</div><h1>Wachtrij</h1></div><span class="spacer"></span>
    <span class="muted small">Niets gaat online zonder jouw klik.</span></div>
    ${q.length ? `<div class="stack">${q.map((e) => {
      const [k, l] = stat[e.status] || ["", e.status];
      return `<div class="card"><div class="grid cols-2"><div>${e.video_exists ? `<video controls preload="metadata" src="${fileUrl(e.video)}" ${e.cover_exists ? `poster="${fileUrl(e.cover)}"` : ""}></video>`
        : `<div class="empty">Bestand niet meer gevonden<br><span class="small">${esc(e.video || "")}</span></div>`}</div>
        <div class="stack"><div class="row"><b>${esc(e.meta?.hook || e.id)}</b><span class="tag ${k}">${l}</span><span class="spacer"></span><span class="muted small">${esc(e.id)} · ${esc(e.style)}</span></div>
        ${Object.entries(e.options || {}).map(([plat, opts]) => `<div><h3>${esc(plat)} <span class="muted small">${esc(e.scheduled?.[plat] || "")}</span></h3>
          ${opts.map((o, i) => `<label style="flex-direction:row;gap:8px;align-items:flex-start;color:var(--text);margin-bottom:6px"><input type="radio" style="width:auto" name="${e.id}-${plat}" data-e="${e.id}" data-p="${plat}" value="${i}" ${(e.chosen?.[plat] ?? 0) === i ? "checked" : ""}>
            <span class="small">${esc(o.caption || o.text || JSON.stringify(o))}</span></label>`).join("")}</div>`).join("")}
        ${e.results && Object.keys(e.results).length ? `<pre class="out">${esc(JSON.stringify(e.results, null, 1))}</pre>` : ""}
        <div class="row">${e.status === "pending_approval" ? `<button data-approve="${e.id}">Goedkeuren (post op gepland tijdstip)</button>` : ""}
          ${["approved", "pending_approval"].includes(e.status) ? `<button class="dark" data-post="${e.id}">Nu posten</button>` : ""}</div></div></div></div>`;
    }).join("")}</div>` : '<div class="empty">De wachtrij is leeg. AutoEdit-builds komen hier om goed te keuren.</div>'}`;
  document.querySelectorAll("input[type=radio][data-e]").forEach((r) => (r.onchange = () =>
    guard(() => api(`/api/queue/${r.dataset.e}/choose`, { method: "POST", body: { platform: r.dataset.p, index: +r.value } }))));
  document.querySelectorAll("[data-approve]").forEach((b) => (b.onclick = async () => {
    if (await confirmDlg("Goedkeuren?", "De video wordt op het geplande tijdstip gepost met de gekozen captions.", "Goedkeuren"))
      startJob(`/api/queue/${b.dataset.approve}/approve`, { caption: 0 }, { onDone: reload });
  }));
  document.querySelectorAll("[data-post]").forEach((b) => (b.onclick = async () => {
    if (await confirmDlg("Nu posten?", "<p>De video gaat <b>nu</b> online met de gekozen captions.</p>", "Ja, nu posten"))
      startJob(`/api/queue/${b.dataset.post}/post`, {}, { onDone: reload });
  }));
}

// ------------------------------------------------------------------ music
async function music() {
  const list = await api("/api/music");
  main.innerHTML = `<div class="head"><div><div class="crumb">AutoEdit</div><h1>Muziek</h1></div><span class="spacer"></span>
    <label class="dark" style="flex-direction:row"><input type="file" id="mUp" accept="audio/*" multiple hidden><button class="dark" onclick="this.previousElementSibling.click()">+ Uploaden</button></label></div>
    <p class="muted small">Liedjes uit een referentievideo zijn prima voor privé, maar check het copyright voordat je post.</p>
    <div class="media-grid">${list.map((f) => `<div class="card stack" style="gap:8px"><b class="small">${esc(f.name)}</b>
      <audio controls preload="none" src="${fileUrl(f.path)}"></audio><span class="muted small">${mb(f.size)}</span></div>`).join("") || '<div class="empty">Geen muziek.</div>'}</div>`;
  $("#mUp").onchange = (ev) => guard(async () => {
    const fd = new FormData();
    [...ev.target.files].forEach((f) => fd.append("file", f));
    const r = await api("/api/music", { method: "POST", body: fd });
    toast(`${r.saved.length} liedje(s) toegevoegd`, "ok"); reload();
  });
}

// ------------------------------------------------------------------ tools & insights
async function tools() {
  const rep = await api("/api/report").catch((e) => ({ text: e.message }));
  const t = [["stats", "Instagram-statistieken ophalen", "haalt cijfers op en leert je beste posttijden"],
    ["ai-balance", "Muapi-tegoed", "hoeveel AI-tegoed je nog hebt"], ["ai-models", "AI-modellen + prijzen", "live prijzen"],
    ["sfx", "SFX-bibliotheek", "geluiden per categorie"], ["optimize", "Resolve soepeler maken", "proxies, render cache"],
    ["validate", "Editor controleren", "stijl-DNA, browser, ffmpeg, documentatie"], ["post-due", "Geplande posts versturen", "post goedgekeurde video's waarvan de tijd gekomen is"]];
  main.innerHTML = `<div class="head"><div><div class="crumb">AutoEdit</div><h1>Inzichten & tools</h1></div></div>
  <div class="grid cols-2"><div class="stack">
    <div class="card"><h2>Contentideeën</h2><div class="form"><label>Stijl<select id="tStyle"><option>lifestyle</option><option>travel</option><option>food</option><option>fashion</option><option>fitness</option></select></label>
      <label>Weken<input id="tWeeks" type="number" min="1" max="8" value="2"></label></div>
      <button style="margin-top:10px" id="tIdeas">Ideeën maken</button></div>
    <div class="card"><h2>Tools</h2><div class="files">${t.map(([k, l, d]) => `<div class="file"><span class="nm"><b>${l}</b> <span class="muted">${d}</span></span><button class="dark sm" data-tool="${k}">Start</button></div>`).join("")}</div></div>
  </div><div class="card"><h2>Wat werkt het best</h2><pre class="out">${esc(rep.text || "Nog geen gegevens.")}</pre></div></div>`;
  document.querySelectorAll("[data-tool]").forEach((b) => (b.onclick = () => startJob(`/api/tools/${b.dataset.tool}`)));
  $("#tIdeas").onclick = () => startJob("/api/tools/ideas", { style: $("#tStyle").value, weeks: $("#tWeeks").value });
}

// ------------------------------------------------------------------ jobs
async function jobs(id) {
  if (id) {
    main.innerHTML = `<div class="head"><div><div class="crumb"><a href="#/jobs">Taken</a></div><h1 id="jTitle">Taak</h1></div></div><pre class="out" id="jLog" style="max-height:70vh"></pre>`;
    const j = await api(`/api/jobs/${id}?since=0`);
    $("#jTitle").textContent = `${j.label} (${j.status})`;
    $("#jLog").textContent = j.log.join("\n");
    if (["queued", "running"].includes(j.status)) watchJob(id, () => route());
    return;
  }
  const list = await api("/api/jobs");
  const st = { queued: "warn", running: "blue", done: "ok", failed: "fail", cancelled: "" };
  main.innerHTML = `<div class="head"><div><div class="crumb">AutoEdit Studio</div><h1>Taken</h1></div></div>
    ${list.length ? `<div class="card" style="padding:0;overflow:auto"><table class="jobs-table"><tr><th>Wat</th><th>Project</th><th>Status</th><th>Gestart</th><th>Duur</th></tr>
    ${list.map((j) => `<tr onclick="location.hash='#/jobs/${j.id}'"><td>${esc(j.label)}</td><td>${esc(j.project || "")}</td><td><span class="tag ${st[j.status]}">${j.status}</span></td>
      <td class="muted">${when(j.created)}</td><td class="muted">${j.started ? Math.round(((j.ended || Date.now() / 1000) - j.started)) + " s" : ""}</td></tr>`).join("")}</table></div>`
      : '<div class="empty">Nog geen taken sinds de app gestart is.</div>'}`;
}

loadStatus(); setInterval(loadStatus, 20000); refreshBadge(); route();
