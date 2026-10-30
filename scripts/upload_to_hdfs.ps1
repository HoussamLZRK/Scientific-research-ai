# Execute depuis la racine de Scientific-research-ai (PowerShell).
# Copie uniquement les fichiers verifies vers HDFS. Ne supprime aucune donnee locale.
$ErrorActionPreference = 'Stop'
$compose = 'docker/hdfs/compose.yaml'
if (-not (Test-Path $compose -PathType Leaf)) {
    throw 'compose.yaml introuvable : ouvre le terminal dans Scientific-research-ai.'
}
$docs = @(
    'acl_rag_retrievers_2024.pdf',
    'pmlr_retrieval_models_2024.pdf',
    'plos_llm_science_2024.pdf',
    'hal_wikidata_llm_2024.pdf'
)
$needed = @(
    'data/raw/publications_v2.jsonl',
    'data/raw/publications_pmlr_v3.jsonl',
    'data/processed/publications_multisource_v3.jsonl'
)
foreach ($name in $docs) { $needed += "data/sample_documents/$name" }
$missing = @($needed | Where-Object { -not (Test-Path $_ -PathType Leaf) })
if ($missing.Count -gt 0) {
    Write-Host 'STOP : fichiers sources manquants (aucun transfert lance) :' -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  $_" }
    exit 1
}

function Invoke-Hdfs {
    param([Parameter(Mandatory = $true)][string[]]$ArgsList)
    & docker compose -f $compose exec -T namenode hdfs dfs @ArgsList
    if ($LASTEXITCODE -ne 0) { throw "Commande HDFS echouee : $($ArgsList -join ' ')" }
}

Write-Host 'Verification des conteneurs HDFS...'
& docker compose -f $compose ps
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose indisponible.' }

Invoke-Hdfs -ArgsList @('-mkdir','-p','/scientific-research-ai/raw/crawler')
Invoke-Hdfs -ArgsList @('-mkdir','-p','/scientific-research-ai/raw/sample_documents')
Invoke-Hdfs -ArgsList @('-mkdir','-p','/scientific-research-ai/processed')

Invoke-Hdfs -ArgsList @('-put','-f','/project-data/raw/publications_v2.jsonl','/scientific-research-ai/raw/crawler/')
Invoke-Hdfs -ArgsList @('-put','-f','/project-data/raw/publications_pmlr_v3.jsonl','/scientific-research-ai/raw/crawler/')
Invoke-Hdfs -ArgsList @('-put','-f','/project-data/processed/publications_multisource_v3.jsonl','/scientific-research-ai/processed/')
foreach ($name in $docs) {
    Invoke-Hdfs -ArgsList @('-put','-f',"/project-data/sample_documents/$name",'/scientific-research-ai/raw/sample_documents/')
}

$destinations = @(
    '/scientific-research-ai/raw/crawler/publications_v2.jsonl',
    '/scientific-research-ai/raw/crawler/publications_pmlr_v3.jsonl',
    '/scientific-research-ai/processed/publications_multisource_v3.jsonl'
)
foreach ($name in $docs) { $destinations += "/scientific-research-ai/raw/sample_documents/$name" }
foreach ($item in $destinations) {
    Invoke-Hdfs -ArgsList @('-test','-e',$item)
}
Write-Host "`nSept fichiers verifies dans HDFS :" -ForegroundColor Green
Invoke-Hdfs -ArgsList @('-ls','-R','/scientific-research-ai')
Write-Host "`nTransfert termine : 3 JSONL + 4 PDF." -ForegroundColor Green
