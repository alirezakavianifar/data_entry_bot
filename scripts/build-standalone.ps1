<#
.SYNOPSIS
    Builds a standalone, portable Windows executable (.exe) for Data Entry Bot.
.DESCRIPTION
    This script compiles the Data Entry Bot desktop application into a single standalone 
    executable using PyInstaller, packages the Playwright browser engine, driver, and 
    CustomTkinter UI assets, and optionally creates a portable distribution ready to copy 
    to any other PC.
.PARAMETER Clean
    Cleans previous build, dist, and temporary artifacts before building.
.PARAMETER BundleBrowser
    Downloads and copies the Playwright Chromium browser binaries into a portable 'browsers'
    folder alongside the executable, enabling 100% offline functionality on PCs without Chrome.
.PARAMETER CreateZip
    Creates a compressed ZIP archive (DataEntryBot-Portable.zip) containing the executable,
    configuration templates, and optional browser binaries for easy sharing.
.PARAMETER OutputDir
    Destination directory for the build output. Defaults to 'dist'.
.EXAMPLE
    .\scripts\build-standalone.ps1
.EXAMPLE
    .\scripts\build-standalone.ps1 -Clean -BundleBrowser -CreateZip
#>

[CmdletBinding()]
param(
    [switch]$Clean,
    [switch]$BundleBrowser,
    [switch]$CreateZip,
    [string]$OutputDir = "dist"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location -Path $RootDir

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " Data Entry Bot - Standalone Executable Builder" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Root Directory  : $RootDir" -ForegroundColor Gray
Write-Host "Output Directory: $OutputDir" -ForegroundColor Gray
Write-Host "Clean Build     : $Clean" -ForegroundColor Gray
Write-Host "Bundle Browser  : $BundleBrowser" -ForegroundColor Gray
Write-Host "Create ZIP      : $CreateZip" -ForegroundColor Gray
Write-Host "-----------------------------------------------------------------" -ForegroundColor DarkGray

# 1. Verify Python & PyInstaller Environment
Write-Host "[1/6] Checking build environment and dependencies..." -ForegroundColor Yellow

try {
    $pythonVersion = python --version 2>&1
    Write-Host "      + Python detected: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Error "Python is not found in PATH. Please install Python 3.10+ and add it to PATH."
}

# Verify PyInstaller is installed
$hasPyinstaller = python -c "import PyInstaller; print('OK')" 2>$null
if ($hasPyinstaller -ne "OK") {
    Write-Host "      * PyInstaller not found. Installing pyinstaller..." -ForegroundColor Yellow
    python -m pip install --upgrade pyinstaller
} else {
    Write-Host "      + PyInstaller is installed" -ForegroundColor Green
}

# Verify Playwright is installed
$hasPlaywright = python -c "import playwright; print('OK')" 2>$null
if ($hasPlaywright -ne "OK") {
    Write-Host "      * Playwright not found. Installing playwright..." -ForegroundColor Yellow
    python -m pip install --upgrade playwright
} else {
    Write-Host "      + Playwright is installed" -ForegroundColor Green
}

# 2. Clean previous build artifacts if requested
if ($Clean) {
    Write-Host "[2/6] Cleaning previous build and dist artifacts..." -ForegroundColor Yellow
    if (Test-Path "$RootDir\build") { Remove-Item -Path "$RootDir\build" -Recurse -Force }
    if (Test-Path "$RootDir\$OutputDir") { Remove-Item -Path "$RootDir\$OutputDir" -Recurse -Force }
    Get-ChildItem -Path "$RootDir" -Filter "*.pyc" -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Force
    Write-Host "      + Cleanup complete" -ForegroundColor Green
} else {
    Write-Host "[2/6] Skipping clean step (use -Clean to perform full clean)" -ForegroundColor DarkGray
}

# 3. Ensure Playwright Chromium Browser is installed locally if BundleBrowser requested
if ($BundleBrowser) {
    Write-Host "[3/6] Ensuring Playwright Chromium binaries are available..." -ForegroundColor Yellow
    python -m playwright install chromium
    Write-Host "      + Playwright Chromium browser verified" -ForegroundColor Green
} else {
    Write-Host "[3/6] Browser mode: Multi-tier (uses host Chrome / Edge or auto-provisions Chromium)" -ForegroundColor DarkGray
}

# 4. Compile Standalone Executable using PyInstaller Spec
Write-Host "[4/6] Building standalone executable with PyInstaller..." -ForegroundColor Yellow

$specFile = "$RootDir\data_entry_bot.spec"
if (-not (Test-Path $specFile)) {
    Write-Error "Spec file '$specFile' not found."
}

$buildStartTime = Get-Date
python -m PyInstaller --noconfirm "$specFile"

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed with exit code $LASTEXITCODE."
}

$exePath = "$RootDir\$OutputDir\DataEntryBot.exe"
if (-not (Test-Path $exePath)) {
    Write-Error "Build finished but executable was not found at: $exePath"
}

$buildDuration = [math]::Round(((Get-Date) - $buildStartTime).TotalSeconds, 1)
$exeSize = (Get-Item $exePath).Length
$exeSizeMB = [math]::Round(($exeSize / 1MB), 2)
Write-Host "      + Successfully built $exePath ($exeSizeMB MB in $buildDuration s)" -ForegroundColor Green

# 5. Prepare Portable Distribution Files
Write-Host "[5/6] Preparing portable bundle files..." -ForegroundColor Yellow

# Copy sample configuration & templates
if (Test-Path "$RootDir\config\promo_links.json") {
    $destConfig = "$RootDir\$OutputDir\config"
    if (-not (Test-Path $destConfig)) { New-Item -ItemType Directory -Path $destConfig -Force | Out-Null }
    Copy-Item -Path "$RootDir\config\promo_links.json" -Destination "$destConfig\promo_links.json" -Force
}

if (Test-Path "$RootDir\.env.example") {
    Copy-Item -Path "$RootDir\.env.example" -Destination "$RootDir\$OutputDir\.env.example" -Force
}

if (Test-Path "$RootDir\Test.xlsx") {
    Copy-Item -Path "$RootDir\Test.xlsx" -Destination "$RootDir\$OutputDir\Test.xlsx" -Force
}

if (Test-Path "$RootDir\GOOGLE_SHEETS_SETUP_GUIDE.md") {
    Copy-Item -Path "$RootDir\GOOGLE_SHEETS_SETUP_GUIDE.md" -Destination "$RootDir\$OutputDir\GOOGLE_SHEETS_SETUP_GUIDE.md" -Force
}

# Create a QuickStart README for the end user on the other PC
$readmeContent = @"
# Data Entry Bot - Portable Standalone Edition

## How to Run:
1. Simply double-click DataEntryBot.exe to open the Desktop GUI application.
2. Select your data source (Local Excel file 'Test.xlsx' or Google Sheets).
3. Select your target websites and click Start Automation.

## Browser Support:
- The bot automatically connects to your local Google Chrome or Microsoft Edge browser.
- If no browser is installed, it will automatically download its internal Chromium engine on first launch.

## Data and Logs:
- State database (state.db) and logs (logs/) are stored right here alongside the .exe.
- Promo links configuration can be customized in the UI or in config/promo_links.json.
"@

Set-Content -Path "$RootDir\$OutputDir\README-PORTABLE.txt" -Value $readmeContent -Encoding UTF8

# Bundle Playwright Chromium directory if requested
if ($BundleBrowser) {
    $localMsPlaywright = "$env:LOCALAPPDATA\ms-playwright"
    if (Test-Path $localMsPlaywright) {
        Write-Host "      * Copying Chromium binaries into '$OutputDir\browsers'..." -ForegroundColor Yellow
        $destBrowsers = "$RootDir\$OutputDir\browsers"
        if (-not (Test-Path $destBrowsers)) { New-Item -ItemType Directory -Path $destBrowsers -Force | Out-Null }
        Copy-Item -Path "$localMsPlaywright\*" -Destination $destBrowsers -Recurse -Force
        Write-Host "      + Bundled offline Chromium browser" -ForegroundColor Green
    }
}

# 6. Create ZIP archive if requested
if ($CreateZip) {
    Write-Host "[6/6] Creating portable ZIP package..." -ForegroundColor Yellow
    $zipPath = "$RootDir\DataEntryBot-Portable.zip"
    if (Test-Path $zipPath) { Remove-Item -Path $zipPath -Force }
    
    $distItems = Get-ChildItem -Path "$RootDir\$OutputDir" -Exclude "*.zip"
    Compress-Archive -Path $distItems.FullName -DestinationPath $zipPath -Force
    $zipSize = (Get-Item $zipPath).Length
    $zipSizeMB = [math]::Round(($zipSize / 1MB), 2)
    Write-Host "      + Created $zipPath ($zipSizeMB MB)" -ForegroundColor Green
} else {
    Write-Host "[6/6] Skipping ZIP creation (use -CreateZip to generate .zip archive)" -ForegroundColor DarkGray
}

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " BUILD SUCCESSFUL!" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " Executable File : $exePath" -ForegroundColor White
Write-Host " Size            : $exeSizeMB MB" -ForegroundColor White
Write-Host " Ready to copy to another PC: YES" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Cyan
