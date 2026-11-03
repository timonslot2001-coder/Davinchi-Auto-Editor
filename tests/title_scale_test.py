"""Titles are never stretched (Timon 2026-11-03): the component fits text with one uniform scale. A render of a long
title through Edge is checked by eye on the storyboard; this guards the code path.
usage: python tests/title_scale_test.py"""
import re
from pathlib import Path

html = (Path(__file__).resolve().parents[1] / "EDITING_DNA_PACKAGE" / "animations_and_components" / "components.html")
src = html.read_text(encoding="utf-8")
fit = src[src.index("function fitBox"):src.index("function render(")]
scales = re.findall(r"scale\(([^)]*)\)", fit)
assert scales and all("," not in s for s in scales), f"non-uniform scale in fitBox: {scales}"
assert "<br>" in fit, "long titles may go onto two lines"
assert not re.search(r"scaleX|scaleY", fit), "no one-axis scaling"
print("title scale test ok")
