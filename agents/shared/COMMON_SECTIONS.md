# QuantNova 共享章节

> 版本：v1.0 | 创建日期：2026-06-15
> 所有 Agent 共享的章节内容

## 一、使用方式

### 1.1 作为 WorkBuddy Agent

```python
# 通过 WorkBuddy Agent 系统调用
from tools.<agent_name> import <AgentClass>

agent = <AgentClass>()
result = agent.<method>(<input_data>)
print(result)
```

### 1.2 作为独立脚本

```bash
# 基本用法
python tools/<agent_name>.py --<input_type> <input_value>

# 输出 JSON 格式
python tools/<agent_name>.py --<input_type> <input_value> --output json

# 保存结果到文件
python tools/<agent_name>.py --<input_type> <input_value> --save
```

## 二、错误处理

### 2.1 通用错误处理策略

| 错误类型 | 处理方式 |
|----------|----------|
| LLM 调用失败 | 使用规则退化，生成基本建议 |
| 数据源不可用 | 尝试备用数据源，记录日志 |
| 数据不足 | 返回 DATA_INSUFFICIENT 状态 |
| 超时 | 重试 1 次，仍失败则跳过 |
| 解析失败 | 返回原始数据，添加警告 |

### 2.2 降级策略

当 LLM 不可用时，使用规则退化：

```python
def fallback_response(context):
    """规则退化响应"""
    return {
        "routes": [{
            "route_id": "A",
            "name": "观望等待",
            "action": "暂不操作，等待更明确的信号",
            "confidence": 0.5,
            "reasoning": "LLM 不可用，使用规则退化建议",
            "constraints": [],
            "risks": ["无法进行深度推理，建议仅供参考"]
        }],
        "recommended_route": "A",
        "warnings": ["当前使用规则退化模式，建议质量有限"]
    }
```

## 三、日志规范

### 3.1 日志格式

```json
{
  "timestamp": "2026-06-15T10:30:00",
  "component": "reasoner|debater|evolver|orchestrator",
  "level": "INFO|WARN|ERROR",
  "message": "推理完成，生成 2 个方案",
  "context": {
    "symbol": "DCE.jm2609",
    "processing_time_ms": 1200
  }
}
```

### 3.2 日志级别

| 级别 | 使用场景 |
|------|----------|
| INFO | 正常操作，如"开始分析"、"分析完成" |
| WARN | 非致命错误，如"数据不足"、"使用备用数据源" |
| ERROR | 致命错误，如"LLM 调用失败"、"数据源不可用" |

## 四、性能指标

### 4.1 通用指标

| 指标 | 说明 | 目标值 |
|------|------|--------|
| 成功率 | 成功处理的请求比例 | > 95% |
| 平均处理时间 | 从接收到输出的时间 | < 5s |
| Token 消耗 | 每次处理消耗的 token 数 | < 5000 |
| 错误率 | 处理失败的请求比例 | < 5% |

### 4.2 监控指标格式

```json
{
  "component": "reasoner",
  "metrics": {
    "total_requests": 100,
    "success_count": 95,
    "error_count": 5,
    "success_rate": 0.95,
    "avg_processing_time_ms": 1200,
    "total_tokens_used": 250000
  }
}
```

## 五、配置管理

### 5.1 配置优先级

1. 命令行参数（最高优先级）
2. 环境变量
3. 配置文件（config.json）
4. 默认值（最低优先级）

### 5.2 配置热加载

- 脚本层（Scanner/Monitor）：每次执行时读取 config.json，无需重启
- Agent 层（Reasoner/Debater/Evolver）：Orchestrator 在触发时传递最新配置

## 六、安全规范

### 6.1 数据安全

- 不在日志中记录敏感信息（如 API Key）
- 不在输出中暴露内部实现细节
- 不在错误消息中泄露系统路径

### 6.2 操作安全

- 所有外部操作（如修改配置）需要用户确认
- 所有破坏性操作（如删除数据）需要二次确认
- 所有批量操作需要限制数量和频率

## 七、文档规范

### 7.1 文档结构

所有 Agent 文档应包含以下章节：
- 概述（Agent 特有）
- 核心理念（引用共享文档）
- 职责（Agent 特有）
- 输入格式（引用共享文档）
- 输出格式（引用共享文档）
- 工作流程（Agent 特有）
- 触发条件（Agent 特有）
- 配置参数（Agent 特有）
- 使用方式（引用共享文档）
- 依赖模块（Agent 特有）
- 错误处理（引用共享文档）
- 监控指标（Agent 特有）

### 7.2 引用格式

在 Agent 文档中引用共享章节：

```markdown
## 使用方式

参见 [共享章节 - 使用方式](shared/COMMON_SECTIONS.md#一使用方式)
```
