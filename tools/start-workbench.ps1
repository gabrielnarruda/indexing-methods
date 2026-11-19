param(
    [switch]$Setup,
    [switch]$Services,
    [switch]$PrepareOnly,
    [int]$Port = 18766
)
$ErrorActionPreference = 'Stop'
$WorkbenchRoot = Split-Path $PSScriptRoot -Parent
$WorkbenchPython = Join-Path $WorkbenchRoot '.venv/Scripts/python.exe'
Push-Location $WorkbenchRoot
try {
    if ($Setup) {
        if (-not (Test-Path -LiteralPath $WorkbenchPython)) {
            uv --cache-dir .cache/uv venv .venv --python 3.12
            if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar o ambiente Python.' }
        }
        uv --cache-dir .cache/uv pip install --python $WorkbenchPython -r requirements.lock.txt
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar as dependências Python.' }
        npm --prefix frontend ci
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar as dependências da interface.' }
    }
    if ($Services) {
        docker compose up -d
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao iniciar os serviços locais.' }
    }
    if (-not (Test-Path -LiteralPath $WorkbenchPython)) { throw 'Execute este script com -Setup primeiro.' }
    if ($PrepareOnly) { return }
    npm --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao compilar a interface.' }
    Write-Host "Plataforma local: http://127.0.0.1:$Port"
    Write-Host 'As execuções ficam na fila persistente. Cancele runs na interface antes de encerrar todo o trabalho.'
    & $WorkbenchPython -X utf8 -m workbench --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'A API terminou com erro ou foi interrompida.' }
} finally {
    Pop-Location
}
