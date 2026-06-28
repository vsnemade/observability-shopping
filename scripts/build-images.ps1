# Builds all four service images from the single root Dockerfile.
# Run from anywhere; paths are resolved relative to the repo root.
#
# Note: 'docker build' streams its progress to stderr. Under $ErrorActionPreference='Stop',
# Windows PowerShell 5.1 would treat that as a fatal error, so we use 'Continue' and check
# the exit code explicitly.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$env:DOCKER_BUILDKIT = "1"

$services = @("gateway-service", "order-service", "product-service", "payment-service")

foreach ($svc in $services) {
    Write-Host "==> Building ${svc}:local" -ForegroundColor Cyan
    docker build --build-arg SERVICE=$svc -t "${svc}:local" -f "$root/Dockerfile" $root
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Build failed for $svc (exit $LASTEXITCODE)" -ForegroundColor Red
        exit 1
    }
}

Write-Host "All images built." -ForegroundColor Green
docker images | Select-String "gateway-service|order-service|product-service|payment-service"
