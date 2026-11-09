param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('apply', 'restore')]
    [string]$Command,
    [string]$GameDir,
    [switch]$NoPause
)
$ErrorActionPreference = 'Stop'
$patchRoot = Split-Path -Parent $PSScriptRoot
$resultCode = 0
try {
    if (Get-Process Myst4 -ErrorAction SilentlyContinue) {
        throw 'Myst IV を終了してから実行してください。'
    }
    $venvPython = Join-Path $patchRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        $launcher = Get-Command py -CommandType Application -ErrorAction SilentlyContinue
        $pythonPrefix = @()
        if ($launcher) {
            $pythonPrefix = @('-3')
        } else {
            $launcher = Get-Command python -CommandType Application -ErrorAction SilentlyContinue
        }
        if (-not $launcher) { throw 'Python 3.10以降をインストールしてから、もう一度実行してください。' }
        & $launcher.Source @pythonPrefix -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.10以降が必要です。' }
        & $launcher.Source @pythonPrefix -m venv (Join-Path $patchRoot '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Pythonの作業環境を作成できませんでした。' }
    }
    if ($Command -eq 'apply') {
        & $venvPython -c 'import importlib.util, sys; s=importlib.util.find_spec("PIL"); sys.exit(0 if s and __import__("PIL").__version__ == "12.3.0" else 1)'
        if ($LASTEXITCODE -ne 0) {
            Write-Host '初回のみ、Pillowをダウンロードしてこのフォルダーへインストールします。'
            & $venvPython -m pip install --disable-pip-version-check -r (Join-Path $patchRoot 'requirements.txt')
            if ($LASTEXITCODE -ne 0) { throw 'Pillowのインストールに失敗しました。ネットワーク接続を確認してください。' }
        }
    }
    $patchArgs = @((Join-Path $PSScriptRoot 'patch.py'), $Command)
    if ($GameDir) { $patchArgs += @('--game-dir', $GameDir) }
    & $venvPython @patchArgs
    if ($LASTEXITCODE -ne 0) { throw '処理を完了できませんでした。上に表示されたエラーを確認してください。' }
} catch {
    $resultCode = 1
    Write-Host ('エラー: ' + $_.Exception.Message) -ForegroundColor Red
} finally {
    if (-not $NoPause) { $null = Read-Host 'Enterキーで閉じます' }
}
exit $resultCode
