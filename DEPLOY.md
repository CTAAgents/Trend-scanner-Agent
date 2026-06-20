# QuantNova 本地部署指南

> 本指南帮助你在本地部署和运行 QuantNova 系统

---

## 一、环境要求

- **操作系统**: Windows 10/11
- **Python**: 3.10 或更高版本
- **磁盘空间**: 至少 1GB 可用空间
- **网络**: 需要访问期货数据源（TqSdk）

---

## 二、快速部署（3步完成）

### 步骤 1：安装依赖

```bash
# 双击运行（首次会自动安装依赖）
start.bat
```

或手动安装：

```bash
pip install -r requirements.txt
```

### 步骤 2：配置数据源

编辑 `config/config.json`，确保 TqSdk 账号密码正确：

```json
{
  "data_sources": {
    "tqsdk": {
      "user": "你的账号",
      "password": "你的密码"
    }
  }
}
```

### 步骤 3：启动系统

```bash
# 双击运行
start.bat
```

---

## 三、开机自启动

### 方法 A：自动安装（推荐）

以管理员身份运行：

```bash
install_startup.bat
```

### 方法 B：手动设置

1. 按 `Win+R`，输入 `taskschd.msc`
2. 点击"创建基本任务"
3. 名称：`QuantNova`
4. 触发器：`当用户登录时`
5. 操作：`启动程序`
6. 程序：`E:\QuantNova\service.bat`
7. 参数：`start`

---

## 四、服务管理

### 启动/停止服务

```bash
# 双击运行服务管理器
service.bat
```

### 查看状态

```bash
# 双击运行监控面板
monitor.bat
```

### 命令行操作

```bash
# 查看任务状态
schtasks /query /tn "QuantNova"

# 手动运行任务
schtasks /run /tn "QuantNova"

# 删除自启动任务
schtasks /delete /tn "QuantNova" /f
```

---

## 五、日志和调试

### 日志位置

- 服务日志：`logs/service.log`
- 系统日志：`logs/YYYY-MM-DD.jsonl`

### 查看日志

```bash
# 查看最近日志
type logs\service.log

# 实时监控
monitor.bat
```

---

## 六、常见问题

### Q1: 启动时报错"未找到Python"

**解决方案**：安装 Python 3.10+ 并添加到 PATH

### Q2: TqSdk连接失败

**解决方案**：
1. 检查网络连接
2. 确认账号密码正确
3. 检查防火墙设置

### Q3: 服务无法自启动

**解决方案**：
1. 以管理员身份运行 `install_startup.bat`
2. 检查任务计划程序：`taskschd.msc`

### Q4: 如何完全卸载

1. 删除自启动任务：`schtasks /delete /tn "QuantNova" /f`
2. 停止服务：`service.bat` → 选择停止
3. 删除项目目录

---

## 七、系统架构

```
E:\QuantNova\
├── start.bat          # 快速启动
├── service.bat        # 服务管理器
├── monitor.bat        # 状态监控
├── install_startup.bat # 安装开机自启动
├── scripts/           # 核心代码（简化后）
│   ├── futures/       # 期货子系统
│   ├── securities/    # 证券子系统
│   ├── reasoning/     # 推理+辩论引擎
│   ├── indicators/    # 指标计算
│   ├── fundamental/   # 基本面分析
│   ├── risk/          # 风控模块
│   └── core/          # 核心基础设施
├── config\            # 配置文件
├── data\              # 数据目录
├── logs\              # 日志目录
└── tools\             # 工具脚本
```

---

## 八、技术支持

遇到问题请查看：
- [README.md](README.md) - 完整技术文档
- [系统架构](docs/system_architecture_overview.md) - 架构详情
- [全景档案](docs/quantnova_system_overview.md) - 系统全景

---

*部署指南版本：v2.1.0 | 更新日期：2026-06-20 | 简化版*
