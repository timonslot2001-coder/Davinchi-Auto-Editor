"""Looks test: new looks exist, strength is a linear mix, look_lut layout matches identity().
usage: python tests/grade_looks_test.py"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autoedit import grade               # noqa: E402

for k in ("reference_film", "clean_warm", "moody", "daylight", "blue_hour", "vintage", "none"):
    assert k in grade.LOOKS
c = np.random.default_rng(1).random((500, 3))
for k in ("daylight", "blue_hour", "vintage"):
    p = grade.LOOKS[k]
    full = grade.film_look(c, p, 1.0)
    assert np.allclose(grade.film_look(c, p, 0.6), c + (full - c) * 0.6, atol=1e-6)   # strength is a linear mix
    assert np.abs(full - c).mean() > 0.01 and np.isfinite(full).all()
    lut = grade.look_lut(k, 17)
    assert lut.shape == (17, 17, 17, 3) and lut.min() >= -1e-6 and lut.max() <= 1 + 1e-6
assert np.allclose(grade.look_lut("none", 9), grade.identity(9))
# daylight warmer than blue_hour on a mid grey
g = np.full((1, 3), 0.5)
d, b = grade.film_look(g, grade.LOOKS["daylight"], 1)[0], grade.film_look(g, grade.LOOKS["blue_hour"], 1)[0]
assert d[0] - d[2] > b[0] - b[2]
print("grade looks ok")
