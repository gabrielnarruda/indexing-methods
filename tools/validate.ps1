param(
    [switch]$Full,
    [string]$Name = 'local'
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$PythonPath = Join-Path $ProjectRoot '.venv/Scripts/python.exe'
Push-Location $ProjectRoot
try {
    if ($Full) {
        & $PythonPath -X utf8 -m poc fetch
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao obter corpus' }
        & $PythonPath -X utf8 -m poc index --corpus all
        if ($LASTEXITCODE -ne 0) { throw 'Falha na indexação' }
    }
    & $PythonPath -X utf8 -m pytest -q --junitxml=reports/validation/junit.xml
    if ($LASTEXITCODE -ne 0) { throw 'Testes falharam' }
    if ($Full) {
        & $PythonPath -X utf8 -m poc benchmark --name $Name --repetitions 3 --variants ABCDEF
        if ($LASTEXITCODE -ne 0) { throw 'Falha no benchmark; inspecione o manifesto' }
        & $PythonPath -X utf8 -m poc report --name $Name
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar relatório' }
        & $PythonPath -X utf8 tools/verify_run.py --name $Name
        if ($LASTEXITCODE -ne 0) { throw 'Falha na auditoria ponta a ponta' }
    }
} finally {
    Pop-Location
}
