"""Phone mode lets in only this PC and your Tailscale devices (webapp/phone.py).
usage: python tests/webapp_phone_test.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flask import Flask                      # noqa: E402

from webapp import phone                     # noqa: E402

for ok in ("127.0.0.1", "::1", "100.64.0.1", "100.101.102.103", "100.127.255.254", "fd7a:115c:a1e0::1",
           "::ffff:100.100.1.2"):
    assert phone.allowed(ok), ok
for bad in ("192.168.1.20", "10.0.0.5", "172.17.0.2", "100.128.0.1", "100.63.255.255", "8.8.8.8", "fe80::1", "",
            None, "nonsense"):
    assert not phone.allowed(bad), bad

app = Flask(__name__)
app.get("/")(lambda: "ok")
phone.guard(app)
c = app.test_client()
assert c.get("/", environ_base={"REMOTE_ADDR": "100.90.1.2"}).status_code == 200
assert c.get("/", environ_base={"REMOTE_ADDR": "127.0.0.1"}).status_code == 200
assert c.get("/", environ_base={"REMOTE_ADDR": "192.168.1.20"}).status_code == 403
assert c.get("/", environ_base={"REMOTE_ADDR": "8.8.8.8"}).status_code == 403
print("webapp phone test ok")
