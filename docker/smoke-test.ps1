param(
    [string]$BaseUrl = "http://localhost:8080",
    [int]$Attempts = 30
)

$ErrorActionPreference = "Stop"

for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
    try {
        $frontend = Invoke-WebRequest -Uri $BaseUrl -TimeoutSec 5
        $health = Invoke-RestMethod `
            -Uri "$BaseUrl/api/v1/health/ready" `
            -TimeoutSec 10

        if ($frontend.StatusCode -eq 200 -and $health.status -eq "ready") {
            Write-Output "Docker deployment smoke test: PASSED"
            Write-Output "Frontend: $($frontend.StatusCode)"
            Write-Output "Backend readiness: $($health.status)"
            exit 0
        }
    }
    catch {
        if ($attempt -eq $Attempts) {
            throw
        }
    }

    Start-Sleep -Seconds 2
}

throw "Docker deployment did not become ready in time."
