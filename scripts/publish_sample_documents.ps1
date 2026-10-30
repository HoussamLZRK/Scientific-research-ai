#Requires -Version 5.1
<#
Finalise le module Sample Documents du projet Scientific Research AI.
Usage depuis la racine du projet :
  powershell -ExecutionPolicy Bypass -File scripts/publish_sample_documents.ps1 -Publish
Aucun PDF, dataset, essai DBLP ou fichier existant non suivi n'est ajoute.
#>
param([switch]$Publish)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$required = @(
    'config/sample_documents.json',
    'docs/SAMPLE_DOCUMENTS.md',
    'scripts/download_sample_documents.py',
    'scripts/validate_sample_documents.py',
    'tests/test_sample_documents.py',
    'data/sample_documents/.gitignore',
    'scripts/publish_sample_documents.ps1'
)

Write-Host '[1/5] Verification du dossier et des fichiers...' -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath 'docker/hdfs/compose.yaml' -PathType Leaf)) {
    throw 'Lance ce script a la racine du depot Scientific-research-ai (dossier de docker/hdfs).'
}
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe' -PathType Leaf)) {
    throw 'Python virtuel introuvable : .venv/Scripts/python.exe'
}
foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Fichier manquant : $path. Verifie que le module Sample Documents est bien copie."
    }
}
$gitIgnore = Get-Content -LiteralPath 'data/sample_documents/.gitignore' -Raw
if ($gitIgnore -notmatch '(?m)^\s*\*\.pdf\s*$') {
    throw 'Le .gitignore des PDF ne contient pas une regle *.pdf. Arret pour securite.'
}

Write-Host '[2/5] Verification des 3 tests Sample Documents...' -ForegroundColor Cyan
& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -p 'test_sample_documents.py' -v
if ($LASTEXITCODE -ne 0) { throw 'Tests Sample Documents en echec. Aucun commit.' }

Write-Host '[3/5] Verification des quatre PDF locaux...' -ForegroundColor Cyan
& '.\.venv\Scripts\python.exe' scripts/validate_sample_documents.py
if ($LASTEXITCODE -ne 0) { throw 'Validation locale des PDF en echec. Aucun commit.' }

Write-Host '[4/5] Verification de la branche et de l index Git...' -ForegroundColor Cyan
$branch = (& git branch --show-current)
if ($LASTEXITCODE -ne 0) { throw 'Impossible de lire la branche Git.' }
if ($branch.Trim() -ne 'main') { throw "Branche actuelle : '$branch'. La branche main est requise." }
$stagedBefore = @(& git diff --cached --name-only)
if ($LASTEXITCODE -ne 0) { throw 'Impossible de verifier les fichiers indexes.' }
if ($stagedBefore.Count -gt 0) {
    throw "Des fichiers sont deja indexes : $($stagedBefore -join ', '). Verifie-les avant de relancer."
}

Write-Host 'Fichiers autorises pour le nouveau commit :' -ForegroundColor Yellow
foreach ($path in $required) { Write-Host " - $path" }
if (-not $Publish) {
    Write-Host 'Mode verification seulement. Relance avec -Publish pour ajouter, committer et pousser.' -ForegroundColor Green
    exit 0
}

Write-Host '[5/5] Creation du commit et publication sur GitHub...' -ForegroundColor Cyan
& git add -- $required
if ($LASTEXITCODE -ne 0) { throw 'git add a echoue.' }
$staged = @(& git diff --cached --name-only)
if ($LASTEXITCODE -ne 0) { throw 'Impossible de verifier les fichiers indexes.' }
$unexpected = @($staged | Where-Object { $_ -notin $required })
if ($unexpected.Count -gt 0) {
    throw "Fichiers inattendus indexes : $($unexpected -join ', '). Publication annulee."
}
if (@($staged | Where-Object { $_ -match '\.pdf$' -or ($_ -like 'data/*' -and $_ -ne 'data/sample_documents/.gitignore') }).Count -gt 0) {
    throw 'Des fichiers de donnees sont indexes. Publication annulee.'
}
& git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw 'git diff --cached --check a signale une erreur. Publication annulee.' }
if ($staged.Count -eq 0) {
    Write-Host 'Aucune modification nouvelle a publier. Les fichiers sont deja suivis.' -ForegroundColor Yellow
    exit 0
}
& git commit -m 'feat(data): add reproducible scientific sample documents'
if ($LASTEXITCODE -ne 0) { throw 'Le commit Git a echoue. Rien n a ete pousse.' }
& git push origin main
if ($LASTEXITCODE -ne 0) { throw 'Le push a echoue. Le commit reste local; aucun fichier n a ete supprime.' }
Write-Host ''
Write-Host 'PUBLICATION SAMPLE DOCUMENTS TERMINEE.' -ForegroundColor Green
& git log -1 --oneline
& git status --short
Write-Host 'Remarque : les anciens fichiers non suivis sont conserves localement.' -ForegroundColor Yellow
