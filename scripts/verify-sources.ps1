$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $workspaceRoot 'docs/source-manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.sources.Count -ne 3) { throw 'Expected three authoritative sources.' }
foreach ($source in $manifest.sources) {
    $sourcePath = Join-Path $workspaceRoot $source.path
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) { throw "Missing source: $($source.path)" }
    $actualHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $source.sha256) { throw "Source changed: $($source.path). Review and explicitly update the baseline." }
    Write-Output "PASS source integrity: $($source.path)"
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$brdPath = Join-Path $workspaceRoot $manifest.sources[0].path
$archive = [IO.Compression.ZipFile]::OpenRead($brdPath)
try {
    $reader = [IO.StreamReader]::new($archive.GetEntry('word/document.xml').Open())
    try { [xml]$xml = $reader.ReadToEnd() } finally { $reader.Dispose() }
    $ns = [Xml.XmlNamespaceManager]::new($xml.NameTable)
    $ns.AddNamespace('w', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
    $text = ($xml.SelectNodes('//w:t', $ns) | ForEach-Object { $_.'#text' }) -join ' '
    1..9 | ForEach-Object { if ($text -notmatch ('FR-{0:00}' -f $_)) { throw "Missing BRD requirement $_" } }
    Write-Output 'PASS BRD readable: FR-01 through FR-09 present'
} finally { $archive.Dispose() }
Write-Output 'Stage 0 source checks passed. Application acceptance targets remain unevaluated.'
