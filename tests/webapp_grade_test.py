"""Web app: the cine grade route and the render/preview argv. usage: python tests/webapp_grade_test.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webapp import app as webapp   # noqa: E402


class FakeHost:
    mode = "local"

    def __init__(self):
        self.runs = []

    def call(self, op, args=None):
        assert op == "project", op
        return {"path": "/p/x"}

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

# render never gets --look (grade.json is the source); preview may
c.post("/api/projects/x/cine/render", json={"look": "moody"})
assert host.runs[-1] == ["engine", "render", "/p/x"], host.runs[-1]
c.post("/api/projects/x/cine/preview", json={"look": "moody"})
assert host.runs[-1] == ["engine", "preview", "/p/x", "--look", "moody"], host.runs[-1]
c.post("/api/projects/x/cine/preview", json={"look": "daylight"})
assert host.runs[-1][-2:] == ["--look", "daylight"]
print("webapp grade test OK")
