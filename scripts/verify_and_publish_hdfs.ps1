# Scientific Research AI - Validation HDFS et publication GitHub
# A executer depuis Windows PowerShell :
#   powershell -ExecutionPolicy Bypass -File scripts/verify_and_publish_hdfs.ps1
# Pour publier apres validation :
#   powershell -ExecutionPolicy Bypass -File scripts/verify_and_publish_hdfs.ps1 -Publish
# Aucun fichier PDF, JSONL ou volume Docker n'est modifie.
param(
    [switch]$Publish
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$originalLocation = Get-Location

function Invoke-External {
    param(
        [string]$Description,
        [scriptblock]$Action
    )
    # Sous Windows PowerShell 5.1, les messages sur stderr des programmes natifs
    # (ex. git push) ne doivent pas etre interpretes comme un echec automatique.
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $result = & $Action 2>&1
        $code = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $oldPreference }
    if ($code -ne 0) {
        throw "$Description : erreur (code $code). $($result -join ' ')"
    }
    return $result
}

try {
    Set-Location -LiteralPath $repoRoot
    $compose = 'docker/hdfs/compose.yaml'
    if (-not (Test-Path -LiteralPath $compose -PathType Leaf)) {
        throw 'Configuration HDFS introuvable : docker/hdfs/compose.yaml.'
    }

    $items = @(
        [pscustomobject]@{ Local = 'data/raw/publications_v2.jsonl'; Remote = '/scientific-research-ai/raw/crawler/publications_v2.jsonl' },
        [pscustomobject]@{ Local = 'data/raw/publications_pmlr_v3.jsonl'; Remote = '/scientific-research-ai/raw/crawler/publications_pmlr_v3.jsonl' },
        [pscustomobject]@{ Local = 'data/processed/publications_multisource_v3.jsonl'; Remote = '/scientific-research-ai/processed/publications_multisource_v3.jsonl' },
        [pscustomobject]@{ Local = 'data/sample_documents/acl_rag_retrievers_2024.pdf'; Remote = '/scientific-research-ai/raw/sample_documents/acl_rag_retrievers_2024.pdf' },
        [pscustomobject]@{ Local = 'data/sample_documents/pmlr_retrieval_models_2024.pdf'; Remote = '/scientific-research-ai/raw/sample_documents/pmlr_retrieval_models_2024.pdf' },
        [pscustomobject]@{ Local = 'data/sample_documents/plos_llm_science_2024.pdf'; Remote = '/scientific-research-ai/raw/sample_documents/plos_llm_science_2024.pdf' },
        [pscustomobject]@{ Local = 'data/sample_documents/hal_wikidata_llm_2024.pdf'; Remote = '/scientific-research-ai/raw/sample_documents/hal_wikidata_llm_2024.pdf' }
    )

    Write-Host '1/3 - Verification de la sante HDFS...' -ForegroundColor Cyan
    $fsck = Invoke-External -Description 'HDFS fsck' -Action {
        & docker compose -f $compose exec -T namenode hdfs fsck /scientific-research-ai -files -blocks
    }
    $fsckText = $fsck -join "`n"
    if ($fsckText -notmatch 'Status:\s*HEALTHY' -or $fsckText -notmatch 'Total files:\s*7\b') {
        throw 'HDFS doit etre HEALTHY et contenir exactement 7 fichiers. Consulte le rapport fsck.'
    }
    Write-Host 'OK : HDFS HEALTHY, 7 fichiers.' -ForegroundColor Green

    Write-Host "`n2/3 - Comparaison SHA-256 (Windows / HDFS)..." -ForegroundColor Cyan
    $verified = @()
    foreach ($item in $items) {
        if (-not (Test-Path -LiteralPath $item.Local -PathType Leaf)) {
            throw "Fichier Windows absent : $($item.Local)"
        }

        $localHash = (Get-FileHash -LiteralPath $item.Local -Algorithm SHA256).Hash.ToLowerInvariant()

        # Le tube est execute *dans Linux* et non dans PowerShell Windows.
        # Aucun guillemet Bash imbrique, afin d'eviter les erreurs de parsing Windows.
        $bashCommand = 'set -o pipefail; hdfs dfs -cat ' + $item.Remote + ' | sha256sum'
        $hashOutput = Invoke-External -Description "SHA HDFS $($item.Remote)" -Action {
            & docker compose -f $compose exec -T namenode bash -c $bashCommand
        }
        $hashText = ($hashOutput -join "`n").Trim()
        if ($hashText -notmatch '(?i)^([a-f0-9]{64})\s+') {
            throw "Empreinte HDFS illisible pour : $($item.Remote). Reponse : $hashText"
        }
        $remoteHash = $Matches[1].ToLowerInvariant()
        if ($localHash -ne $remoteHash) {
            throw "Empreintes DIFFERENTES : $($item.Remote)"
        }
        $verified += [pscustomobject]@{ File = $item.Remote; SHA256 = $localHash }
        Write-Host "OK : $($item.Remote)" -ForegroundColor Green
    }
    Write-Host "`nVALIDATION HDFS : 7/7 fichiers identiques." -ForegroundColor Green

    # Generer une preuve technique reproductible, sans copier les donnees dans GitHub.
    $lines = @(
        '# Validation HDFS - Scientific Research AI',
        '',
        "Date de verification (UTC) : $((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss'))",
        '',
        '- Hadoop : 3.4.3 (Docker Compose)',
        '- Architecture : 1 NameNode + 1 DataNode, replication 1',
        '- Controle fsck : HEALTHY ; 7 fichiers et 7 blocs valides',
        '- Comparaison SHA-256 locale / HDFS : 7/7 identiques',
        '',
        '| Chemin HDFS | SHA-256 |',
        '|---|---|'
    )
    foreach ($entry in $verified) {
        $lines += "| ``$($entry.File)`` | ``$($entry.SHA256)`` |"
    }
    $lines += @('', 'Ce rapport ne contient ni PDF ni JSONL. Le stockage fonctionne sur un seul ordinateur ; la replication 1 ne procure pas de redondance.', '')
    $reportPath = 'docs/HDFS_VALIDATION.md'
    $lines | Set-Content -LiteralPath $reportPath -Encoding UTF8
    Write-Host "Rapport genere : $reportPath" -ForegroundColor Green

    if (-not $Publish) {
        Write-Host "`n3/3 - Publication non demandee. Pour publier :" -ForegroundColor Yellow
        Write-Host 'powershell -ExecutionPolicy Bypass -File scripts/verify_and_publish_hdfs.ps1 -Publish'
        return
    }

    Write-Host "`n3/3 - Publication GitHub des fichiers HDFS uniquement..." -ForegroundColor Cyan
    $branch = (Invoke-External -Description 'Verification branche Git' -Action { & git branch --show-current } | Select-Object -Last 1).Trim()
    if ($branch -ne 'main') {
        throw "Branche actuelle '$branch' : publication annulee pour eviter un push sur la mauvaise branche."
    }
    $stagedBefore = @(Invoke-External -Description 'Verification index Git' -Action { & git diff --cached --name-only })
    if ($stagedBefore.Count -gt 0) {
        throw 'Des fichiers sont deja indexes dans Git. Publication annulee pour ne pas les inclure dans ce commit.'
    }

    $toStage = @(
        'docker/hdfs/compose.yaml',
        'docker/hdfs/start-namenode.sh',
        'docker/hdfs/start-datanode.sh',
        'docker/hdfs/config/core-site.xml',
        'docker/hdfs/config/hdfs-site.xml',
        'scripts/upload_to_hdfs.ps1',
        'scripts/verify_and_publish_hdfs.ps1',
        'docs/HDFS_SETUP.md',
        'docs/HDFS_VALIDATION.md'
    )
    foreach ($path in $toStage) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Impossible de publier, fichier manquant : $path"
        }
    }
    Invoke-External -Description 'git add' -Action { & git add -- $toStage } | Out-Null
    Invoke-External -Description 'git diff --cached --check' -Action { & git diff --cached --check } | Out-Null
    & git diff --cached --quiet
    $hasChanges = $LASTEXITCODE
    if ($hasChanges -eq 0) {
        Write-Host 'Aucun nouveau changement HDFS a committer.' -ForegroundColor Yellow
        return
    }
    if ($hasChanges -ne 1) {
        throw 'Impossible de determiner les modifications indexees.'
    }

    Write-Host 'Fichiers prepares pour le commit :'
    & git diff --cached --stat
    Invoke-External -Description 'git commit' -Action {
        & git commit -m 'feat(hdfs): validate scientific document storage and integrity'
    } | ForEach-Object { Write-Host $_ }
    Invoke-External -Description 'git push origin main' -Action {
        & git push origin main
    } | ForEach-Object { Write-Host $_ }
    Write-Host "`nPUBLICATION GITHUB TERMINEE." -ForegroundColor Green
}
catch {
    Write-Host "`nERREUR : $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Set-Location $originalLocation
}
