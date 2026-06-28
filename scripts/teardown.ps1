# Tears everything down: stops port-forward jobs and deletes the KIND cluster.
# Uses 'Continue' so native-tool stderr isn't treated as fatal (PowerShell 5.1 quirk).
param([switch]$KeepCluster)
$ErrorActionPreference = "Continue"

Get-Job -Name "pf-*" -ErrorAction SilentlyContinue | Stop-Job -PassThru | Remove-Job

if ($KeepCluster) {
    Write-Host "Deleting 'shop' namespace only (keeping cluster)..." -ForegroundColor Cyan
    kubectl delete namespace shop --ignore-not-found
} else {
    Write-Host "Deleting KIND cluster 'obs-lab'..." -ForegroundColor Cyan
    kind delete cluster --name obs-lab
}
Write-Host "Done." -ForegroundColor Green
