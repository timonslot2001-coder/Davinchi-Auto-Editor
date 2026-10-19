"""Local dashboard: http://127.0.0.1:5055 — build, set stabilization per clip, preview, pick caption, approve, post."""
from __future__ import annotations

import threading
import traceback
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file

from . import analyze, performance, pipeline, publish
from .config import load

app = Flask(__name__)
JOB = {"running": False, "log": [], "result": None}


def _log(*a, **k):
    msg = " ".join(str(x) for x in a)
    for tag in ("[bold]", "[/]", "[cyan]", "[yellow]", "[red]", "[green]"):
        msg = msg.replace(tag, "")
    JOB["log"].append(msg.strip())
    JOB["log"] = JOB["log"][-300:]


@app.get("/")
def index():
    return PAGE


@app.get("/api/state")
def state():
    cfg = load()
    return jsonify({"styles": {k: v.get("label", k) for k, v in cfg.styles.items()},
                    "default_style": cfg.get("default_style"), "drop": cfg.get("paths.drop_folder"),
                    "queue": list(reversed(publish.entries()))[:30], "job": JOB,
                    "stats": performance.report()})


@app.get("/api/music")
def api_music():
    return jsonify(pipeline.list_music(load()))


@app.post("/api/music")
def api_music_upload():
    cfg = load()
    folder = Path(cfg.get("paths.music_folder"))
    folder.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in request.files.getlist("file"):
        name = Path(f.filename).name
        if Path(name).suffix.lower() in analyze.AUDIO_EXT:
            f.save(folder / name)
            saved.append(name)
    return jsonify({"saved": saved, "music": pipeline.list_music(cfg)})


@app.post("/api/analyze")
def api_analyze():
    folder = Path(request.json["folder"])
    cfg = load()
    thr = cfg.get("stabilization.shake_threshold", 0.35)
    videos, _ = analyze.find_media(folder)
    out = []
    for v in videos:
        c = analyze.analyze_clip(v)
        out.append({"name": c.name, "duration": c.duration, "shake": c.shake, "stabilize": c.shake >= thr,
                    "rejected": c.rejected_reason, "speech": c.has_speech})
    return jsonify(out)


@app.post("/api/build")
def api_build():
    if JOB["running"]:
        return jsonify({"error": "a build is already running"}), 409
    body = request.json
    cfg = load()
    cfg.raw.setdefault("stabilization", {})["overrides"] = body.get("stabilize", {})
    if body.get("bass") not in (None, ""):
        cfg.raw.setdefault("audio", {})["music_bass_db"] = float(body["bass"])

    def work():
        JOB.update(running=True, log=[], result=None)
        try:
            JOB["result"] = pipeline.run(cfg, body["folder"], None, body.get("variants", "A"),
                                         body.get("music") or None, stab_mode="auto",
                                         location=body.get("location") or None, title=body.get("title") or None,
                                         category=body.get("category") or None, aspect=body.get("aspect") or None,
                                         log=_log)
        except BaseException as e:                       # SystemExit included: show it in the log
            _log(f"ERROR: {e}")
            _log(traceback.format_exc()[-800:])
        finally:
            JOB["running"] = False

    threading.Thread(target=work, daemon=True).start()
    return jsonify({"ok": True})


@app.get("/media/<entry_id>/<kind>")
def media(entry_id, kind):
    e = publish.get(entry_id)
    if not e:
        abort(404)
    path = e["video"] if kind == "video" else e.get("cover")
    if not path or not Path(path).exists():
        abort(404)
    return send_file(path)


@app.post("/api/queue/<entry_id>")
def api_queue(entry_id):
    body = request.json
    e = publish.get(entry_id) or abort(404)
    changes = {}
    if "chosen" in body:
        changes["chosen"] = body["chosen"]
    if "options" in body:                                # edited caption text
        changes["options"] = body["options"]
    if "scheduled" in body:
        changes["scheduled"] = body["scheduled"]
    if body.get("action") == "approve":
        changes["status"] = "approved"
    if body.get("action") == "reject":
        changes["status"] = "rejected"
    e = publish.update(entry_id, **changes)
    if body.get("action") == "post_now":
        e = publish.post_entry(entry_id, force_now=True)
    return jsonify(e)


def serve(port: int = 5055):
    print(f"Dashboard: http://127.0.0.1:{port}")
    app.run("127.0.0.1", port, debug=False, threaded=True)


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AutoEdit</title><style>
:root{--bg:#0f1012;--card:#18191c;--line:#2a2c30;--txt:#e9e9ea;--mut:#9a9ca1;--acc:#ffd400;--ok:#3ecf8e;--bad:#ff5d5d}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--txt)}
header{display:flex;align-items:center;gap:12px;padding:16px 24px;border-bottom:1px solid var(--line)}
header b{font-size:18px}header span{color:var(--mut)}main{display:grid;grid-template-columns:420px 1fr;gap:20px;padding:20px 24px}
@media(max-width:900px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);margin:0 0 12px}
label{display:block;color:var(--mut);font-size:12px;margin:10px 0 4px}input,select,textarea{width:100%;background:#0d0e10;color:var(--txt);border:1px solid var(--line);border-radius:8px;padding:8px}
button{background:var(--acc);color:#111;border:0;border-radius:8px;padding:8px 14px;font-weight:600;cursor:pointer}button.ghost{background:transparent;color:var(--txt);border:1px solid var(--line)}
button:disabled{opacity:.5}.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
table{width:100%;border-collapse:collapse;font-size:13px}td{padding:5px 4px;border-top:1px solid var(--line)}
.bar{height:6px;border-radius:3px;background:#2a2c30;overflow:hidden;width:80px}.bar i{display:block;height:100%;background:var(--acc)}
pre{background:#0d0e10;border-radius:8px;padding:10px;max-height:260px;overflow:auto;font-size:12px;white-space:pre-wrap}
.q{display:grid;grid-template-columns:200px 1fr;gap:16px}video{width:200px;border-radius:10px;background:#000}
.opt{border:1px solid var(--line);border-radius:8px;padding:8px;margin:6px 0;cursor:pointer}.opt.sel{border-color:var(--acc)}
.pill{font-size:11px;padding:2px 8px;border-radius:99px;border:1px solid var(--line);color:var(--mut)}.pill.approved{color:var(--acc);border-color:var(--acc)}.pill.posted{color:var(--ok);border-color:var(--ok)}
.err{color:var(--bad)}
</style></head><body>
<header><b>AutoEdit</b><span>DaVinci auto editor · TikTok + Instagram</span></header>
<main><section>
<div class="card"><h2>1 · Footage</h2>
<label>Folder with clips</label><input id="folder" placeholder="C:\Users\...\Videos\Shoot">
<div class="row" style="margin-top:10px"><button onclick="analyse()">Analyse clips</button></div>
<div id="clips"></div></div>
<div class="card"><h2>2 · Style</h2>
<label>Category (only for captions & hashtags — the edit style is always your house style)</label>
<select id="category"><option value="">none</option><option>fitness</option><option>travel</option><option>fashion</option><option>lifestyle</option></select>
<label>Shape</label><select id="aspect"><option value="">house style default</option><option>16:9</option><option>9:16</option></select>
<label>Variants (A/B hooks)</label><select id="variants"><option>A</option><option selected>AB</option><option>ABC</option></select>
<label>Music</label><div class=row><select id="music" style="flex:1"></select>
<label class="ghost" style="margin:0;padding:8px 12px;border:1px solid var(--line);border-radius:8px;cursor:pointer;color:var(--txt)">+ add song<input type=file id="songfile" accept="audio/*" multiple hidden onchange="upload(this.files)"></label></div>
<div id="drop" style="margin-top:6px;border:1px dashed var(--line);border-radius:8px;padding:10px;text-align:center;color:var(--mut);font-size:12px">or drop an mp3/wav here</div>
<label>Bass in the song: <b id="bassv">-4</b> dB</label><input id="bass" type=range min=-12 max=4 step=1 value=-4 oninput="$('bassv').textContent=this.value">
<label>Title (optional, small spaced text over the intro)</label><input id="title" placeholder="e.g. UTRECHT">
<label>Location (for captions, optional)</label><input id="location">
<div class="row" style="margin-top:12px"><button id="go" onclick="build()">Build in Resolve + render</button></div>
<pre id="log"></pre></div>
<div class="card"><h2>Stats</h2><pre id="stats"></pre></div>
</section><section><div class="card"><h2>3 · Review & post</h2><div id="queue"></div></div></section></main>
<script>
let clips=[],state={},lastQ='';
const $=id=>document.getElementById(id);
async function api(u,b){const r=await fetch(u,b?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}:{});return r.json()}
async function refresh(){state=await api('/api/state');

 $('log').textContent=state.job.log.join('\n');$('go').disabled=state.job.running;$('stats').textContent=state.stats;const q=JSON.stringify(state.queue);if(q!==lastQ){lastQ=q;renderQueue()}}
async function analyse(){$('clips').innerHTML='analysing…';clips=await api('/api/analyze',{folder:$('folder').value});
 $('clips').innerHTML='<table>'+clips.map((c,i)=>`<tr><td>${c.name}${c.rejected?` <span class=err>(${c.rejected})</span>`:''}</td><td>${c.duration.toFixed(1)}s</td>
 <td><div class=bar title="shake ${c.shake}"><i style="width:${c.shake*100}%"></i></div></td>
 <td><label style="margin:0;color:var(--txt)"><input type=checkbox style="width:auto" ${c.stabilize?'checked':''} onchange="clips[${i}].stabilize=this.checked"> stabilize</label></td></tr>`).join('')+'</table>'}
async function build(){const stab={};clips.forEach(c=>stab[c.name]=c.stabilize);
 await api('/api/build',{folder:$('folder').value,category:$('category').value,aspect:$('aspect').value,variants:$('variants').value,music:$('music').value,location:$('location').value,title:$('title').value,bass:$('bass').value,stabilize:stab});refresh()}
async function loadMusic(sel){const m=await api('/api/music');const s=$('music');s.innerHTML='';s.add(new Option('random from music folder',''));s.add(new Option('no music','none'));m.forEach(x=>s.add(new Option(x,x)));if(sel)s.value=sel}
async function upload(files){const fd=new FormData();[...files].forEach(f=>fd.append('file',f));const r=await fetch('/api/music',{method:'POST',body:fd}).then(r=>r.json());await loadMusic(r.saved[0])}
const dz=document.getElementById('drop');dz.ondragover=e=>{e.preventDefault();dz.style.borderColor='var(--acc)'};dz.ondragleave=()=>dz.style.borderColor='';dz.ondrop=e=>{e.preventDefault();dz.style.borderColor='';upload(e.dataTransfer.files)};
loadMusic();
function renderQueue(){$('queue').innerHTML=state.queue.map(e=>`<div class="card q"><div><video src="/media/${e.id}/video" controls preload=metadata poster="/media/${e.id}/cover"></video></div><div>
 <div class=row><b>${e.style} · ${e.meta.variant||''}</b><span class="pill ${e.status}">${e.status}</span><span class=pill>${e.id}</span></div>
 <div style="color:var(--mut);margin:4px 0">Hook: ${e.meta.hook||''}</div>
 ${Object.entries(e.options).map(([p,opts])=>`<label>${p} · scheduled <input style="width:auto" type=datetime-local value="${(e.scheduled[p]||'').slice(0,16)}" onchange="sched('${e.id}','${p}',this.value)"></label>
   ${opts.map((o,i)=>`<div class="opt ${e.chosen[p]==i?'sel':''}" onclick="choose('${e.id}','${p}',${i})">${o.full.replace(/\n/g,'<br>')}</div>`).join('')}
   ${e.results[p]?`<div class="${e.results[p].ok?'':'err'}">${e.results[p].ok?('✓ '+(e.results[p].url||e.results[p].status||'posted')):e.results[p].error}</div>`:''}`).join('')}
 <div class=row style="margin-top:10px">${e.status=='pending_approval'?`<button onclick="act('${e.id}','approve')">Approve (posts at scheduled time)</button><button class=ghost onclick="act('${e.id}','reject')">Reject</button>`:''}
 ${['approved','partially_posted'].includes(e.status)?`<button onclick="if(confirm('Post now?'))act('${e.id}','post_now')">Post now</button>`:''}</div></div></div>`).join('')||'<span style="color:var(--mut)">Nothing in the queue yet.</span>'}
async function choose(id,p,i){const e=state.queue.find(x=>x.id==id);e.chosen[p]=i;await api('/api/queue/'+id,{chosen:e.chosen});refresh()}
async function sched(id,p,v){const e=state.queue.find(x=>x.id==id);e.scheduled[p]=v;await api('/api/queue/'+id,{scheduled:e.scheduled})}
async function act(id,a){await api('/api/queue/'+id,{action:a});refresh()}
refresh();setInterval(refresh,3000);
</script></body></html>"""
