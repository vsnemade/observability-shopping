# Creates the KIND cluster (if needed), loads the service images into it, and applies all manifests.
#
# Note: native tools (kind/kubectl) write progress to stderr. Under $ErrorActionPreference='Stop',
# Windows PowerShell 5.1 wrongly treats that stderr as a fatal error, so we use 'Continue' and
# check exit codes explicitly instead.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$cluster = "obs-lab"
$services = @("gateway-service", "order-service", "product-service", "payment-service")

function Assert-LastExit($message) {
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: $message (exit $LASTEXITCODE)" -ForegroundColor Red
        exit 1
    }
}

# 1) Cluster
$existing = kind get clusters 2>$null
if ($LASTEXITCODE -ne 0) { $existing = @() }      # "No kind clusters found." -> treat as none
if ($existing -notcontains $cluster) {
    Write-Host "==> Creating KIND cluster '$cluster'" -ForegroundColor Cyan
    kind create cluster --config "$root/kind/kind-config.yaml"
    Assert-LastExit "Failed to create KIND cluster"
} else {
    Write-Host "==> KIND cluster '$cluster' already exists" -ForegroundColor DarkGray
}

# 2) Load images into the cluster's nodes (KIND can't pull :local from a registry)
foreach ($svc in $services) {
    Write-Host "==> Loading ${svc}:local into KIND" -ForegroundColor Cyan
    kind load docker-image "${svc}:local" --name $cluster
    Assert-LastExit "Failed to load image ${svc}:local (did you run build-images.ps1?)"
}

# 3) Apply manifests: namespace -> observability stack -> services
Write-Host "==> Applying manifests" -ForegroundColor Cyan
kubectl apply -f "$root/k8s/00-namespace.yaml";        Assert-LastExit "namespace apply failed"
kubectl apply -f "$root/k8s/observability/";           Assert-LastExit "observability apply failed"
kubectl apply -f "$root/k8s/services/";                Assert-LastExit "services apply failed"

# 4) Wait for everything to be ready
Write-Host "==> Waiting for pods to become ready (this can take a couple of minutes)..." -ForegroundColor Cyan
kubectl -n shop wait --for=condition=available deployment --all --timeout=420s

kubectl -n shop get pods
Write-Host "Deploy complete. Run scripts/port-forward.ps1 to open the UIs." -ForegroundColor Green
