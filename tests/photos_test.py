"""Photos page: one entry per picture (JPG with its RAW twin, or a RAW alone), developed from the RAW, edits are not
listed again, refs outside the shoot are refused, and the LightCraft command is auto + look + export. A fake
lightcraft-cli stands in, so no LightCraft is needed.
usage: python tests/photos_test.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autoedit import photos                  # noqa: E402
from autoedit.config import Config           # noqa: E402

tmp = Path(tempfile.mkdtemp())
lib = tmp / "SSD"
foto = lib / "Reizen" / "2026-10-09 Ibiza" / "1 Ruw" / "Foto"
foto.mkdir(parents=True)
for n in ("DSC0001.JPG", "DSC0001.ARW", "DSC0002.JPG", "DSC0003.ARW"):
    (foto / n).write_bytes(b"x")
done = lib / "Reizen" / "2026-10-09 Ibiza" / "2 Bewerkt" / "Foto"
done.mkdir(parents=True)
(done / "DSC0002_moody.jpg").write_bytes(b"x")
cfg = Config({"paths": {"library_folder": str(lib)}, "lightcraft": str(tmp / "lightcraft-cli.exe")}, {})
(tmp / "lightcraft-cli.exe").write_bytes(b"")

s = photos.photos(cfg, "Reizen/2026-10-09 Ibiza")
assert [(p["name"], bool(p["raw"])) for p in s["photos"]] == [("DSC0001", True), ("DSC0002", False), ("DSC0003", True)], s
assert s["done"] == ["DSC0002_moody.jpg"], "edits are listed as done, not as photos"
assert photos.resolve_photo(cfg, "Reizen/2026-10-09 Ibiza/DSC0001").suffix == ".ARW", "the RAW is developed"
for bad in ("Reizen/2026-10-09 Ibiza/nope", "Reizen/../x", "C:/Windows/x.jpg"):
    try:
        photos.resolve_photo(cfg, bad)
        raise AssertionError(bad)
    except (ValueError, FileNotFoundError):
        pass

calls = []


def fake_run(cmd, **kw):
    calls.append(cmd)
    out = Path(next(a for a in cmd if a.startswith("path="))[5:])
    out.write_bytes(b"jpg")
    return subprocess.CompletedProcess(cmd, 0, json.dumps({"ok": True}) + "\n", "")


photos.subprocess.run = fake_run
w = photos.export(cfg, ["Reizen/2026-10-09 Ibiza/DSC0001", "Reizen/2026-10-09 Ibiza/DSC0003"], "cinematic")
assert [Path(p).name for p in w] == ["DSC0001_cinematic.jpg", "DSC0003_cinematic.jpg"] and all(Path(p).exists() for p in w)
assert calls[0][2:7] == ["--import", str(foto / "DSC0001.ARW"), "develop.auto", "preset.apply", "id=lc.cinematic"], calls[0]
assert "longEdge=0" in calls[0], "full size"
photos.export(cfg, ["Reizen/2026-10-09 Ibiza/DSC0002"], "auto")
assert "preset.apply" not in calls[-1], "auto = only LightCraft's auto settings"
try:
    photos.export(cfg, ["Reizen/2026-10-09 Ibiza/DSC0002"], "sepia")
    raise AssertionError("unknown look")
except SystemExit:
    pass

# Openen in LightCraft: the app next to lightcraft-cli.exe, on the shoot's photo folder(s)
(tmp / "lightcraft.exe").write_bytes(b"")
started = []
r = photos.open_app(cfg, "Reizen/2026-10-09 Ibiza", popen=lambda cmd, **kw: started.append(cmd), running=lambda: False)
assert started == [[str(tmp / "lightcraft.exe"), "--no-demo", "--control", "7980", str(foto)]], started
assert r == {"opened": [str(foto)], "reused": False}
# already open: the folder goes into that window over the control channel, no second copy
sent = []


def fake_connect(cmd, **kw):
    sent.append(cmd)
    return subprocess.CompletedProcess(cmd, 0, json.dumps({"command": "library.import", "ok": True}) + "\n", "")


started.clear()
r = photos.open_app(cfg, "Reizen/2026-10-09 Ibiza", popen=lambda cmd, **kw: started.append(cmd),
                    running=lambda: True, run=fake_connect)
assert not started and r["reused"], (started, r)
assert sent[0][1:4] == ["run", "--connect", "127.0.0.1:7980"] and json.loads(sent[0][5])["paths"] == [str(foto)], sent
try:                                                          # open, but started outside AutoEdit (no control channel)
    photos.open_app(cfg, "Reizen/2026-10-09 Ibiza", running=lambda: True,
                    run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "connection refused"))
    raise AssertionError("must explain, not start a second copy")
except ValueError as e:
    assert "sluit LightCraft" in str(e)
print("photos test ok")
