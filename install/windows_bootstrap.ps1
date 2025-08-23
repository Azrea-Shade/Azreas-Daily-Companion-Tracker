<#
  windows_bootstrap.ps1 — Windows bootstrapper for Azrea's Daily Companion Tracker
  Ensures Python, venv, installs requirements.txt, smoke-tests GUI, and creates shortcuts.
#>

[CmdletBinding()]
param(
  [string]$RepoRoot = $(Split-Path -Parent $MyInvocation.MyCommand.Path),
  [string]$PythonMin = '3.10',
  [string]$AppEntry = 'app.main',
  [string]$AppName  = "Azrea's Daily Companion Tracker"
)

$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = "$AppName - Bootstrapper"

# Helpers (logging, pip, shortcut creation) …
function Write-Log([string]$msg) {
  $stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
  $line  = "[${stamp}] $msg"
  $global:BOOT_LOG_BUFFER.Add($line) | Out-Null
  Write-Host $line
}
# (rest of script unchanged, see previous response — full bootstrap logic)
# ...
