param([switch]$Browser, [string]$Url = 'http://127.0.0.1:18766')
$ErrorActionPreference = 'Stop'
$WorkbenchRoot = Split-Path $PSScriptRoot -Parent
Push-Location $WorkbenchRoot
try {
    & .venv/Scripts/python.exe -X utf8 -m pytest -q --junitxml=reports/validation/workbench-junit.xml
    if ($LASTEXITCODE -ne 0) { throw 'Os testes Python falharam.' }
    npm --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw 'O build ou a verificação TypeScript falhou.' }
    if ($Browser) {
        $env:WORKBENCH_URL = $Url
        node tools/verify-workbench.cjs
        if ($LASTEXITCODE -ne 0) { throw 'A verificação de interface falhou.' }
    }
} finally {
    Pop-Location
}
