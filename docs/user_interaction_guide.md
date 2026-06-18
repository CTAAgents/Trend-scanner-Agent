# 用户交互指南

> 版本：v2.0 | 创建日期：2026-06-18 | 更新：2026-06-18
> 说明：系统独立运行时的用户交互方式

## 一、交互模式概览

系统支持三种交互模式，用户可根据需求选择：

| 模式 | 适用场景 | 特点 |
|------|----------|------|
| **CLI 模式** | 命令行操作、自动化脚本 | 轻量、高效、可脚本化 |
| **Web UI 模式** | 可视化操作、数据查看 | 直观、易用、实时 |
| **API 模式** | 系统集成、第三方调用 | 灵活、可编程、可扩展 |

**所有模式均支持自然语言交互**，用户可以用日常语言与系统交流。

---

## 二、自然语言交互

### 2.1 支持的自然语言指令

| 类型 | 示例 | 系统动作 |
|------|------|----------|
| **查询类** | "查看当前信号" | 执行扫描并显示结果 |
| | "显示持仓状态" | 显示当前持仓 |
| | "什么品种有信号" | 列出有信号的品种 |
| **操作类** | "扫描一下" | 执行市场扫描 |
| | "运行进化" | 执行因子进化 |
| | "同步数据" | 同步行情数据 |
| | "检查健康度" | 检查持仓健康度 |
| | "套利分析" | 执行套利分析 |
| **分析类** | "分析一下螺纹钢" | 深度分析螺纹钢 |
| | "为什么铜在涨" | 分析铜上涨原因 |
| | "预测一下原油走势" | 预测原油走势 |
| **状态类** | "系统状态" | 显示系统运行状态 |
| | "是否在运行" | 检查系统状态 |
| **帮助类** | "帮助" | 显示帮助信息 |
| | "怎么用" | 显示使用说明 |

### 2.2 自然语言交互示例

```bash
# CLI 自然语言交互
python scripts/core/nlp_chat.py

# 输入自然语言
> 查看当前信号
系统：扫描完成！发现 3 个信号。

> 扫描一下黑色系
系统：正在扫描黑色系品种...

> 系统状态
系统：系统状态正常，已运行 2 小时 30 分钟。

> 帮助
系统：可用命令：scan, evolve, sync, health_check, arbitrage, status
```

### 2.3 自然语言处理架构

```
用户输入 → 意图识别 → 命令解析 → 命令执行 → 响应生成
    ↓           ↓           ↓           ↓           ↓
自然语言    Intent     Command     执行结果    自然语言
```

---

## 三、CLI 模式

### 2.1 启动系统

```bash
# 启动独立运行模式
python scripts/core/main.py

# 查看系统状态
python scripts/core/main.py --status

# 停止系统
python scripts/core/main.py --stop
```

### 2.2 常用命令

```bash
# 查看系统状态
python tools/core/scan_opportunities.py --status

# 手动触发扫描
python tools/core/scan_opportunities.py --output text --save

# 手动触发因子进化
python tools/core/scan_opportunities.py --evolve --evolve-rounds 3

# 查看持仓健康度
python tools/core/scan_opportunities.py --position-health

# 查看套利机会
python tools/core/scan_opportunities.py --arbitrage --output text
```

### 2.3 CLI 优势

- **轻量级**：无需图形界面，资源占用低
- **可脚本化**：支持批处理和自动化
- **远程操作**：支持 SSH 远程执行
- **日志完整**：所有操作都有详细日志

---

## 三、Web UI 模式

### 3.1 启动 Web 服务

```bash
# 启动 Web UI 服务
python tools/web_server.py --port 8080

# 或使用内置命令
python scripts/core/main.py --web --port 8080
```

### 3.2 访问方式

- **本地访问**：http://localhost:8080
- **局域网访问**：http://<服务器IP>:8080
- **远程访问**：通过反向代理（Nginx/Apache）

### 3.3 Web UI 功能

| 功能 | 说明 |
|------|------|
| **仪表盘** | 显示系统状态、最新信号、持仓概览 |
| **市场扫描** | 实时扫描结果、信号详情 |
| **因子进化** | 进化进度、新因子展示 |
| **持仓管理** | 当前持仓、健康度评估 |
| **系统设置** | 配置修改、参数调整 |
| **日志查看** | 实时日志、历史记录 |

### 3.4 Web UI 优势

- **直观易用**：图形界面，操作简单
- **实时更新**：WebSocket 实时推送
- **数据可视化**：图表、仪表盘、K线图
- **移动端支持**：响应式设计，支持手机访问

---

## 四、API 模式

### 4.1 启动 API 服务

```bash
# 启动 API 服务
python tools/api_server.py --port 8081

# 或使用内置命令
python scripts/core/main.py --api --port 8081
```

### 4.2 API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 获取系统状态 |
| `/api/scan` | POST | 触发市场扫描 |
| `/api/evolve` | POST | 触发因子进化 |
| `/api/positions` | GET | 获取持仓信息 |
| `/api/signals` | GET | 获取信号列表 |
| `/api/config` | GET/PUT | 获取/修改配置 |

### 4.3 API 调用示例

```bash
# 获取系统状态
curl http://localhost:8081/api/status

# 触发市场扫描
curl -X POST http://localhost:8081/api/scan

# 获取持仓信息
curl http://localhost:8081/api/positions
```

### 4.4 API 优势

- **可编程**：支持任何编程语言调用
- **可集成**：易于与其他系统集成
- **可扩展**：支持自定义接口
- **标准化**：RESTful API 设计

---

## 五、交互模式选择

### 5.1 场景推荐

| 场景 | 推荐模式 | 原因 |
|------|----------|------|
| **日常交易** | Web UI | 直观查看信号和持仓 |
| **自动化脚本** | CLI | 可脚本化，易于集成 |
| **系统集成** | API | 灵活调用，标准接口 |
| **远程管理** | CLI + API | SSH + API 组合 |
| **移动查看** | Web UI | 响应式设计，支持手机 |

### 5.2 混合使用

系统支持多种模式同时运行：

```bash
# 同时启动 Web UI 和 API
python scripts/core/main.py --web --api --port 8080 --api-port 8081
```

---

## 六、配置管理

### 6.1 配置文件

| 文件 | 用途 |
|------|------|
| `config/config.json` | 主配置 |
| `config/positions.json` | 持仓配置 |
| `config/web.json` | Web UI 配置 |
| `config/api.json` | API 配置 |

### 6.2 Web UI 配置

```json
{
  "web": {
    "enabled": true,
    "port": 8080,
    "host": "0.0.0.0",
    "auth": {
      "enabled": false,
      "username": "admin",
      "password": "admin"
    }
  }
}
```

### 6.3 API 配置

```json
{
  "api": {
    "enabled": true,
    "port": 8081,
    "host": "0.0.0.0",
    "cors": {
      "enabled": true,
      "origins": ["*"]
    }
  }
}
```

---

## 七、安全注意事项

### 7.1 网络安全

- **生产环境**：建议启用认证
- **防火墙**：仅开放必要端口
- **HTTPS**：建议使用 SSL 加密

### 7.2 访问控制

- **CLI**：系统用户权限控制
- **Web UI**：用户名密码认证
- **API**：Token 认证

---

## 八、故障排除

### 8.1 常见问题

| 问题 | 解决方案 |
|------|----------|
| **端口被占用** | 修改配置文件中的端口号 |
| **无法访问 Web UI** | 检查防火墙设置 |
| **API 调用失败** | 检查服务是否启动 |
| **日志查看** | 查看 `logs/` 目录 |

### 8.2 日志位置

| 日志类型 | 位置 |
|----------|------|
| **系统日志** | `logs/system.log` |
| **访问日志** | `logs/access.log` |
| **错误日志** | `logs/error.log` |

---

*本指南由 WorkBuddy 于 2026-06-18 创建*
