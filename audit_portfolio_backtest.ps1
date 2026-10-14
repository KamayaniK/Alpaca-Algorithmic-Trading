$ErrorActionPreference = "Stop"
$dir = ".\reports\backtest_portfolios_20261014"

Write-Output "`n=== CASH RESERVE BREACH DETAIL ==="
Import-Csv "$dir\daily_equity.csv" |
    Where-Object { [double]$_.cash -lt 5000 } |
    Select-Object member, date, cash, market_value, equity, technology_exposure, ai_hardware_exposure, position_count |
    Format-Table -AutoSize

Write-Output "`n=== TECHNOLOGY CAP BREACH RANGE ==="
Import-Csv "$dir\daily_equity.csv" |
    Where-Object { [double]$_.technology_exposure -gt 33250.01 } |
    Group-Object member |
    ForEach-Object {
        $r = $_.Group
        $values = @($r | ForEach-Object { [double]$_.technology_exposure })
        [pscustomobject]@{
            Member = $_.Name
            BreachDays = $r.Count
            FirstBreach = ($r | Select-Object -First 1).date
            LastBreach = ($r | Select-Object -Last 1).date
            MaxTechnologyExposure = [math]::Round(($values | Measure-Object -Maximum).Maximum, 2)
        }
    } | Format-Table -AutoSize

Write-Output "`n=== TEST DISCOVERY FILES (NO TESTS EXECUTED HERE) ==="
Get-ChildItem -Path . -Recurse -File -Include test*.py,*_test.py |
    Where-Object { $_.FullName -notmatch '\\.venv\\|\\__pycache__\\|\\site-packages\\' } |
    Select-Object FullName

Write-Output "`n=== TEST FILES WITH NETWORK OR PROMPT MARKERS ==="
Get-ChildItem -Path . -Recurse -File -Include test*.py,*_test.py |
    Where-Object { $_.FullName -notmatch '\\.venv\\|\\__pycache__\\|\\site-packages\\' } |
    Select-String -Pattern 'input\(|TradingClient|StockHistoricalDataClient|requests\.|httpx\.|urlopen|get_account\(|get_stock_bars\(' |
    Select-Object -First 80 Path, LineNumber, Line
