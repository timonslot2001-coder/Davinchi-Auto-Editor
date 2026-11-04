# Starts the AutoEdit website (http://127.0.0.1:5080, phone via Tailscale) when you log in to Windows, minimised and
# without opening a browser, so the Studio's Foto's link always has something to open.
#   powershell -ExecutionPolicy Bypass -File setup\autostart-website.ps1           # add the shortcut
#   powershell -ExecutionPolicy Bypass -File setup\autostart-website.ps1 -Remove   # take it away again
param([switch]$Remove)
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Link = Join-Path ([Environment]::GetFolderPath("Startup")) "AutoEdit website.lnk"
if ($Remove) {
    if (Test-Path $Link) { Remove-Item $Link; Write-Host "removed $Link" } else { Write-Host "no shortcut to remove" }
    exit 0
}
$Py = Join-Path $env:USERPROFILE ".aev\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = Join-Path $Repo ".venv\Scripts\python.exe" }
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($Link)
$s.TargetPath = Join-Path $env:SystemRoot "System32\cmd.exe"
$s.Arguments = "/c set PYTHONIOENCODING=utf-8&& `"$Py`" -m webapp --phone --no-browser"
$s.WorkingDirectory = $Repo
$s.WindowStyle = 7                                               # minimised
$s.Description = "AutoEdit website (port 5080)"
$s.Save()
Write-Host "added $Link"
