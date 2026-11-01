"""Web app: the cine grade route and the render/preview argv. usage: python tests/webapp_grade_test.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webapp import app as webapp   # noqa: E402


class FakeHost:
    mode = "local"

    def __init__(self):
        self.runs = []
        self.approval = None

    def call(self, op, args=None):
        assert op == "project", op
        return {"path": "/p/x", "cine": {"approval": self.approval}}

    def run(self, args, label, project=None):
        self.runs.append(args)
        return {"id": "j1"}


host = FakeHost()
c = webapp.create(host=host).test_client()
url = "/api/projects/x/cine/grade"

r = c.post(url, json={"look": "blue_hour", "strength": 0.7, "exposure": -1.5})
assert r.status_code == 200, r.get_json()
assert host.runs[-1] == ["engine", "grade", "/p/x", "--look", "blue_hour", "--strength", "0.7", "--exposure", "-1.5"], host.runs[-1]

n = len(host.runs)
assert c.post(url, json={"look": "odyssey"}).status_code == 400
assert c.post(url, json={"look": "moody", "strength": 2}).status_code == 400
assert c.post(url, json={"strength": 0.5}).status_code == 400
assert c.post(url, json={"look": "moody", "exposure": 1}).status_code == 400
assert len(host.runs) == n

r = c.post(url, json={"look": "vintage"})
assert r.status_code == 200 and host.runs[-1] == ["engine", "grade", "/p/x", "--look", "vintage"], host.runs[-1]
for look in ("reference_film", "clean_warm", "moody", "daylight", "blue_hour", "vintage"):
    assert c.post(url, json={"look": look}).status_code == 200, look

# render sends the approved --grade mode itself, whatever the body says
host.approval = {"status": "approved", "grade_mode": "slog3"}
c.post("/api/projects/x/cine/render", json={"grade": "auto"})
assert host.runs[-1] == ["engine", "render", "/p/x", "--grade", "slog3"], host.runs[-1]
host.approval = {"status": "approved", "grade_mode": "auto"}
c.post("/api/projects/x/cine/render", json={"grade": "rec709"})
assert host.runs[-1] == ["engine", "render", "/p/x"], host.runs[-1]
host.approval = None
c.post("/api/projects/x/cine/render", json={"grade": "slog3"})
assert host.runs[-1] == ["engine", "render", "/p/x"], host.runs[-1]

# query.cine carries the saved grade
import json, tempfile                      # noqa: E402
from webapp import query                   # noqa: E402
t = Path(tempfile.mkdtemp())
assert query.cine(t)["grade"] == {"look": "reference_film", "strength": 1.0, "exposure": -1.75}
(t / "cine_montage").mkdir()
(t / "cine_montage/grade.json").write_text(json.dumps({"look": "moody", "strength": 0.5}))
assert query.cine(t)["grade"] == {"look": "moody", "strength": 0.5, "exposure": -1.75}

# render never gets --look (grade.json is the source); preview may
c.post("/api/projects/x/cine/render", json={"look": "moody"})
assert host.runs[-1] == ["engine", "render", "/p/x"], host.runs[-1]
c.post("/api/projects/x/cine/preview", json={"look": "moody"})
assert host.runs[-1] == ["engine", "preview", "/p/x", "--look", "moody"], host.runs[-1]
c.post("/api/projects/x/cine/preview", json={"look": "daylight"})
assert host.runs[-1][-2:] == ["--look", "daylight"]
print("webapp grade test OK")
