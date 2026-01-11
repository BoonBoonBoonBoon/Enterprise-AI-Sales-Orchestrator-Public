# Restart core consumers using hierarchical stream naming.
# Starts new PowerShell windows; does NOT kill existing python processes.

$tenant = "agentic-dev"
$projectRoot = $PWD
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (!(Test-Path $venvPython)) {
    Write-Host "❌ Venv python not found at $venvPython" -ForegroundColor Red
    Write-Host "Create venv first or adjust path." -ForegroundColor Yellow
    exit 1
}

Write-Host "`nStarting consumers with TENANT_ID=$tenant..." -ForegroundColor Green

# Start Manager Consumer
Write-Host "`n[1/3] Starting Manager Consumer..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$projectRoot'; `$env:TENANT_ID='$tenant'; `$env:PYTHONIOENCODING='utf-8'; & '$venvPython' -m tiers.tier_1.manager.consumer"

Start-Sleep -Seconds 3

# Start Leads Orchestrator
Write-Host "[2/4] Starting Leads Orchestrator..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$projectRoot'; `$env:TENANT_ID='$tenant'; `$env:PYTHONIOENCODING='utf-8'; & '$venvPython' -m tiers.tier_2.leads_orchestrator.consumer"

Start-Sleep -Seconds 3

# Start Outbound Orchestrator
Write-Host "[3/4] Starting Outbound Orchestrator..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$projectRoot'; `$env:TENANT_ID='$tenant'; `$env:PYTHONIOENCODING='utf-8'; & '$venvPython' -m tiers.tier_2.outreach_orchestrator.consumer"

Start-Sleep -Seconds 3

# Start RAG Agent
Write-Host "[4/4] Starting RAG Agent..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$projectRoot'; `$env:TENANT_ID='$tenant'; `$env:PYTHONIOENCODING='utf-8'; & '$venvPython' -m tiers.tier_3.rag_agent.consumer"

Write-Host "`nAll consumers started! Check the new terminal windows." -ForegroundColor Green
Write-Host "New streams will use hierarchical naming: {tenant}:orchestrators:{name}:tasks" -ForegroundColor Yellow
