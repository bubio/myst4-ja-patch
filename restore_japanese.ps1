param([string]$GameDir, [switch]$NoPause)
& (Join-Path $PSScriptRoot 'tools/Invoke-Patch.ps1') -Command restore -GameDir $GameDir -NoPause:$NoPause
exit $LASTEXITCODE
