#!/bin/bash
# QuantNova 部署脚本
# 
# 使用方式：
#   bash tools/deploy.sh [选项]
#
# 选项：
#   --check     只检查环境，不执行部署
#   --install   安装依赖
#   --init      初始化配置
#   --start     启动服务
#   --all       执行全部步骤（默认）
#   --help      显示帮助

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助
show_help() {
    echo "QuantNova 部署脚本"
    echo ""
    echo "使用方式："
    echo "  bash tools/deploy.sh [选项]"
    echo ""
    echo "选项："
    echo "  --check     只检查环境，不执行部署"
    echo "  --install   安装依赖"
    echo "  --init      初始化配置"
    echo "  --start     启动服务"
    echo "  --all       执行全部步骤（默认）"
    echo "  --help      显示帮助"
}

# 检查环境
check_environment() {
    log_info "检查环境..."
    
    # 检查 Python
    if command -v python &> /dev/null; then
        PYTHON_VERSION=$(python --version 2>&1)
        log_success "Python: $PYTHON_VERSION"
    else
        log_error "Python 未安装"
        return 1
    fi
    
    # 检查 pip
    if command -v pip &> /dev/null; then
        PIP_VERSION=$(pip --version 2>&1)
        log_success "pip: $PIP_VERSION"
    else
        log_error "pip 未安装"
        return 1
    fi
    
    # 检查 git
    if command -v git &> /dev/null; then
        GIT_VERSION=$(git --version 2>&1)
        log_success "git: $GIT_VERSION"
    else
        log_warning "git 未安装（可选）"
    fi
    
    # 检查必要的目录
    for dir in "config" "data" "logs" "scripts" "tools"; do
        if [ -d "$dir" ]; then
            log_success "目录存在: $dir"
        else
            log_warning "目录不存在: $dir（将创建）"
            mkdir -p "$dir"
        fi
    done
    
    # 检查环境变量
    if [ -n "$TQ_USER" ] && [ -n "$TQ_PASSWORD" ]; then
        log_success "TqSdk 环境变量已设置"
    else
        log_warning "TqSdk 环境变量未设置（TQ_USER, TQ_PASSWORD）"
    fi
    
    log_success "环境检查完成"
}

# 安装依赖
install_dependencies() {
    log_info "安装依赖..."
    
    # 检查 requirements.txt
    if [ -f "requirements.txt" ]; then
        log_info "从 requirements.txt 安装依赖..."
        pip install -r requirements.txt --quiet
        log_success "依赖安装完成"
    else
        log_warning "requirements.txt 不存在，跳过依赖安装"
    fi
    
    # 安装关键依赖
    log_info "安装关键依赖..."
    pip install pandas numpy duckdb --quiet
    log_success "关键依赖安装完成"
}

# 初始化配置
init_config() {
    log_info "初始化配置..."
    
    # 检查配置文件
    if [ -f "config/config.json" ]; then
        log_success "配置文件已存在: config/config.json"
    else
        log_warning "配置文件不存在，创建默认配置..."
        create_default_config
    fi
    
    # 检查持仓文件
    if [ -f "config/positions.json" ]; then
        log_success "持仓文件已存在: config/positions.json"
    else
        log_warning "持仓文件不存在，创建空持仓..."
        echo '{"updated_at": null, "positions": []}' > config/positions.json
    fi
    
    # 初始化数据库
    log_info "初始化数据库..."
    python -c "
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
"
    
    log_success "配置初始化完成"
}

# 创建默认配置
create_default_config() {
    cat > config/config.json << 'EOF'
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
EOF
    log_success "默认配置已创建"
}

# 启动服务
start_service() {
    log_info "启动服务..."
    
    # 检查是否已经在运行
    if [ -f "data/orchestrator.pid" ]; then
        PID=$(cat data/orchestrator.pid)
        if ps -p $PID > /dev/null 2>&1; then
            log_warning "服务已在运行 (PID: $PID)"
            return 0
        fi
    fi
    
    # 启动 Orchestrator
    log_info "启动 Orchestrator..."
    nohup python tools/orchestrator.py --daemon > logs/orchestrator.log 2>&1 &
    echo $! > data/orchestrator.pid
    log_success "Orchestrator 已启动 (PID: $!)"
    
    # 启动自动 Git 推送
    log_info "启动自动 Git 推送..."
    nohup python tools/start_auto_git_push.py > logs/auto_git_push.log 2>&1 &
    echo $! > data/auto_git_push.pid
    log_success "自动 Git 推送已启动 (PID: $!)"
    
    log_success "服务启动完成"
}

# 停止服务
stop_service() {
    log_info "停止服务..."
    
    # 停止 Orchestrator
    if [ -f "data/orchestrator.pid" ]; then
        PID=$(cat data/orchestrator.pid)
        if ps -p $PID > /dev/null 2>&1; then
            kill $PID
            log_success "Orchestrator 已停止 (PID: $PID)"
        fi
        rm -f data/orchestrator.pid
    fi
    
    # 停止自动 Git 推送
    if [ -f "data/auto_git_push.pid" ]; then
        PID=$(cat data/auto_git_push.pid)
        if ps -p $PID > /dev/null 2>&1; then
            kill $PID
            log_success "自动 Git 推送已停止 (PID: $PID)"
        fi
        rm -f data/auto_git_push.pid
    fi
    
    log_success "服务停止完成"
}

# 显示状态
show_status() {
    log_info "系统状态..."
    
    echo ""
    echo "=== 进程状态 ==="
    
    # Orchestrator
    if [ -f "data/orchestrator.pid" ]; then
        PID=$(cat data/orchestrator.pid)
        if ps -p $PID > /dev/null 2>&1; then
            log_success "Orchestrator: 运行中 (PID: $PID)"
        else
            log_warning "Orchestrator: 已停止"
        fi
    else
        log_warning "Orchestrator: 未启动"
    fi
    
    # 自动 Git 推送
    if [ -f "data/auto_git_push.pid" ]; then
        PID=$(cat data/auto_git_push.pid)
        if ps -p $PID > /dev/null 2>&1; then
            log_success "自动 Git 推送: 运行中 (PID: $PID)"
        else
            log_warning "自动 Git 推送: 已停止"
        fi
    else
        log_warning "自动 Git 推送: 未启动"
    fi
    
    echo ""
    echo "=== 数据库状态 ==="
    
    # SQLite
    if [ -f "data/memory.db" ]; then
        SIZE=$(du -h data/memory.db | cut -f1)
        log_success "SQLite: $SIZE"
    else
        log_warning "SQLite: 不存在"
    fi
    
    # DuckDB
    if [ -f "data/analytics.duckdb" ]; then
        SIZE=$(du -h data/analytics.duckdb | cut -f1)
        log_success "DuckDB: $SIZE"
    else
        log_warning "DuckDB: 不存在"
    fi
    
    echo ""
    echo "=== 配置状态 ==="
    
    if [ -f "config/config.json" ]; then
        log_success "配置文件: 存在"
    else
        log_warning "配置文件: 不存在"
    fi
    
    if [ -f "config/positions.json" ]; then
        POSITIONS=$(python -c "import json; data=json.load(open('config/positions.json')); print(len(data.get('positions', [])))")
        log_success "持仓数量: $POSITIONS"
    else
        log_warning "持仓文件: 不存在"
    fi
}

# 主函数
main() {
    echo ""
    echo "=== QuantNova 部署脚本 ==="
    echo ""
    
    # 解析参数
    ACTION="all"
    
    for arg in "$@"; do
        case $arg in
            --check)
                ACTION="check"
                ;;
            --install)
                ACTION="install"
                ;;
            --init)
                ACTION="init"
                ;;
            --start)
                ACTION="start"
                ;;
            --stop)
                ACTION="stop"
                ;;
            --status)
                ACTION="status"
                ;;
            --all)
                ACTION="all"
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知参数: $arg"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 执行操作
    case $ACTION in
        check)
            check_environment
            ;;
        install)
            check_environment
            install_dependencies
            ;;
        init)
            check_environment
            init_config
            ;;
        start)
            start_service
            ;;
        stop)
            stop_service
            ;;
        status)
            show_status
            ;;
        all)
            check_environment
            install_dependencies
            init_config
            start_service
            show_status
            ;;
    esac
    
    echo ""
    log_success "操作完成"
}

# 执行主函数
main "$@"
