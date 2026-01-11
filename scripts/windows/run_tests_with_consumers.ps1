# Start consumers in background
Write-Host "Starting all consumers in background..." -ForegroundColor Cyan
$consumerProcess = Start-Process python -ArgumentList "start_all_consumers.py" -PassThru -NoNewWindow
Start-Sleep -Seconds 3

Write-Host "Consumers started (PID: $($consumerProcess.Id))" -ForegroundColor Green
Write-Host ""
Write-Host "Running Manager→Orchestrator test..." -ForegroundColor Cyan
Write-Host ""

# Run test with auto-answer
$testInput = "`n"  # Just press Enter
$testProcess = Start-Process python -ArgumentList "tests/integration/test_manager_orchestrator_flow.py" -PassThru -NoNewWindow -RedirectStandardInput

Start-Sleep -Seconds 2
$testProcess | Send-Keys "`n"

# Wait for test to complete
$testProcess.WaitForExit(60000)

Write-Host ""
Write-Host "Test completed. Stopping consumers..." -ForegroundColor Cyan
$consumerProcess.Kill()

Write-Host "All done!" -ForegroundColor Green
