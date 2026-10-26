param([ValidateSet('start', 'prepare', 'test', 'stop')][string]$Action)
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$env:DO_NOT_TRACK = '1'
$env:SUPABASE_TELEMETRY_DISABLED = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:LANGSMITH_TRACING = 'false'
$env:LANGCHAIN_TRACING_V2 = 'false'
$env:LANGGRAPH_STRICT_MSGPACK = 'true'
$env:UV_CACHE_DIR = Join-Path $workspaceRoot '.cache/uv'
Push-Location $workspaceRoot
try {
    if ($Action -eq 'start' -or $Action -eq 'stop') {
        # Capture all CLI output: its normal success text contains credentials.
        $ErrorActionPreference = 'Continue' # Windows PowerShell treats native stderr progress as an error record.
        if ($Action -eq 'start') {
            $captured = npm exec --yes --package=supabase@2.122.0 --cache .cache/npm -- supabase start --exclude studio,realtime,storage-api,imgproxy,edge-runtime,logflare,vector,supavisor,postgres-meta 2>&1
        } else {
            $captured = npm exec --offline --yes --package=supabase@2.122.0 --cache .cache/npm -- supabase stop 2>&1
        }
        $nativeExit = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
        if ($nativeExit -ne 0) { throw "Local Supabase $Action failed (exit $nativeExit); credential-bearing CLI output suppressed." }
        Write-Output "PASS local Supabase $Action; credentials not displayed"
    } else {
        Push-Location (Join-Path $workspaceRoot 'backend')
        try {
            if ($Action -eq 'prepare') {
                uv run --frozen --extra test --no-sync python tools/prepare_local_auth.py
            } else {
                $previous = $env:LATHER_INTEGRATION_CONFIG
                try {
                    $env:LATHER_INTEGRATION_CONFIG = Join-Path $workspaceRoot '.cache/auth-stage.json'
                    uv run --frozen --extra test --no-sync pytest -q -m integration -p no:cacheprovider
                } finally { $env:LATHER_INTEGRATION_CONFIG = $previous }
            }
            if ($LASTEXITCODE -ne 0) { throw "Local auth $Action failed (exit $LASTEXITCODE)" }
        } finally { Pop-Location }
    }
} finally { Pop-Location }
