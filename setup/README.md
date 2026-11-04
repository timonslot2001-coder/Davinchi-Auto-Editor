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
| Python packages | `requirements-lock.txt` (exact `pip freeze` incl. torch CPU, demucs, faster-whisper) | `install.ps1` builds `%USERPROFILE%\.autoedit\venv` from it and points `~/.aev` there |

```powershell
powershell -ExecutionPolicy Bypass -File setup\install.ps1 -DryRun                            # what is missing
powershell -ExecutionPolicy Bypass -File setup\install.ps1 -Models -PacksBackup "D:\Backup\AutoEdit packs"
powershell -ExecutionPolicy Bypass -File setup\install.ps1 -MakeBackup "D:\Backup\AutoEdit packs"  # back up the bought packs
```

After adding a skill, plugin, pack or model: run `python setup/snapshot.py` and commit `setup/toolchain.json`.
Comfy Desktop and DaVinci Resolve themselves are installed by hand. **LightCraft in the browser** (any device, over Tailscale): Docker Desktop (`winget install Docker.DockerDesktop`, with
WSL), Remote Desktop on, LightCraft registered as the only RemoteApp (admin PowerShell: the `TSAppAllowList\Applications\lightcraft`
key with `Name`, `Path` to `lightcraft.exe`, `ShowInTSWA` 1, `CommandLineSetting` 1), then `python setup/lightcraft_web.py up`
(Guacamole on port 8085 of this PC and its Tailscale address; login password in `data/guacamole/WACHTWOORD.txt`).
`setup/autostart-website.ps1` makes the website start at
Windows log-in (minimised, no browser; `-Remove` takes it away). LM Studio (the local model behind the website box
*Typ wat je wilt*) too: `winget install ElementLabs.LMStudio`, open it once, then `lms get openai/gpt-oss-20b`; `install.ps1`
reports it when missing. LightCraft (the *Foto's* page and the `lightcraft` MCP server in `.mcp.json`): unzip the
portable release from github.com/storytold/lightcraft into `~/.autoedit/lightcraft/v<version>/`.
