# 智法通 V2 —— Windows 一键启动（Docker 生产模式）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "=== 检查 Docker ===" -ForegroundColor Cyan
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "请先启动 Docker Desktop" }

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" -Force }

Write-Host "=== 构建并启动（mysql/redis/neo4j/backend/frontend）===" -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw "docker compose 启动失败" }

Write-Host "=== 等待后端就绪 ===" -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 40; $i++) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 "http://localhost:28000/health"
    if ($r.StatusCode -eq 200) { $ok = $true; break }
  } catch { Start-Sleep -Seconds 3 }
}
if (-not $ok) { Write-Warning "后端健康检查超时，请查看 docker compose logs backend" }

Write-Host "============================================" -ForegroundColor Green
Write-Host "  智法通 V2 已启动："
Write-Host "  前端  http://localhost:8188"
Write-Host "  后端  http://localhost:28000/docs   (health: /health)"
Write-Host "  账号  admin/admin123  lawyer/lawyer123  user/user123456"
Write-Host "============================================" -ForegroundColor Green
