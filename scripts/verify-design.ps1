$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$requiredPaths = @('docs/REQUIREMENTS_TRACEABILITY.md', 'docs/ARCHITECTURE.md', 'docs/BACKLOG.md', 'docs/adr/0001-harness-first.md', 'docs/adr/0002-durable-workflow.md', 'docs/adr/0003-evidence-and-evaluation.md', 'docs/adr/0004-stack-and-egress.md')
foreach ($relativePath in $requiredPaths) {
    $content = Get-Content -LiteralPath (Join-Path $workspaceRoot $relativePath) -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($content)) { throw "Empty document: $relativePath" }
}
Write-Output 'PASS seven required design documents exist and are nonempty'
$matrix = Get-Content -LiteralPath (Join-Path $workspaceRoot 'docs/REQUIREMENTS_TRACEABILITY.md') -Raw -Encoding UTF8
$architecture = Get-Content -LiteralPath (Join-Path $workspaceRoot 'docs/ARCHITECTURE.md') -Raw -Encoding UTF8
$backlog = Get-Content -LiteralPath (Join-Path $workspaceRoot 'docs/BACKLOG.md') -Raw -Encoding UTF8
$evalPlan = Get-Content -LiteralPath (Join-Path $workspaceRoot 'docs/EVALUATION_PLAN.md') -Raw -Encoding UTF8
foreach ($group in @(@{Prefix='FR-';Count=9;Text=$matrix}, @{Prefix='A';Count=8;Text=$matrix}, @{Prefix='D';Count=17;Text=$matrix}, @{Prefix='T';Count=8;Text=$matrix}, @{Prefix='S';Count=4;Text=$matrix}, @{Prefix='UI';Count=6;Text=$matrix}, @{Prefix='C';Count=15;Text=$architecture}, @{Prefix='B';Count=16;Text=$backlog}, @{Prefix='D';Count=17;Text=$evalPlan})) {
    1..$group.Count | ForEach-Object {
        $id = '{0}{1:00}' -f $group.Prefix, $_
        if ($group.Text -notmatch ('(?m)^\| ' + [regex]::Escape($id) + ' \|')) { throw "Missing definition: $id" }
    }
}
Write-Output 'PASS FR-01..09, A01..08, D01..17, T01..08, S01..04, UI01..06, C01..15 and B01..16 definitions'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$sources = Get-Content -LiteralPath (Join-Path $workspaceRoot 'docs/source-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$archive = [IO.Compression.ZipFile]::OpenRead((Join-Path $workspaceRoot $sources.sources[0].path))
try {
    $reader = [IO.StreamReader]::new($archive.GetEntry('word/document.xml').Open())
    try { [xml]$xml = $reader.ReadToEnd() } finally { $reader.Dispose() }
    $ns = [Xml.XmlNamespaceManager]::new($xml.NameTable)
    $ns.AddNamespace('w', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
    $brdText = ($xml.SelectNodes('//w:body//w:p', $ns) | ForEach-Object {
        ($_.SelectNodes('.//w:t', $ns) | ForEach-Object { $_.'#text' }) -join ''
    }) -join "`n"
    $acceptanceRows = [regex]::Matches($matrix, '(?m)^\| A\d{2} \| [^|]+ \| ([^|]+) \|')
    if ($acceptanceRows.Count -ne 8) { throw 'Expected eight acceptance rows' }
    foreach ($row in $acceptanceRows) {
        $target = $row.Groups[1].Value.Trim()
        if (-not $brdText.Contains($target)) { throw "Target does not match original BRD: $target" }
    }
} finally { $archive.Dispose() }
Write-Output 'PASS all eight acceptance target strings occur verbatim in original BRD'
Write-Output 'Design checks passed. This structural check does not execute application or evaluation tests.'
