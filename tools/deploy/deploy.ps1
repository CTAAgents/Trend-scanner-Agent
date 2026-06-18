# QuantNova 部署脚本 (Windows PowerShell)
#
# 使用方式：
#   powershell -ExecutionPolicy Bypass -File tools/deploy.ps1 [选项]
#
# 选项：
#   -Check     只检查环境，不执行部署
#   -Install   安装依赖
#   -Init      初始化配置
#   -Start     启动服务
#   -All       执行全部步骤（默认）

param(
    [switch]$Check,
    [switch]$Install,
    [switch]$Init,
    [switch]$Start,
    [switch]$Stop,
    [switch]$Status,
    [switch]$All
)

# 设置错误处理
$ErrorActionPreference = "Stop"

# 项目根目录
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

# 颜色函数
function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Blue }
function Write-Success { Write-Host "[SUCCESS] $args" -ForegroundColor Green }
function Write-Warning { Write-Host "[WARNING] $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "[ERROR] $args" -ForegroundColor Red }

# 检查环境
function Check-Environment {
    Write-Info "检查环境..."
    
    # 检查 Python
    try {
        $pythonVersion = python --version 2>&1
        Write-Success "Python: $pythonVersion"
    } catch {
        Write-Error "Python 未安装"
        return $false
    }
    
    # 检查 pip
    try {
        $pipVersion = pip --version 2>&1
        Write-Success "pip: $pipVersion"
    } catch {
        Write-Error "pip 未安装"
        return $false
    }
    
    # 检查 git
    try {
        $gitVersion = git --version 2>&1
        Write-Success "git: $gitVersion"
    } catch {
        Write-Warning "git 未安装（可选）"
    }
    
    # 检查必要的目录
    foreach ($dir in @("config", "data", "logs", "scripts", "tools")) {
        if (Test-Path $dir) {
            Write-Success "目录存在: $dir"
        } else {
            Write-Warning "目录不存在: $dir（将创建）"
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
    
    # 检查环境变量
    if ($env:TQ_USER -and $env:TQ_PASSWORD) {
        Write-Success "TqSdk 环境变量已设置"
    } else {
        Write-Warning "TqSdk 环境变量未设置（TQ_USER, TQ_PASSWORD）"
    }
    
    Write-Success "环境检查完成"
    return $true
}

# 安装依赖
function Install-Dependencies {
    Write-Info "安装依赖..."
    
    # 检查 requirements.txt
    if (Test-Path "requirements.txt") {
        Write-Info "从 requirements.txt 安装依赖..."
        pip install -r requirements.txt --quiet
        Write-Success "依赖安装完成"
    } else {
        Write-Warning "requirements.txt 不存在，跳过依赖安装"
    }
    
    # 安装关键依赖
    Write-Info "安装关键依赖..."
    pip install pandas numpy duckdb --quiet
    Write-Success "关键依赖安装完成"
}

# 初始化配置
function Init-Config {
    Write-Info "初始化配置..."
    
    # 检查配置文件
    if (Test-Path "config/config.json") {
        Write-Success "配置文件已存在: config/config.json"
    } else {
        Write-Warning "配置文件不存在，创建默认配置..."
        Create-DefaultConfig
    }
    
    # 检查持仓文件
    if (Test-Path "config/positions.json") {
        Write-Success "持仓文件已存在: config/positions.json"
    } else {
        Write-Warning "持仓文件不存在，创建空持仓..."
        '{"updated_at": null, "positions": []}' | Out-File -FilePath "config/positions.json" -Encoding UTF8
    }
    
    # 初始化数据库
    Write-Info "初始化数据库..."
    python -c @"
from scripts.trend_scanner.memory import UnifiedMemoryManager
config = {
    'sqlite_path': 'data/memory.db',
    'duckdb_path': 'data/analytics.duckdb',
    'vector_dim': 15,
    'llm': {'provider': 'workbuddy'}
}
memory = UnifiedMemoryManager(config)
memory.close()
print('数据库初始化完成')
"@
    
    Write-Success "配置初始化完成"
}

# 创建默认配置
function Create-DefaultConfig {
    $config = @'
{
  "scanner": {
    "symbols": [
      "SHFE.rb", "SHFE.hc", "DCE.jm", "DCE.i", "DCE.j",
      "SHFE.cu", "SHFE.al", "SHFE.ni",
      "INE.sc", "SHFE.fu", "SHFE.bu",
      "CZCE.CF", "CZCE.SR", "CZCE.OI",
      "DCE.m", "DCE.y", "DCE.p",
      "SHFE.au", "SHFE.ag"
    ],
    "schedule": ["09:15", "09:30", "10:30", "13:30", "14:30", "15:15"],
    "signal_filter": {
      "er_min": 0.6,
      "tsi_min": 20,
      "tsi_max": -20,
      "trend_strength_min": 0.5,
      "r2_min": 0.4
    }
  },
  "monitor": {
    "interval_minutes": 30,
    "alert_thresholds": {
      "LOW": {"trend_strength_drop": 0.15},
      "MEDIUM": {"trend_strength_drop": 0.25, "tsi_divergence": true},
      "HIGH": {"trend_strength_drop": 0.35, "er_below": 0.3}
    }
  },
  "reasoner": {
    "llm_type": "workbuddy",
    "debate_trigger_confidence": 0.7,
    "max_tokens_per_day": 500000,
    "experience_top_k": 5,
    "experience_similarity_threshold": 0.6
  },
  "debater": {
    "debate_trigger_confidence": 0.7,
    "debate_trigger_amount": 100000,
    "max_debate_rounds": 1
  },
  "evolver": {
    "auto_trigger": {
      "consecutive_losses": 3,
      "cumulative_loss_pct": 10,
      "trade_count_interval": 20
    },
    "overfitting_threshold": 0.7,
    "min_samples_for_rule": 5,
    "rule_promotion_threshold": 0.6
  },
  "memory_system": {
    "sqlite_path": "data/memory.db",
    "duckdb_path": "data/analytics.duckdb",
    "vector_dim": 15,
    "max_experiences": 10000,
    "time_decay_half_life_days": 90
  },
  "llm": {
    "provider": "workbuddy",
    "model": "default",
    "temperature": 0.3,
    "max_tokens": 2000,
    "daily_budget": 850000
  }
}
'@
    $config | Out-File -FilePath "config/config.json" -Encoding UTF8
    Write-Success "默认配置已创建"
}

# 启动服务
function Start-Service {
    Write-Info "启动服务..."
    
    # 检查是否已经在运行
    if (Test-Path "data/orchestrator.pid") {
        $pid = Get-Content "data/orchestrator.pid"
        $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($process) {
            Write-Warning "服务已在运行 (PID: $pid)"
            return
        }
    }
    
    # 启动 Orchestrator
    Write-Info "启动 Orchestrator..."
    $process = Start-Process -FilePath "python" -ArgumentList "tools/orchestrator.py", "--daemon" -NoNewWindow -PassThru -RedirectStandardOutput "logs/orchestrator.log" -RedirectStandardError "logs/orchestrator_error.log"
    $process.Id | Out-File -FilePath "data/orchestrator.pid"
    Write-Success "Orchestrator 已启动 (PID: $($process.Id))"
    
    # 启动自动 Git 推送
    Write-Info "启动自动 Git 推送..."
    $process = Start-Process -FilePath "python" -ArgumentList "tools/start_auto_git_push.py" -NoNewWindow -PassThru -RedirectStandardOutput "logs/auto_git_push.log" -RedirectStandardError "logs/auto_git_push_error.log"
    $process.Id | Out-File -FilePath "data/auto_git_push.pid"
    Write-Success "自动 Git 推送已启动 (PID: $($process.Id))"
    
    Write-Success "服务启动完成"
}

# 停止服务
function Stop-ServiceFunc {
    Write-Info "停止服务..."
    
    # 停止 Orchestrator
    if (Test-Path "data/orchestrator.pid") {
        $pid = Get-Content "data/orchestrator.pid"
        $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($process) {
            Stop-Process -Id $pid
            Write-Success "Orchestrator 已停止 (PID: $pid)"
        }
        Remove-Item "data/orchestrator.pid" -ErrorAction SilentlyContinue
    }
    
    # 停止自动 Git 推送
    if (Test-Path "data/auto_git_push.pid") {
        $pid = Get-Content "data/auto_git_push.pid"
        $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($process) {
            Stop-Process -Id $pid
            Write-Success "自动 Git 推送已停止 (PID: $pid)"
        }
        Remove-Item "data/auto_git_push.pid" -ErrorAction SilentlyContinue
    }
    
    Write-Success "服务停止完成"
}

# 显示状态
function Show-Status {
    Write-Info "系统状态..."
    
    Write-Host ""
    Write-Host "=== 进程状态 ===" -ForegroundColor Cyan
    
    # Orchestrator
    if (Test-Path "data/orchestrator.pid") {
        $pid = Get-Content "data/orchestrator.pid"
        $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($process) {
            Write-Success "Orchestrator: 运行中 (PID: $pid)"
        } else {
            Write-Warning "Orchestrator: 已停止"
        }
    } else {
        Write-Warning "Orchestrator: 未启动"
    }
    
    # 自动 Git 推送
    if (Test-Path "data/auto_git_push.pid") {
        $pid = Get-Content "data/auto_git_push.pid"
        $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($process) {
            Write-Success "自动 Git 推送: 运行中 (PID: $pid)"
        } else {
            Write-Warning "自动 Git 推送: 已停止"
        }
    } else {
        Write-Warning "自动 Git 推送: 未启动"
    }
    
    Write-Host ""
    Write-Host "=== 数据库状态 ===" -ForegroundColor Cyan
    
    # SQLite
    if (Test-Path "data/memory.db") {
        $size = (Get-Item "data/memory.db").Length / 1KB
        Write-Success "SQLite: $([math]::Round($size, 2)) KB"
    } else {
        Write-Warning "SQLite: 不存在"
    }
    
    # DuckDB
    if (Test-Path "data/analytics.duckdb") {
        $size = (Get-Item "data/analytics.duckdb").Length / 1KB
        Write-Success "DuckDB: $([math]::Round($size, 2)) KB"
    } else {
        Write-Warning "DuckDB: 不存在"
    }
    
    Write-Host ""
    Write-Host "=== 配置状态 ===" -ForegroundColor Cyan
    
    if (Test-Path "config/config.json") {
        Write-Success "配置文件: 存在"
    } else {
        Write-Warning "配置文件: 不存在"
    }
    
    if (Test-Path "config/positions.json") {
        $positions = Get-Content "config/positions.json" | ConvertFrom-Json
        Write-Success "持仓数量: $($positions.positions.Count)"
    } else {
        Write-Warning "持仓文件: 不存在"
    }
}

# 主函数
function Main {
    Write-Host ""
    Write-Host "=== QuantNova 部署脚本 ===" -ForegroundColor Cyan
    Write-Host ""
    
    # 根据参数执行操作
    if ($Check) {
        Check-Environment
    } elseif ($Install) {
        Check-Environment
        Install-Dependencies
    } elseif ($Init) {
        Check-Environment
        Init-Config
    } elseif ($Start) {
        Start-Service
    } elseif ($Stop) {
        Stop-ServiceFunc
    } elseif ($Status) {
        Show-Status
    } else {
        # 默认执行全部步骤
        Check-Environment
        Install-Dependencies
        Init-Config
        Start-Service
        Show-Status
    }
    
    Write-Host ""
    Write-Success "操作完成"
}

# 执行主函数
Main
