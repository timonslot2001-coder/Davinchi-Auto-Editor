"""Keeps the project's documents true: rules, numbers, paths and commands named in the docs must match the code and
EDITING_DNA_PACKAGE/style_dna.json; every document is in the map (docs/README.md), every decision record is complete and
indexed, and README's command reference names every command. Run after changing a document, a command or the DNA:
python tools/doc_check.py
Exit code 1 when something is out of date; each line says which document and what."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DNA = REPO / "EDITING_DNA_PACKAGE"
SKIP = ("/.claude/skills/popular-web-designs/", "/.venv/", "/data/", "/reference_frames/", "/annotated_comparisons/")
# local-only material (gitignored or created per project) that docs may name without it being in the repo
LOCAL_OK = ("reference_frames", "annotated_comparisons", "data/", ".env", "exports/", "cine_montage/", "clips/", "music/",
            "project.yaml", "_review.", "ai_spend.json", "qa.json", "APPROVAL.json", "edl.json", "storyboard",
            "EDITING_DNA_PACKAGE.zip", "OdysseyPowergrade.drx", "user_styles.yaml", "script.yaml", "tags.json",
            "smoke_result.json", "packs_index.json", "toolchain.json", "gridflow_strip", "gridflow_test.mp4")
EXT = (".py", ".md", ".json", ".yaml", ".html", ".ps1", ".bat", ".png", ".jpg", ".ttf", ".txt")


def docs() -> list[Path]:
    files = subprocess.run(["git", "ls-files", "*.md"], cwd=REPO, capture_output=True, text=True).stdout.split()
    return [REPO / f for f in files if not any(s in "/" + f for s in SKIP)]


def rel(p: Path) -> str:
    return p.relative_to(REPO).as_posix()


def check_rules(dna: dict, problems: list) -> None:
    ids = [r["id"] for r in dna["rules"]]
    for name in ("STYLE_DNA.md", "EDITING_PSYCHOLOGY.md"):
        text = (DNA / name).read_text(encoding="utf-8")
        for i in ids:
            if i not in text:
                problems.append(f"EDITING_DNA_PACKAGE/{name}: rule {i} from style_dna.json is not described")
    m = re.search(r"Conflict priority[^:]*:\s*(.+?)(?:\.\s|\n\n)", (DNA / "STYLE_DNA.md").read_text(encoding="utf-8"), re.S)
    if m:
        doc = [x.strip(" .\n") for x in re.split(r">", m[1].replace("\n", " "))]
        want = [i.replace("RULE_", "") for i in dna["priority"]]
        if doc[:len(want)] != want:
            problems.append(f"EDITING_DNA_PACKAGE/STYLE_DNA.md: conflict priority {doc} != style_dna.json {want}")
    for d in docs():
        for i in sorted(set(re.findall(r"\bRULE_[A-Z_]+\b", d.read_text(encoding="utf-8")))):
            if i not in ids:
                problems.append(f"{rel(d)}: names {i}, which is not in style_dna.json")
    status = (REPO / "VIDEO_EDITING_SYSTEM" / "PROJECT_STATUS.md").read_text(encoding="utf-8")
    m = re.search(r"(\d+) rules", status)
    if m and int(m[1]) != len(ids):
        problems.append(f"VIDEO_EDITING_SYSTEM/PROJECT_STATUS.md: says {m[1]} rules, style_dna.json has {len(ids)}")


def check_numbers(problems: list) -> None:
    sys.path.insert(0, str(REPO / "VIDEO_EDITING_SYSTEM"))
    from engine import dna as dna_mod                     # the engine's own reading of the DNA
    p = dna_mod.load()
    text = (DNA / "STYLE_DNA.md").read_text(encoding="utf-8")
    want = {
        "pacing curve": " → ".join(f"{x:.2f}" for x in p.pacing_by_fifth),
        "hard cut share": f"{p.transition_share['hard_cut'] * 100:.1f} %",
        "flash share": f"{p.transition_share['flash_white'] * 100:.1f} %",
        "whip share": f"{p.transition_share['whip_blur'] * 100:.1f} %",
        "accent density": f"{p.accents_per_second:.2f} non-hard",
        "title in (median)": f"median {p.title_timing['in_s_median']:.2f}",
        "title hold (median)": f"median {p.title_timing['hold_s_median']:.2f}",
    }
    for what, s in want.items():
        if s not in text:
            problems.append(f"EDITING_DNA_PACKAGE/STYLE_DNA.md: {what} should read '{s}' (style_dna.json)")


def cli_commands() -> dict[str, set]:
    eng = (REPO / "VIDEO_EDITING_SYSTEM" / "engine" / "cli.py").read_text(encoding="utf-8")
    e = set(re.findall(r'add_parser\("([\w-]+)"', eng))
    for tup in re.findall(r"for c in \(([^)]*)\)", eng):
        e |= set(re.findall(r'"([\w-]+)"', tup))
    a = set(re.findall(r'add_parser\("([\w-]+)"', (REPO / "autoedit" / "__main__.py").read_text(encoding="utf-8")))
    return {"engine": e, "autoedit": a}


def check_commands(problems: list) -> None:
    cmds = cli_commands()
    for d in docs():
        text = d.read_text(encoding="utf-8")
        # only inside code: `...` spans and ``` blocks, where a command is meant literally
        code = " ¦ ".join(re.findall(r"```.*?```", text, re.S) + re.findall(r"`([^`\n]+)`", text))
        for m in re.findall(r"(?:-m\s+(engine)|(?<![\w/.\\-])(autoedit)(?:\.bat)?)\s+([a-z][\w-]*)", code):
            tool, sub = m[0] or m[1], m[2]
            if sub not in cmds[tool]:
                problems.append(f"{rel(d)}: `{tool} {sub}` is not a command (known: {', '.join(sorted(cmds[tool]))})")


def check_paths(problems: list) -> None:
    for d in docs():
        text = d.read_text(encoding="utf-8")
        for tok in re.findall(r"`([^`\n]+)`", text) + re.findall(r"\]\(([^)#\s]+)\)", text):
            t = tok.strip().split()[0].rstrip(".,:;") if tok.strip() else ""
            if (not t or "://" in t or re.match(r"^[A-Za-z]:[\\/]", t) or t.startswith(("~", "%", "$", "-", "#"))
                    or any(c in t for c in "<>*{}|=?") or "..." in t or "…" in t):
                continue
            if not (t.endswith(EXT) or (t.endswith("/") and "/" in t[:-1])):
                continue
            if any(x in t for x in LOCAL_OK):
                continue
            base = t.split(":")[0].split("#")[0].replace("\\", "/")
            cands = [d.parent / base, REPO / base, DNA / base, REPO / "VIDEO_EDITING_SYSTEM" / base,
                     REPO / "VIDEO_EDITING_SYSTEM" / "engine" / base, DNA / "animations_and_components" / base]
            if "/" not in base.rstrip("/"):                # a bare file name: accept it anywhere in the repo
                if list(REPO.glob(f"**/{base}")):
                    continue
            if not any(c.exists() for c in cands):
                problems.append(f"{rel(d)}: names `{t}`, which does not exist")


def links(d: Path) -> set[Path]:
    """Documents a markdown file links to, resolved to absolute paths."""
    out = set()
    for t in re.findall(r"\]\(([^)#\s]+)", d.read_text(encoding="utf-8")):
        if "://" not in t:
            out.add((d.parent / t).resolve())
    return out


def check_map(problems: list) -> None:
    """Every tracked document is reachable from docs/README.md (decision records through their index)."""
    home = REPO / "docs" / "README.md"
    index = REPO / "docs" / "decisions" / "README.md"
    reach = links(home) | links(index) | {home.resolve()}
    for d in docs():
        if d.resolve() not in reach:
            problems.append(f"docs/README.md: {rel(d)} is not in the documentation map")


def check_decisions(problems: list) -> None:
    folder = REPO / "docs" / "decisions"
    listed = links(folder / "README.md")
    for d in sorted(folder.glob("[0-9][0-9][0-9][0-9]-*.md")):
        text = d.read_text(encoding="utf-8")
        for need in ("- Status:", "- Date:", "## Context", "## Decision", "## Consequences"):
            if need not in text:
                problems.append(f"{rel(d)}: missing '{need}'")
        if d.resolve() not in listed:
            problems.append(f"docs/decisions/README.md: {d.name} is not in the index")


def check_reference(problems: list) -> None:
    """README's command reference names every autoedit and engine command."""
    text = (REPO / "README.md").read_text(encoding="utf-8")
    m = re.search(r"## Command reference\n(.*?)(?:\n## |\Z)", text, re.S)
    if not m:
        problems.append("README.md: no '## Command reference' section")
        return
    code = " ".join(re.findall(r"`([^`\n]+)`", m[1]))
    for tool, cmds in cli_commands().items():
        for c in sorted(cmds):
            if not re.search(rf"(?<![\w-]){re.escape(c)}(?![\w-])", code):
                problems.append(f"README.md: command reference misses `{tool} {c}`")


def main() -> int:
    dna = json.loads((DNA / "style_dna.json").read_text(encoding="utf-8"))
    problems: list[str] = []
    check_rules(dna, problems)
    check_numbers(problems)
    check_commands(problems)
    check_paths(problems)
    check_map(problems)
    check_decisions(problems)
    check_reference(problems)
    n = len(docs())
    for p in problems:
        print("OUT OF DATE:", p)
    print(f"doc_check: {n} documents, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
