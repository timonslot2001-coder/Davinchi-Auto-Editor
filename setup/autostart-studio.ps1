# Starts the Studio session (start-studio-sessie.bat) when you log in to Windows, in a minimised window, so the buttons
# of the AutoEdit Studio in the Claude app always have the PC behind them. The bat restarts the session when it stops.
#   powershell -ExecutionPolicy Bypass -File setup\autostart-studio.ps1           # add the shortcut
#   powershell -ExecutionPolicy Bypass -File setup\autostart-studio.ps1 -Remove   # take it away again
param([switch]$Remove)
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Link = Join-Path ([Environment]::GetFolderPath("Startup")) "AutoEdit Studio-sessie.lnk"
if ($Remove) {
    if (Test-Path $Link) { Remove-Item $Link; Write-Host "removed $Link" } else { Write-Host "no shortcut to remove" }
    exit 0
}
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($Link)
$s.TargetPath = Join-Path $Repo "start-studio-sessie.bat"
$s.WorkingDirectory = $Repo
$s.WindowStyle = 7                                               # minimised
$s.Description = "AutoEdit Studio-sessie (Claude Code voor de knoppen van de Studio)"
$s.Save()
Write-Host "added $Link"
