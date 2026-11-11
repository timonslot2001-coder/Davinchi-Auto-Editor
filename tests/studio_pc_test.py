"""studio/pc tells the Studio where the website is (the Foto's link): localhost always, the Tailscale address when set.
usage: python tests/studio_pc_test.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webapp import phone, studio             # noqa: E402

phone.tailscale_ip = lambda: None
d = studio.pc_doc()
assert d["website"] == "http://127.0.0.1:5080" and d["phone"] is None and d["host"], d
phone.tailscale_ip = lambda: "100.101.102.103"
assert studio.pc_doc()["phone"] == "http://100.101.102.103:5080"
html = (Path(__file__).resolve().parents[1] / "webapp" / "artifact" / "studio.html").read_text(encoding="utf-8")
assert "navFotos" not in html and "remotedesktop.google.com" not in html, "Foto's and PC op afstand left the Studio menu (2026-11-11)"
assert 'class="side-gear" href="#/instellingen"' in html, "Instellingen is the small gear under the PC status"
print("studio pc test ok")
