<#
.SYNOPSIS
    Registers the SaaS Manager (web + Celery worker + Celery beat) as Windows
    services using NSSM.

.DESCRIPTION
    Run from an elevated PowerShell in the project root:
        powershell -ExecutionPolicy Bypass -File scripts\install_services.ps1

    Prerequisites:
      * NSSM on PATH (https://nssm.cc)  — `nssm version` must work
      * A virtualenv at .\venv with requirements.txt installed
      * .env configured (see .env.example)

    Redis and PostgreSQL are assumed to run as their own services; this script
    only manages the Python processes.

.NOTES
    The Celery worker on Windows must use --pool=solo (no fork support).
#>

param(
    [string]$ServicePrefix = "SaasManager",
    [string]$VenvPath      = ".\venv",
    [string]$AppDir        = (Get-Location).Path,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "This script must be run as Administrator."
    }
}

function Get-Nssm {
    $nssm = Get-Command nssm -ErrorAction SilentlyContinue
    if (-not $nssm) { throw "nssm was not found on PATH. Install it from https://nssm.cc and retry." }
    return $nssm.Source
}

function Register-Service {
    param(
        [string]$Nssm,
        [string]$Name,
        [string]$DisplayName,
        [string]$PythonExe,
        [string]$Arguments,
        [string]$LogPath
    )

    $existing = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "Service $Name already exists — updating."
        & $Nssm stop    $Name | Out-Null
        & $Nssm remove  $Name confirm | Out-Null
    }

    Write-Host "Registering $Name ..."
    & $Nssm install    $Name $PythonExe $Arguments | Out-Null
    & $Nssm set        $Name AppDirectory $AppDir    | Out-Null
    & $Nssm set        $Name DisplayName  $DisplayName | Out-Null
    & $Nssm set        $Name Start        SERVICE_AUTO_START | Out-Null
    & $Nssm set        $Name AppStdout    $LogPath   | Out-Null
    & $Nssm set        $Name AppStderr    $LogPath   | Out-Null
    & $Nssm set        $Name AppRotateFiles 1        | Out-Null
    & $Nssm set        $Name AppRotateBytes 10485760 | Out-Null
    & $Nssm start      $Name | Out-Null
    Write-Host "Service $Name started."
}

function Unregister-Service {
    param([string]$Name)
    $existing = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "Removing $Name ..."
        & nssm stop   $Name | Out-Null
        & nssm remove $Name confirm | Out-Null
    }
}

$names = @{
    Web    = "$ServicePrefix-Web"
    Worker = "$ServicePrefix-Worker"
    Beat   = "$ServicePrefix-Beat"
}

if ($Uninstall) {
    Assert-Admin
    foreach ($n in $names.Values) { Unregister-Service -Name $n }
    Write-Host "All SaaS Manager services removed."
    exit 0
}

Assert-Admin
$nssm = Get-Nssm

$pythonExe = (Resolve-Path (Join-Path $VenvPath "Scripts\python.exe")).Path
$logDir = Join-Path $AppDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# 1. Web (uvicorn)
Register-Service -Nssm $nssm -Name $names.Web -DisplayName "SaaS Manager Web" `
    -PythonExe $pythonExe `
    -Arguments "-m uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers" `
    -LogPath (Join-Path $logDir "web.log")

# 2. Celery worker (Windows requires --pool=solo)
Register-Service -Nssm $nssm -Name $names.Worker -DisplayName "SaaS Manager Worker" `
    -PythonExe $pythonExe `
    -Arguments "-m celery -A app.workers.celery_app.celery_app worker --loglevel=INFO --pool=solo --concurrency=1 -Q default,updates,backups" `
    -LogPath (Join-Path $logDir "worker.log")

# 3. Celery beat (scheduler)
Register-Service -Nssm $nssm -Name $names.Beat -DisplayName "SaaS Manager Scheduler" `
    -PythonExe $pythonExe `
    -Arguments "-m celery -A app.workers.celery_app.celery_app beat --loglevel=INFO" `
    -LogPath (Join-Path $logDir "beat.log")

Write-Host ""
Write-Host "Done. Services:" -ForegroundColor Green
foreach ($n in $names.Values) { Write-Host "  - $n" }
Write-Host ""
Write-Host "Check status:  Get-Service $ServicePrefix*"
Write-Host "Logs:          $logDir"
Write-Host "Uninstall:     powershell -ExecutionPolicy Bypass -File scripts\install_services.ps1 -Uninstall"
