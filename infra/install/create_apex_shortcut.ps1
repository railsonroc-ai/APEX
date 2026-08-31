$ErrorActionPreference = 'Stop'

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$targetBat = Join-Path $rootDir 'start_apex.bat'

if (-not (Test-Path $targetBat)) {
    throw "Arquivo não encontrado: $targetBat"
}

$desktopPath = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktopPath 'APEX.lnk'

$iconCandidates = @(
    (Join-Path $rootDir 'static\apex_icon.ico'),
    (Join-Path $rootDir 'static\apex_logo.ico'),
    (Join-Path $rootDir 'static\apex_logo.svg'),
    (Join-Path $rootDir 'static\apex_logo_light.svg')
)

$iconPath = $null
foreach ($candidate in $iconCandidates) {
    if (Test-Path $candidate) {
        $iconPath = $candidate
        break
    }
}

$wshShell = New-Object -ComObject WScript.Shell
$shortcut = $wshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetBat
$shortcut.WorkingDirectory = $rootDir
$shortcut.Description = 'Iniciar APEX (backend + agente local)'
$shortcut.WindowStyle = 1

if ($iconPath) {
    if ($iconPath.ToLower().EndsWith('.ico')) {
        $shortcut.IconLocation = "$iconPath,0"
    }
}

$shortcut.Save()

Write-Host "Atalho criado: $shortcutPath"
if ($iconPath -and $iconPath.ToLower().EndsWith('.ico')) {
    Write-Host "Ícone aplicado: $iconPath"
} else {
    Write-Host 'Ícone customizado não encontrado em .ico; atalho criado com ícone padrão.'
}
