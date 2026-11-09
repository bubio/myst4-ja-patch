param([string]$GameDir, [switch]$NoPause)
& (Join-Path $PSScriptRoot 'restore_japanese.ps1') @PSBoundParameters
exit $LASTEXITCODE
