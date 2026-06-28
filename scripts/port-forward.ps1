# Opens port-forwards to every UI + the gateway in background jobs.
# Stop them all with: Get-Job | Stop-Job; Get-Job | Remove-Job
$ErrorActionPreference = "Stop"

$forwards = @(
    @{ name = "gateway";    svc = "svc/gateway-service"; ports = "8080:8080" },
    @{ name = "grafana";    svc = "svc/grafana";         ports = "3000:3000" },
    @{ name = "prometheus"; svc = "svc/prometheus";      ports = "9090:9090" },
    @{ name = "jaeger";     svc = "svc/jaeger";          ports = "16686:16686" },
    @{ name = "tempo";      svc = "svc/tempo";           ports = "3200:3200" },
    @{ name = "loki";       svc = "svc/loki";            ports = "3100:3100" }
)

# Clean up any prior jobs from this script
Get-Job -Name "pf-*" -ErrorAction SilentlyContinue | Stop-Job -PassThru | Remove-Job

foreach ($f in $forwards) {
    Start-Job -Name "pf-$($f.name)" -ScriptBlock {
        param($svc, $ports)
        kubectl -n shop port-forward $svc $ports
    } -ArgumentList $f.svc, $f.ports | Out-Null
    Write-Host ("{0,-12} -> http://localhost:{1}" -f $f.name, $f.ports.Split(":")[0]) -ForegroundColor Green
}

Write-Host ""
Write-Host "Port-forwards running as background jobs. UIs:" -ForegroundColor Cyan
Write-Host "  Grafana     http://localhost:3000   (anonymous admin; explore Tempo/Loki/Prometheus)"
Write-Host "  Prometheus  http://localhost:9090"
Write-Host "  Jaeger      http://localhost:16686"
Write-Host "  Gateway API http://localhost:8080/api/products"
Write-Host ""
Write-Host "Stop everything with: Get-Job -Name pf-* | Stop-Job; Get-Job -Name pf-* | Remove-Job" -ForegroundColor DarkGray
