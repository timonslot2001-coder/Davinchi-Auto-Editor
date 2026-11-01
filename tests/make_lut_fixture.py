"""Write tests/fixtures/studio_lut.json: reference numbers for the Studio page's grade maths (tests/studio_page_lut_test.js).

The page grades a still in the browser in two LUT stages (see webapp/studio_assets.py):
    x' = clamp(x + exposure*0.0769)  (log only)  ->  c = conv(x')  (log only, skipped without conv)
    ->  o = look(c)  ->  out = c + (o - c)*strength
This helper computes the same with numpy (autoedit/grade.py read_cube + apply_cube) on small cubes that are written
with grade.write_cube, the writer studio_assets.export uses. No Sony file: the conversion cube is synthetic.
Cubes are 9^3 to keep the fixture small; the page's parser and lookup do not depend on the size.

usage: python tests/make_lut_fixture.py"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from autoedit import grade  # noqa: E402

N = 9
OUT = REPO / "tests" / "fixtures" / "studio_lut.json"


def synthetic_conv(n: int) -> np.ndarray:
    """A made-up log -> display curve with channel mixing, so a wrong axis order in the reader shows up."""
    g = grade.identity(n)                                         # [b][g][r] -> (r, g, b)
    r, gg, b = g[..., 0], g[..., 1], g[..., 2]
    out = np.stack([r ** 0.6 * 0.9 + gg * 0.08 + 0.01,
                    gg ** 0.7 * 0.85 + b * 0.1,
                    b ** 0.8 * 0.8 + r * 0.15 + 0.02], axis=-1)
    return np.clip(out, 0, 1)


def stage(cubes: dict, case: dict) -> list:
    c = np.asarray(case["pixel"], np.float64)
    if case["is_log"]:
        c = np.clip(c + case["exposure"] * 0.0769, 0, 1)
        if case["conv"]:
            c = grade.apply_cube(cubes[case["conv"]], c)
    o = grade.apply_cube(cubes[case["look"]], c) if case["look"] else c
    out = c + (o - c) * case["strength"]
    return [round(float(v), 6) for v in np.clip(out, 0, 1)]


def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    arrays = {"conv": synthetic_conv(N), "moody": grade.look_lut("moody", N), "vintage": grade.look_lut("vintage", N)}
    texts, cubes = {}, {}
    for name, arr in arrays.items():
        f = tmp / f"{name}.cube"
        grade.write_cube(f, arr, f"fixture {name}")
        texts[name] = f.read_text()
        cubes[name], _ = grade.read_cube(f)                       # the reference reads the same text as the page
    pixels = [[0.08, 0.12, 0.30], [0.41, 0.39, 0.37], [0.62, 0.48, 0.33], [0.93, 0.88, 0.80], [0.20, 0.55, 0.15]]
    settings = [dict(conv="conv", look="moody", exposure=-1.75, strength=0.7, is_log=True),
                dict(conv="conv", look="vintage", exposure=0.0, strength=1.0, is_log=True),
                dict(conv="conv", look="moody", exposure=0.5, strength=0.0, is_log=True),
                dict(conv=None, look="moody", exposure=-1.0, strength=1.0, is_log=True),
                dict(conv="conv", look="vintage", exposure=-1.75, strength=0.5, is_log=False)]
    cases = []
    for s in settings:
        for p in pixels:
            case = {"pixel": p, **s}
            case["expect"] = stage(cubes, case)
            cases.append(case)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"size": N, "cubes": texts, "cases": cases}, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}: {len(cases)} cases")


if __name__ == "__main__":
    main()
