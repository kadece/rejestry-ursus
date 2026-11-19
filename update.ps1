<#
.SYNOPSIS
    Aktualizuje stronę z wykazami Ursus i opcjonalnie publikuje ją dalej.

.EXAMPLE
    .\update.ps1
    .\update.ps1 -Deploy 'C:\inetpub\wwwroot\wykazy'
    .\update.ps1 -Years '2024-2026'

.NOTES
    Roczniki 2019-2020 urzad publikowal jako PDF-y, wiec build
    potrzebuje modulu pdfplumber:
        python -m pip install openpyxl pdfplumber
    Bez niego build pominie te dwa lata i pojdzie dalej.

.EXAMPLE
    # rejestracja zadania w Harmonogramie zadań (poniedziałki, 6:00)
    .\update.ps1 -RegisterTask
#>
[CmdletBinding()]
param(
    [string]$Years,          # np. '2024-2026'; domyślnie wszystkie od 2019
    [string]$Deploy,
    [switch]$RegisterTask,
    [switch]$Offline
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $root 'logs'
$log = Join-Path $logDir ('update-{0}.log' -f (Get-Date -Format 'yyyy-MM'))

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-Log($msg) {
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path $log -Value $line -Encoding UTF8
}

# --- rejestracja zadania ---------------------------------------------------
if ($RegisterTask) {
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' `
        -Argument ('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $PSCommandPath) `
        -WorkingDirectory $root
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 6am
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd

    Register-ScheduledTask -TaskName 'Wykazy Ursus - aktualizacja' `
        -Action $action -Trigger $trigger -Settings $settings `
        -Description 'Pobiera rejestry z ursus.um.warszawa.pl i przebudowuje stronę.' -Force | Out-Null

    Write-Host 'Zadanie "Wykazy Ursus - aktualizacja" zarejestrowane (poniedziałki, 6:00).' -ForegroundColor Green
    return
}

# --- aktualizacja ----------------------------------------------------------
$scope = if ($Years) { $Years } else { 'wszystkie od 2019' }
Write-Log ("Start aktualizacji (roczniki: {0})" -f $scope)

Push-Location $root
try {
    $buildArgs = @('build.py')
    if ($Years) { $buildArgs += @('--years', $Years) } else { $buildArgs += '--all' }
    if ($Offline) { $buildArgs += '--offline' }

    $out = & python @buildArgs 2>&1
    $out | ForEach-Object { Write-Log $_ }

    if ($LASTEXITCODE -ne 0) { throw "build.py zakończył się kodem $LASTEXITCODE" }

    $site = Join-Path $root 'site\index.html'
    if (-not (Test-Path $site)) { throw 'Nie powstał plik site\index.html' }

    $size = [math]::Round((Get-Item $site).Length / 1KB)
    Write-Log "Strona wygenerowana: site\index.html ($size kB)"

    if ($Deploy) {
        New-Item -ItemType Directory -Force -Path $Deploy | Out-Null
        Copy-Item $site (Join-Path $Deploy 'index.html') -Force
        Write-Log "Opublikowano do: $Deploy"
    }

    Write-Log 'Zakończono pomyślnie'
}
catch {
    Write-Log "BŁĄD: $($_.Exception.Message)"
    exit 1
}
finally {
    Pop-Location
}
