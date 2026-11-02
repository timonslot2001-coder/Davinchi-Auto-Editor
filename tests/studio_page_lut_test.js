// The Studio page's grade maths and request texts, run in node (no browser).
// usage: node tests/studio_page_lut_test.js      (fixture: python tests/make_lut_fixture.py)
// Optional: PYTHON=<python with the repo deps> also parses every request text with webapp/studio.py parse().
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { spawnSync } = require("child_process");

const REPO = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(REPO, "webapp/artifact/studio.html"), "utf8");
const m = html.match(/<script id="grade-math">([\s\S]*?)<\/script>/);
if (!m) throw new Error("no <script id=\"grade-math\"> in studio.html");
const ctx = { globalThis: null };
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(m[1], ctx);
const { parseCube, sample, gradePixel, requestText } = ctx.StudioMath;
if (typeof ctx.gradePixel !== "function") throw new Error("gradePixel not exposed on globalThis");

let fails = 0;
const check = (ok, msg) => { if (!ok) { fails++; console.error("FAIL", msg); } };

// ---- 1. two-stage grade vs numpy (autoedit/grade.py apply_cube), max error <= 2/255
const fx = JSON.parse(fs.readFileSync(path.join(REPO, "tests/fixtures/studio_lut.json"), "utf8"));
const cubes = {};
for (const [k, t] of Object.entries(fx.cubes)) cubes[k] = parseCube(t);
check(cubes.conv.n === fx.size, "cube size");
let maxErr = 0;
for (const c of fx.cases) {
  const out = gradePixel(c.pixel, c.conv ? cubes[c.conv] : null, c.look ? cubes[c.look] : null, c.exposure, c.strength, c.is_log);
  for (let k = 0; k < 3; k++) maxErr = Math.max(maxErr, Math.abs(out[k] - c.expect[k]));
}
check(maxErr <= 2 / 255, `max error ${(maxErr * 255).toFixed(4)}/255 > 2/255`);

// ---- 2. a 33^3 identity cube written like grade.write_cube: lookup returns the input (catches axis order mix-ups
//         together with the asymmetric synthetic conv above)
const n = 33, lines = ['TITLE "id"', "LUT_3D_SIZE 33", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"];
for (let b = 0; b < n; b++) for (let g = 0; g < n; g++) for (let r = 0; r < n; r++)
  lines.push([r, g, b].map((v) => (v / (n - 1)).toFixed(6)).join(" "));
const id = parseCube(lines.join("\n") + "\n");
for (const p of [[0.1, 0.5, 0.9], [0.9, 0.2, 0.05], [0.333, 0.777, 0.5]]) {
  const o = sample(id, p);
  check(o.every((v, k) => Math.abs(v - p[k]) < 1e-5), `identity 33 lookup ${p} -> ${o}`);
}
let threw = false;
try { parseCube("LUT_3D_SIZE 33\n0 0 0\n"); } catch (e) { threw = true; }
check(threw, "short cube must be rejected");

// ---- 3. request texts (webapp/studio.py format, nothing else)
const T = (a, name, x) => requestText(a, name, x);
const exact = [
  [T("plan", "Porto 2026"), '[studio] actie=plan project="Porto 2026"'],
  [T("stills", "Beef Tartaar v2"), '[studio] actie=stills project="Beef Tartaar v2"'],
  [T("render", "A"), '[studio] actie=render project="A"'],
  [T("grade", "Porto 2026", { look: "moody", strength: 0.7, exposure: -1.75 }),
    '[studio] actie=grade project="Porto 2026" look=moody strength=0.7 exposure=-1.75'],
  [T("grade", "P", { look: "vintage", strength: 1, exposure: 0 }), '[studio] actie=grade project="P" look=vintage strength=1 exposure=0'],
  [T("goedkeuren", "Porto 2026", { plan: "0123456789ab", grade: "ba9876543210", note: '  ja, "B" met \\ erin  ' }),
    '[studio] actie=goedkeuren project="Porto 2026" plan=0123456789ab grade=ba9876543210 notitie="ja, \\"B\\" met \\\\ erin"'],
  [T("ssd-ververs", ""), "[studio] actie=ssd-ververs"],
  [T("ssd-bekijk", "", { map: "_Inbox/2026-10-09 SD-kaart" }), '[studio] actie=ssd-bekijk map="_Inbox/2026-10-09 SD-kaart"'],
  [T("ssd-clip", "", { map: "Reizen/2025-08-11 Mongolië", clip: "C0203.MP4" }),
    '[studio] actie=ssd-clip map="Reizen/2025-08-11 Mongolië" clip="C0203.MP4"'],
  [T("ssd-verplaats", "", { name: " Ibiza ", soort: "reizen", maps: ["_Inbox/2026-10-09 SD-kaart", "_Inbox/2026-10-10 SD-kaart"] }),
    '[studio] actie=ssd-verplaats naam="Ibiza" soort=reizen mappen="_Inbox/2026-10-09 SD-kaart|_Inbox/2026-10-10 SD-kaart"'],
];
for (const [got, want] of exact) check(got.text === want, `request ${JSON.stringify(got)} != ${want}`);
const bad = [
  T("goedkeuren", "P", { plan: "0123456789ab", grade: "ba9876543210", note: "   " }),
  T("goedkeuren", "P", { plan: "0123456789ab", grade: "ba9876543210", note: "--by=Evil" }),
  T("goedkeuren", "P", { plan: "0123456789ab", grade: "ba9876543210", note: "x".repeat(301) }),
  T("goedkeuren", "P", { plan: "0123456789ab", grade: "ba9876543210", note: "a\nb" }),
  T("goedkeuren", "P", { plan: null, grade: "ba9876543210", note: "ja" }),
  T("goedkeuren", "P", { plan: "0123456789ab", grade: undefined, note: "ja" }),
  T("grade", "P", { look: "odyssey", strength: 1, exposure: 0 }),
  T("grade", "P", { look: "moody", strength: 1.2, exposure: 0 }),
  T("grade", "P", { look: "moody", strength: 1, exposure: -4 }),
  T("wis", "P"),
  T("plan", ""),
  T("ssd-bekijk", "", { map: "_Inbox/../.." }),
  T("ssd-bekijk", "", { map: "C:/Windows" }),
  T("ssd-clip", "", { map: "_Inbox/2026-10-09 SD-kaart", clip: "../../x.mp4" }),
  T("ssd-verplaats", "", { name: "a/b", soort: "reizen", maps: ["_Inbox/x"] }),
  T("ssd-verplaats", "", { name: "Ibiza", soort: "vakantie", maps: ["_Inbox/x"] }),
  T("ssd-verplaats", "", { name: "Ibiza", soort: "reizen", maps: [] }),
  T("ssd-verplaats", "", { name: "Ibiza", soort: "reizen", maps: ['_Inbox/x" naam="y'] }),
];
bad.forEach((r, i) => check(r.error && !r.text, `bad request ${i} accepted: ${JSON.stringify(r)}`));

const py = process.env.PYTHON;
if (py) {
  const texts = exact.map(([g]) => g.text);
  const code = "import json,sys; sys.path.insert(0, sys.argv[1]); from webapp import studio;" +
    "print(json.dumps([studio.parse(t) for t in json.loads(sys.stdin.read())]))";
  const r = spawnSync(py, ["-c", code, REPO], { input: JSON.stringify(texts), encoding: "utf8" });
  check(r.status === 0, "python parse failed: " + r.stderr);
  if (r.status === 0) {
    const parsed = JSON.parse(r.stdout);
    check(parsed[5].notitie === 'ja, "B" met \\ erin', "note round trip: " + parsed[5].notitie);
    check(parsed[3].look === "moody" && parsed[3].project === "Porto 2026", "grade round trip");
    check(parsed[8].clip === "C0203.MP4" && parsed[8].map === "Reizen/2025-08-11 Mongolië", "ssd-clip round trip");
    check(parsed[9].mappen.length === 2 && parsed[9].naam === "Ibiza" && parsed[9].soort === "reizen", "ssd-verplaats round trip");
    console.log("python parse: " + parsed.length + " request texts accepted");
  }
} else {
  console.log("python parse: skipped (set PYTHON to check the texts against webapp/studio.py)");
}

if (fails) { console.error(fails + " failure(s)"); process.exit(1); }
console.log(`studio page lut test OK (${fx.cases.length} cases, max error ${(maxErr * 255).toFixed(4)}/255)`);
