# Restores the AutoEdit toolchain on a (new) PC from setup/toolchain.json.
#   powershell -ExecutionPolicy Bypass -File setup\install.ps1                     # skills + Resolve scripts, report the rest
#   ... -Models                                                                    # also download the Wan 2.2 models (~17 GB)
#   ... -PacksBackup "D:\Backup\AutoEdit packs"                                    # restore bought .drfx/LUT packs from your backup
#   ... -MakeBackup  "D:\Backup\AutoEdit packs"                                    # copy this PC's bought packs into a backup
#   ... -DryRun                                                                    # only show what would happen
# Bought packs are not in the (public) repo; toolchain.json only lists them with their sha256.
param([switch]$Models, [string]$PacksBackup, [string]$MakeBackup, [switch]$DryRun)
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$T = Get-Content (Join-Path $PSScriptRoot "toolchain.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$Fusion = Join-Path $env:APPDATA "Blackmagic Design\DaVinci Resolve\Support\Fusion"
$Lut = "C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT"
$Comfy = Join-Path $env:LOCALAPPDATA "Comfy-Desktop\ComfyUI-Shared"
$todo = New-Object System.Collections.Generic.List[string]

function Copy-Tree($src, $dst) {
    if ($DryRun) { Write-Host "  [dry] $src -> $dst"; return }
    New-Item -ItemType Directory -Force $dst | Out-Null
    Copy-Item -Path (Join-Path $src "*") -Destination $dst -Recurse -Force
    Write-Host "  $src -> $dst"
}

Write-Host "== Claude skills"
foreach ($s in $T.claude.skills_in_repo) {
    Copy-Tree (Join-Path $Repo ".claude\skills\$s") (Join-Path $HOME ".claude\skills\$s")
}
foreach ($m in $T.claude.marketplaces.PSObject.Properties) {
    $todo.Add("Claude plugin marketplace '$($m.Name)': claude plugin marketplace add $($m.Value.repo)")
}
foreach ($p in $T.claude.installed_plugins) { $todo.Add("Claude plugin: claude plugin install $p") }
foreach ($a in $T.claude.account_provided) { $todo.Add("Comes with your Claude account: $a") }

Write-Host "== Resolve scripts"
if (Test-Path (Split-Path $Fusion)) {
    Copy-Tree (Join-Path $PSScriptRoot "resolve\Scripts") (Join-Path $Fusion "Scripts")
} else { $todo.Add("Install DaVinci Resolve, then re-run this script for the Auto Grade script") }

Write-Host "== ComfyUI models"
foreach ($m in $T.comfy.models.PSObject.Properties) {
    $dst = Join-Path $Comfy ("models\" + $m.Name)
    if ((Test-Path $dst) -and (Get-Item $dst).Length -eq $m.Value.bytes) { Write-Host "  ok  $($m.Name)"; continue }
    if (-not $Models) { $todo.Add("Comfy model missing: $($m.Name) (re-run with -Models)"); continue }
    if ($DryRun) { Write-Host "  [dry] download $($m.Value.url)"; continue }
    New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
    & curl.exe -L --fail -C - -o "$dst.part" $m.Value.url
    if ((Get-Item "$dst.part").Length -ne $m.Value.bytes) { throw "size mismatch for $($m.Name)" }
    Move-Item -Force "$dst.part" $dst
    Write-Host "  downloaded $($m.Name)"
}
if (-not (Test-Path $Comfy)) { $todo.Add("Install Comfy Desktop: $($T.comfy.app)") }
foreach ($n in $T.comfy.custom_nodes) { $todo.Add("Comfy custom node: $n (install via ComfyUI Manager)") }

Write-Host "== Bought Resolve packs"
if ($MakeBackup) {
    Copy-Tree (Join-Path $Fusion "Templates") (Join-Path $MakeBackup "Templates")
    foreach ($l in $T.resolve.lut_folders.PSObject.Properties) {
        if ($l.Name -ne "AutoEdit") { Copy-Tree (Join-Path $Lut $l.Name) (Join-Path $MakeBackup "LUT\$($l.Name)") }
    }
}
foreach ($d in $T.resolve.drfx_packs.PSObject.Properties) {
    $dst = Join-Path $Fusion "Templates\$($d.Name)"
    if ((Test-Path $dst) -and (Get-FileHash $dst -Algorithm SHA256).Hash -eq $d.Value.sha256) { Write-Host "  ok  $($d.Name)"; continue }
    $src = if ($PacksBackup) { Join-Path $PacksBackup "Templates\$($d.Name)" }
    if ($src -and (Test-Path $src) -and (Get-FileHash $src -Algorithm SHA256).Hash -eq $d.Value.sha256) {
        if ($DryRun) { Write-Host "  [dry] $src -> $dst" } else { New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null; Copy-Item $src $dst -Force; Write-Host "  restored $($d.Name)" }
    } else { $todo.Add("Resolve pack missing: $($d.Name) (re-run with -PacksBackup, or re-download from the seller)") }
}
foreach ($f in $T.resolve.loose_template_folders) {
    $src = if ($PacksBackup) { Join-Path $PacksBackup "Templates\$f" }
    if (Test-Path (Join-Path $Fusion "Templates\$f")) { Write-Host "  ok  $f" }
    elseif ($src -and (Test-Path $src)) { Copy-Tree $src (Join-Path $Fusion "Templates\$f") }
    else { $todo.Add("Resolve templates missing: $f") }
}
foreach ($l in $T.resolve.lut_folders.PSObject.Properties) {
    if ($l.Name -eq "AutoEdit" -or (Test-Path (Join-Path $Lut $l.Name))) { Write-Host "  ok  LUT\$($l.Name)"; continue }
    $src = if ($PacksBackup) { Join-Path $PacksBackup "LUT\$($l.Name)" }
    if ($src -and (Test-Path $src)) { Copy-Tree $src (Join-Path $Lut $l.Name) }
    else { $todo.Add("LUT folder missing: $($l.Name) - $($l.Value.note)") }
}

Write-Host "== Python"
if (-not (Test-Path (Join-Path $HOME ".aev\Scripts\python.exe"))) {
    $todo.Add("Python env: py -3.12 -m venv $HOME\.aev ; $HOME\.aev\Scripts\pip install -r requirements.txt")
} else { Write-Host "  ok  $HOME\.aev" }

Write-Host ""
if ($todo.Count) { Write-Host "Still to do by hand:"; $todo | ForEach-Object { Write-Host "  - $_" } }
else { Write-Host "Everything is in place." }
