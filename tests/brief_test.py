"""The brief: the four choices Timon makes before an edit (song, rhythm, length, grade). No Resolve needed.
usage: python tests/brief_test.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autoedit import brief                                    # noqa: E402
from autoedit.brief import Brief                              # noqa: E402

b = Brief()
assert (b.rhythm, b.length, b.kind, b.aspect) == ("rustig", "normaal", "auto", "9:16")
assert b.song is None and b.grade is None and b.song_start is None
assert b.seconds == 20.0 and brief.merge(b, length="kort").seconds == 10.0 and Brief(length="lang").seconds == 30.0
assert brief.merge(Brief(song="a"), song=None, rhythm="beat") == Brief(song="a", rhythm="beat"), "None keeps the old value"

probs = brief.problems(Brief(), ["a.mp3", "b.mp3"], ["basis", "Film"])
assert len(probs) == 2, probs
assert any("liedje" in p.lower() and "a.mp3" in p and "b.mp3" in p for p in probs), probs
assert any("kleur" in p.lower() and "Film" in p and "basis" in p for p in probs), probs
assert brief.problems(Brief(song="a", grade="Film"), ["a.mp3"], ["basis", "Film"]) == []
assert len(brief.problems(Brief(song="a", grade="basis", rhythm="snel"), ["a.mp3"], ["basis"])) == 1
assert len(brief.problems(Brief(song="a", grade="basis", length="episch"), ["a.mp3"], ["basis"])) == 1
assert len(brief.problems(Brief(song="a", grade="basis", aspect="4:3"), ["a.mp3"], ["basis"])) == 1
assert len(brief.problems(Brief(song="zzz", grade="basis"), ["a.mp3"], ["basis"])) == 1, "a song that is not there"
assert len(brief.problems(Brief(song="a", grade="Onbekend"), ["a.mp3"], ["basis"])) == 1, "a grade that is not there"
assert len(brief.problems(Brief(song="a", grade="basis", song_start=-1.0), ["a.mp3"], ["basis"])) == 1
assert brief.problems(Brief(song="none", grade="basis"), [], ["basis"]) == [], "'none' = an edit without music"

got = brief.from_project({"edit": {"song": "x", "bogus": 1, "length": "kort", "song_start": "12"}, "category": "food"})
assert got.song == "x" and got.length == "kort" and got.song_start == 12.0
assert brief.from_project({}) == Brief() and brief.from_project({"edit": None}) == Brief()
d = brief.to_project(Brief(song="x", grade="basis"))
assert d == {"song": "x", "song_start": "auto", "rhythm": "rustig", "length": "normaal", "grade": "basis",
             "kind": "auto", "aspect": "9:16"}, d
assert brief.from_project({"edit": d}) == Brief(song="x", grade="basis"), "round trip"
print("brief test ok")
