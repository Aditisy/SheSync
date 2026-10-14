param([switch]$NoWorker)
$ErrorActionPreference='Stop'
$projectPath=$PSScriptRoot
$preferredPython=Join-Path $projectPath '.venv\Scripts\python.exe'
if(!(Test-Path -LiteralPath $preferredPython)){$preferredPython='C:\Users\scyya\OneDrive\Desktop\SheSync\venv\Scripts\python.exe'}
if(!(Test-Path -LiteralPath $preferredPython)){$preferredPython=(Get-Command python).Source}
$backendPath=Join-Path $projectPath 'backend_api.py'
Start-Process -FilePath $preferredPython -ArgumentList $backendPath -WorkingDirectory $projectPath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectPath 'backend.log') -RedirectStandardError (Join-Path $projectPath 'backend-error.log')
if(!$NoWorker){Start-Process -FilePath $preferredPython -ArgumentList (Join-Path $projectPath 'reminder_worker.py') -WorkingDirectory $projectPath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectPath 'worker.log') -RedirectStandardError (Join-Path $projectPath 'worker-error.log')}
Write-Output 'SheSync: http://localhost:5000 · backend and reminder worker started. Check logs if startup fails.'
