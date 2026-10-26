param(
    [ValidateSet('install', 'lint', 'typecheck', 'test', 'build', 'check', 'api', 'web', 'e2e')]
    [string]$Action = 'check',
    [string]$Python = '3.13'
)
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$env:NEXT_TELEMETRY_DISABLED = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:LANGSMITH_TRACING = 'false'
$env:LANGCHAIN_TRACING_V2 = 'false'
$env:LANGGRAPH_STRICT_MSGPACK = 'true'
$env:UV_CACHE_DIR = Join-Path $workspaceRoot '.cache/uv'

function Invoke-Backend([scriptblock]$Command) {
    Push-Location (Join-Path $workspaceRoot 'backend')
    try { & $Command; if ($LASTEXITCODE -ne 0) { throw "Backend command failed ($LASTEXITCODE)" } }
    finally { Pop-Location }
}
function Invoke-Frontend([scriptblock]$Command) {
    Push-Location (Join-Path $workspaceRoot 'frontend')
    try { & $Command; if ($LASTEXITCODE -ne 0) { throw "Frontend command failed ($LASTEXITCODE)" } }
    finally { Pop-Location }
}

switch ($Action) {
    'install' {
        Invoke-Backend { uv sync --frozen --extra test --python $Python }
        Invoke-Frontend { npm ci --no-audit --fund=false --cache ../.cache/npm }
    }
    'lint' {
        Invoke-Backend { uv run --frozen --extra test --no-sync ruff check app tests tools migrations }
        Invoke-Frontend { npm run lint }
    }
    'typecheck' {
        Invoke-Backend { uv run --frozen --extra test --no-sync mypy }
        Invoke-Frontend { npm run typecheck }
    }
    'test' {
        Invoke-Backend { uv run --frozen --extra test --no-sync pytest -q -m 'not integration' -p no:cacheprovider }
        Invoke-Frontend { npm test }
    }
    'build' {
        Invoke-Backend { uv build --offline }
        Invoke-Backend { uv run --frozen --extra test --no-sync alembic heads }
        Invoke-Frontend { npm run build }
    }
    'check' {
        foreach ($step in @('lint', 'typecheck', 'test', 'build')) {
            & $PSCommandPath -Action $step -Python $Python
        }
    }
    'api' { Invoke-Backend { uv run --frozen --no-sync uvicorn app.main:app --host 127.0.0.1 --port 8000 } }
    'web' { Invoke-Frontend { npm run dev } }
    'e2e' { Invoke-Frontend { npm run test:e2e } }
}
