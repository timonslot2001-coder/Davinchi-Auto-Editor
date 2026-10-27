# Toolchain: skills, plugins, models, Resolve add-ons

Everything AutoEdit needs outside the Python code, so a new PC can be set up the same way.

| What | Where in the repo | How it comes back |
|---|---|---|
| Claude skills (`cine-montage`, `popular-web-designs`) | `.claude/skills/` | `install.ps1` copies them to `~/.claude/skills` |
| Claude plugins / marketplaces | `toolchain.json` → `claude` | printed as `claude plugin ...` commands; `anthropic-skills` and `productivity` come with the Claude account |
| Resolve script *Auto Grade* (own) | `setup/resolve/Scripts/` | copied into Resolve's Fusion `Scripts` folder |
| Bought Resolve packs (`.drfx`, FOUR Editors LUTs, PowerGrade LUTs) | **not in the repo** (public; licences); `toolchain.json` lists name + sha256 | `-PacksBackup <folder>` restores them from your own backup, checked by hash |
| ComfyUI Wan 2.2 5B models (~17 GB) | `toolchain.json` → `comfy.models` (Hugging Face URL + size) | `-Models` downloads them into Comfy Desktop's models folder |
| `AutoEdit_*.cube` LUTs | generated | rebuilt by `autoedit/grade.py` on the first grade |
| Python packages | `requirements.txt` | `pip install -r requirements.txt` in `~/.aev` |

```powershell
powershell -ExecutionPolicy Bypass -File setup\install.ps1 -DryRun                            # what is missing
powershell -ExecutionPolicy Bypass -File setup\install.ps1 -Models -PacksBackup "D:\Backup\AutoEdit packs"
powershell -ExecutionPolicy Bypass -File setup\install.ps1 -MakeBackup "D:\Backup\AutoEdit packs"  # back up the bought packs
```

After adding a skill, plugin, pack or model: run `python setup/snapshot.py` and commit `setup/toolchain.json`.
Comfy Desktop and DaVinci Resolve themselves are installed by hand.
