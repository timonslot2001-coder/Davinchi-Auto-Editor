"""The typed request box: the local model's tool call becomes one website action, checked against what exists; render
or anything unknown never becomes an action. No model needed (the HTTP call is replaced).
usage: python tests/assistant_test.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webapp import assistant                 # noqa: E402

PROJECT = {"name": "Test", "settings": {"song": "ESCAPE PLAN.mp3"}, "clips": [{"name": "C0146.MP4"}]}
SONGS = ["ESCAPE PLAN.mp3", "Other.wav"]


def answer(name=None, args=None, content=""):
    calls = [{"function": {"name": name, "arguments": json.dumps(args or {})}}] if name else []
    seen = {}

    def post(body):
        seen.update(body)
        return {"choices": [{"message": {"content": content, "tool_calls": calls}}]}
    return post, seen


def ask(post):
    return assistant.ask(PROJECT, "x", SONGS, post=post)


post, seen = answer("feedback", {"kind": "korter"})
assert ask(post)["action"] == {"action": "feedback", "kind": "korter"}
names = [t["function"]["name"] for t in seen["tools"]]
assert names == ["plan", "feedback", "remove_clip", "look"], names
assert "render" not in json.dumps(seen["tools"]).lower().replace("rendering", ""), "no render tool"

assert ask(answer("plan", {"song": "Other.wav", "title": "MADEIRA", "length": 12})[0])["action"] == \
    {"action": "plan", "song": "Other.wav", "title": "MADEIRA", "length": 12}
assert ask(answer("plan", {"song": "made-up.mp3", "length": 99})[0])["action"] == {"action": "plan"}, "unknown values dropped"
assert ask(answer("remove_clip", {"clip": "C0146.MP4"})[0])["action"] == {"action": "feedback", "kind": "eruit", "clip": "C0146.MP4"}
assert ask(answer("remove_clip", {"clip": "nope.mp4"})[0])["action"] is None
assert ask(answer("look", {"look": "moody"})[0])["action"] == {"action": "look", "look": "moody"}
assert ask(answer("render", {})[0])["action"] is None, "an invented tool does nothing"
r = ask(answer(content="Druk op Ja, renderen.")[0])
assert r["action"] is None and "renderen" in r["reply"]
try:
    assistant.ask(PROJECT, "  ", SONGS, post=answer()[0])
    raise AssertionError("empty text must be refused")
except ValueError:
    pass
print("assistant test ok")
