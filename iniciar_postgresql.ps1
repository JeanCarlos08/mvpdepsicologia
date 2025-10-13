# Script para iniciar o PostgreSQL como Administrador
# Clique com botão direito e escolha "Executar com PowerShell"

Write-Host "=" -repeat 70 -ForegroundColor Cyan
Write-Host "Iniciando o serviço PostgreSQL..." -ForegroundColor Yellow
Write-Host "=" -repeat 70 -ForegroundColor Cyan
Write-Host ""

try {
    Start-Service -Name "postgresql-x64-18" -ErrorAction Stop
    Write-Host "✅ Serviço PostgreSQL iniciado com sucesso!" -ForegroundColor Green
    Write-Host ""
    
    # Verificar status
    $service = Get-Service -Name "postgresql-x64-18"
    Write-Host "Status atual: $($service.Status)" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host "Agora você pode:" -ForegroundColor Yellow
    Write-Host "  1. Executar: python test_connection.py" -ForegroundColor White
    Write-Host "  2. Executar: python start.py" -ForegroundColor White
    Write-Host ""
} catch {
    Write-Host "❌ Erro ao iniciar o serviço:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "⚠️  Este script precisa ser executado como Administrador!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Como executar como Administrador:" -ForegroundColor Cyan
    Write-Host "  1. Clique com botão direito no arquivo" -ForegroundColor White
    Write-Host "  2. Escolha 'Executar com PowerShell'" -ForegroundColor White
    Write-Host "  3. Ou abra PowerShell como Admin e execute:" -ForegroundColor White
    Write-Host "     .\iniciar_postgresql.ps1" -ForegroundColor White
}

Write-Host ""
Write-Host "=" -repeat 70 -ForegroundColor Cyan
Write-Host "Pressione qualquer tecla para fechar..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
