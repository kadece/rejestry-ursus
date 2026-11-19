# Rejestruje daemona rejestry-ursus na Windows:
#   - dwa zadania miesieczne w Harmonogramie (5. i 20. o 06:00) przez schtasks,
#   - autostart przy logowaniu przez folder Startup (skrypt .bat).
# Daemon (ursus_daemon.py) pilnuje terminow samodzielnie (daemon-state.json),
# a plik .ursus-daemon.lock zapobiega wielu instancjom.
# Uruchomienie:  powershell -NoProfile -ExecutionPolicy Bypass -File register-daemon-task.ps1
$ErrorActionPreference = 'Stop'

$pythonw = 'C:\Users\Krzysztof\AppData\Local\Programs\Python\Python312\pythonw.exe'
$script  = 'C:\rejestry-ursus\ursus_daemon.py'
$tr      = "$pythonw $script"

# 1) zadania miesieczne: 5. i 20. o 06:00 (schtasks /D nie przyjmuje listy dni -> dwa zadania)
foreach ($day in 5, 20) {
    $name = "Rejestry-Ursus-Daemon-dzien$day"
    schtasks /Create /TN $name /SC MONTHLY /D $day /ST 06:00 /TR $tr /F | Out-Null
    Write-Host "OK: $name (miesiecznie, dzien $day, 06:00)" -ForegroundColor Green
}

# 2) autostart przy logowaniu (folder Startup biezacego uzytkownika)
$startup = [Environment]::GetFolderPath('Startup')
$bat = Join-Path $startup 'rejestry-ursus-daemon.bat'
$batContent = "@echo off`r`n`"$pythonw`" `"$script`"`r`n"
[System.IO.File]::WriteAllText($bat, $batContent, [System.Text.Encoding]::ASCII)
Write-Host "OK: autostart $bat" -ForegroundColor Green

Get-ScheduledTask | Where-Object { $_.TaskName -like 'Rejestry-Ursus-Daemon*' } | Select-Object TaskName, State
