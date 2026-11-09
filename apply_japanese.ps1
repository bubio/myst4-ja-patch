param([string]$GameDir, [switch]$NoPause)
& (Join-Path $PSScriptRoot 'tools/Invoke-Patch.ps1') -Command apply -GameDir $GameDir -NoPause:$NoPause
exit $LASTEXITCODE
