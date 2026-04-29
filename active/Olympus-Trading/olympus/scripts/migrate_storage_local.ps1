param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$LocalRoot = (Join-Path $env:USERPROFILE "OlympusLocal"),
    [switch]$UpdateEnv
)

$ErrorActionPreference = "Stop"

function Get-RunLiveProcesses {
    $escapedRoot = [Regex]::Escape($ProjectRoot)
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -like "python*" -and
            $_.CommandLine -match "run_live\.py" -and
            $_.CommandLine -match $escapedRoot
        } |
        Select-Object ProcessId, Name, CommandLine
}

function Copy-IfExists {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source)) {
        return
    }

    $parent = Split-Path -Parent $Destination
    if ($parent) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    $sourceItem = Get-Item -LiteralPath $Source
    if ($sourceItem.PSIsContainer) {
        if (-not (Test-Path -LiteralPath $Destination)) {
            New-Item -ItemType Directory -Path $Destination -Force | Out-Null
        }
        Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $Destination $_.Name) -Recurse -Force
        }
        return
    }

    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

function Set-OrAppendEnvVar {
    param(
        [Parameter(Mandatory = $true)][string]$EnvPath,
        [Parameter(Mandatory = $true)][string]$Key,
        [Parameter(Mandatory = $true)][string]$Value
    )

    $lines = if (Test-Path -LiteralPath $EnvPath) { Get-Content -LiteralPath $EnvPath } else { @() }
    $pattern = "^{0}=" -f [Regex]::Escape($Key)
    $updated = $false

    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match $pattern) {
            $lines[$i] = "$Key=$Value"
            $updated = $true
        }
    }

    if (-not $updated) {
        $lines += "$Key=$Value"
    }

    Set-Content -LiteralPath $EnvPath -Value $lines
}

$active = Get-RunLiveProcesses
if ($active) {
    Write-Error (
        "Olympus runtime is still running. Stop all run_live.py processes before migration.`n" +
        (($active | Format-Table -AutoSize | Out-String).Trim())
    )
}

$sourceData = Join-Path $ProjectRoot "data"
$targetData = Join-Path $LocalRoot "data"

foreach ($dir in @(
    $LocalRoot,
    $targetData,
    (Join-Path $targetData "cache"),
    (Join-Path $targetData "logs"),
    (Join-Path $targetData "trades"),
    (Join-Path $targetData "rankings"),
    (Join-Path $targetData "reports")
)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

Copy-IfExists -Source (Join-Path $sourceData "olympus.db") -Destination (Join-Path $targetData "olympus.db")
Copy-IfExists -Source (Join-Path $sourceData "olympus.db-wal") -Destination (Join-Path $targetData "olympus.db-wal")
Copy-IfExists -Source (Join-Path $sourceData "olympus.db-shm") -Destination (Join-Path $targetData "olympus.db-shm")
Copy-IfExists -Source (Join-Path $sourceData "cache") -Destination (Join-Path $targetData "cache")
Copy-IfExists -Source (Join-Path $sourceData "logs") -Destination (Join-Path $targetData "logs")
Copy-IfExists -Source (Join-Path $sourceData "trades") -Destination (Join-Path $targetData "trades")
Copy-IfExists -Source (Join-Path $sourceData "rankings") -Destination (Join-Path $targetData "rankings")
Copy-IfExists -Source (Join-Path $sourceData "reports") -Destination (Join-Path $targetData "reports")

$manifestPath = Join-Path $LocalRoot ("migration-manifest-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".txt")
$manifest = [System.Collections.Generic.List[string]]::new()
$manifest.Add("Olympus local storage migration")
$manifest.Add("Timestamp: $(Get-Date -Format o)")
$manifest.Add("ProjectRoot: $ProjectRoot")
$manifest.Add("LocalRoot: $LocalRoot")
$manifest.Add("")
$manifest.Add("Copied items:")

Get-ChildItem -LiteralPath $targetData -Recurse -File |
    Sort-Object FullName |
    ForEach-Object {
        $manifest.Add(("{0}`t{1}" -f $_.FullName, $_.Length))
    }

Set-Content -LiteralPath $manifestPath -Value $manifest

if ($UpdateEnv) {
    $envPath = Join-Path $ProjectRoot ".env"
    Set-OrAppendEnvVar -EnvPath $envPath -Key "CACHE_DIR" -Value (Join-Path $targetData "cache")
    Set-OrAppendEnvVar -EnvPath $envPath -Key "LOG_DIR" -Value (Join-Path $targetData "logs")
    Set-OrAppendEnvVar -EnvPath $envPath -Key "TRADES_DIR" -Value (Join-Path $targetData "trades")
    Set-OrAppendEnvVar -EnvPath $envPath -Key "RANKINGS_DIR" -Value (Join-Path $targetData "rankings")
    Set-OrAppendEnvVar -EnvPath $envPath -Key "DB_PATH" -Value (Join-Path $targetData "olympus.db")
}

Write-Output "Local storage copy complete."
Write-Output "LocalRoot: $LocalRoot"
Write-Output "Manifest: $manifestPath"
if ($UpdateEnv) {
    Write-Output "Updated .env to point runtime storage at $targetData"
} else {
    Write-Output "Run again with -UpdateEnv to switch Olympus to the copied local storage."
}
