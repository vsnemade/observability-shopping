# Generates checkout + browse traffic against the gateway so you have metrics, traces and logs to look at.
# Requires scripts/port-forward.ps1 to be running (gateway on localhost:8080).
param(
    [int]$Iterations = 200,
    [int]$DelayMs = 250,
    [string]$BaseUrl = "http://localhost:8080"
)

$products = @("p-1", "p-2", "p-3", "p-4")
$ok = 0; $failed = 0

for ($i = 1; $i -le $Iterations; $i++) {
    $product = $products | Get-Random
    $qty = Get-Random -Minimum 1 -Maximum 4
    $corr = [guid]::NewGuid().ToString()
    $body = @{ productId = $product; quantity = $qty } | ConvertTo-Json

    try {
        # Occasionally browse the catalog too, to vary the endpoints.
        if ($i % 5 -eq 0) {
            Invoke-RestMethod -Uri "$BaseUrl/api/products" -Method Get -Headers @{ "X-Correlation-ID" = $corr } | Out-Null
        }
        $resp = Invoke-RestMethod -Uri "$BaseUrl/api/checkout" -Method Post -Body $body `
            -ContentType "application/json" -Headers @{ "X-Correlation-ID" = $corr }
        $ok++
        Write-Host ("[{0,3}] OK    corr={1} order={2} amount={3}" -f $i, $corr.Substring(0,8), $resp.orderId, $resp.amount) -ForegroundColor Green
    }
    catch {
        $failed++
        $status = $_.Exception.Response.StatusCode.value__
        Write-Host ("[{0,3}] FAIL  corr={1} status={2}" -f $i, $corr.Substring(0,8), $status) -ForegroundColor Yellow
    }
    Start-Sleep -Milliseconds $DelayMs
}

Write-Host ""
Write-Host "Done. ok=$ok failed=$failed (declines/out-of-stock are expected and intentional)." -ForegroundColor Cyan
