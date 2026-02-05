param(
  [Parameter(Mandatory = $true)]
  [string] $InputMd
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
  return (Resolve-Path (Join-Path $PSScriptRoot ".."))
}

$repoRoot = Resolve-RepoRoot
Set-Location $repoRoot

$helpDir = Join-Path $repoRoot "help_documents"
if (-not (Test-Path $helpDir)) {
  throw "help_documents folder not found at: $helpDir"
}

$inputPath = Join-Path $helpDir $InputMd
if (-not (Test-Path $inputPath)) {
  throw "Markdown file not found: $inputPath"
}

$outDir = Join-Path $repoRoot "html"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$stem = [System.IO.Path]::GetFileNameWithoutExtension($inputPath)
$outPath = Join-Path $outDir ($stem + ".html")

$venvPython = Join-Path $repoRoot "venv312\\Scripts\\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

$cssHref = "https://cdn.jsdelivr.net/npm/github-markdown-css@5/github-markdown.min.css"

$converter = Join-Path $repoRoot "scripts\\md_to_html.py"
if (-not (Test-Path $converter)) {
  throw "Converter script not found: $converter"
}

& $python $converter --input $inputPath --output $outPath --css $cssHref

if ($LASTEXITCODE -ne 0) {
  throw "Markdown conversion failed."
}

Write-Host "Wrote: $outPath"

