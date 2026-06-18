# 版本号管理规范

> 版本：v1.0 | 创建日期：2026-06-17
> 适用范围：QuantNova 全系统

---

## 一、问题背景

当前版本历史存在主版本号增长过快的问题：

| 版本 | 日期 | 实际变更 | 问题 |
|------|------|----------|------|
| v1.0.0 | 2026-05-15 | 初始版本 | - |
| v2.0.0 | 2026-06-01 | 自适应系统 | 跳级，应为 v1.1.0 |
| v3.0.0 | 2026-06-14 | 推理优先架构 | 跳级，应为 v1.2.0 |
| v3.1.0 | 2026-06-14 | 机制门思想 | 正确 |
| v3.2.0 | 2026-06-14 | 五路径框架 | 正确 |
| v5.0.0 | 2026-06-16 | 因子进化引擎 | 跳级，应为 v1.3.0 |
| v6.0.0 | 2026-06-16 | Reasoner深度分析 | 跳级，应为 v1.4.0 |
| v6.1.0 | 2026-06-17 | FinClaw整合 | 正确 |

**核心问题**：将"新功能"等同于"破坏性变更"，导致主版本号虚高。

---

## 二、版本号格式

采用语义化版本号（Semantic Versioning 2.0.0）+ 项目扩展：

```
MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
```

### 2.1 核心版本号

| 字段 | 含义 | 增量条件 |
|------|------|----------|
| **MAJOR** | 主版本号 | 不兼容的 API 变更 |
| **MINOR** | 次版本号 | 向后兼容的功能新增 |
| **PATCH** | 补丁号 | 向后兼容的问题修复 |

### 2.2 预发布标签（可选）

```
1.0.0-alpha.1    # 内部测试版
1.0.0-beta.1     # 外部测试版
1.0.0-rc.1       # 候选发布版
```

### 2.3 构建元数据（可选）

```
1.0.0+20260617    # 构建日期
1.0.0+build.475   # 构建编号（测试数量）
```

---

## 三、增量标准

### 3.1 MAJOR 增量（主版本号）

**触发条件**（满足任一即升级）：

1. **数据格式不兼容**
   - 数据库表结构变更（DROP/RENAME 列）
   - 配置文件格式变更（不向后兼容）
   - 扫描结果 JSON 格式变更（删除/重命名字段）

2. **API 不兼容变更**
   - 核心模块接口签名变更（删除参数、改变类型）
   - 工具脚本命令行参数不兼容变更
   - 数据源返回格式变更

3. **行为不兼容变更**
   - 默认数据源优先级变更
   - 信号筛选逻辑变更（可能导致不同结果）
   - 输出格式变更（影响下游消费）

4. **依赖不兼容变更**
   - Python 最低版本要求提升
   - 核心依赖（TqSdk/AkShare）大版本升级

**示例**：
```python
# ❌ 错误：新功能不应升 MAJOR
v6.0.0 → v7.0.0  # 新增套利分析模块

# ✅ 正确：新功能升 MINOR
v6.0.0 → v6.1.0  # 新增套利分析模块
```

### 3.2 MINOR 增量（次版本号）

**触发条件**（满足任一即升级）：

1. **新功能模块**
   - 新增独立模块（如套利分析、知识锚点）
   - 新增 CLI 参数（如 `--arbitrage`）
   - 新增数据类型路由

2. **功能增强**
   - 现有模块功能扩展（如 UnifiedDataRouter 新增数据类型）
   - LLM prompt 增强（如注入新数据维度）
   - 输出格式扩展（如新增分级输出）

3. **接口新增**
   - 新增公开 API（如 `router.get_basis()`）
   - 新增配置选项（如 `data_routing.priorities`）
   - 新增回调/钩子

4. **性能优化**
   - 显著性能提升（>20%）
   - 内存占用显著降低

**示例**：
```python
# ✅ 正确：新功能升 MINOR
v6.1.0 → v6.2.0  # 新增宏观数据模块
v6.1.0 → v6.2.0  # 新增 --output-level 参数
```

### 3.3 PATCH 增量（补丁号）

**触发条件**（满足任一即升级）：

1. **Bug 修复**
   - 修复计算错误
   - 修复数据解析错误
   - 修复边界条件处理

2. **文档修正**
   - 修复文档错误
   - 更新示例代码
   - 补充缺失说明

3. **测试增强**
   - 补充测试用例
   - 修复测试中的问题
   - 提升测试覆盖率

4. **配置调整**
   - 默认参数调整（向后兼容）
   - 超时时间调整
   - 重试策略调整

**示例**：
```python
# ✅ 正确：Bug 修复升 PATCH
v6.1.0 → v6.1.1  # 修复基差计算错误
v6.1.0 → v6.1.2  # 修复龙虎榜解析问题
```

---

## 四、特殊版本规则

### 4.1 开发版本

```
0.y.z      # 初始开发阶段（v0.x.y）
```

- 所有 API 随时可能变更
- 不保证向后兼容
- 用于内部开发和测试

### 4.2 里程碑版本

```
x.y.0-rc.N  # 候选发布版
```

- 功能冻结，只修复 Bug
- 用于集成测试和用户验收
- 通过后发布正式版

### 4.3 热修复版本

```
x.y.z+hotfix.N  # 紧急修复
```

- 仅修复严重 Bug
- 不包含新功能
- 快速发布

---

## 五、版本生命周期

### 5.1 版本阶段

```
开发 → 测试 → 候选 → 正式 → 维护 → 停止维护
 (dev) (beta) (rc) (stable) (maint) (eol)
```

### 5.2 支持策略

| 版本类型 | 支持周期 | 安全更新 | Bug修复 |
|----------|----------|----------|---------|
| 正式版 (stable) | 至少 6 个月 | ✅ | ✅ |
| 候选版 (rc) | 至下个正式版 | ✅ | ✅ |
| 测试版 (beta) | 至下个候选版 | ❌ | ✅ |
| 开发版 (dev) | 无保证 | ❌ | ❌ |

### 5.3 版本命名规范

| 阶段 | 版本格式 | 示例 |
|------|----------|------|
| 开发中 | `x.y.z-dev.N` | `6.2.0-dev.1` |
| 测试中 | `x.y.z-beta.N` | `6.2.0-beta.1` |
| 候选发布 | `x.y.z-rc.N` | `6.2.0-rc.1` |
| 正式发布 | `x.y.z` | `6.2.0` |
| 热修复 | `x.y.z+hotfix.N` | `6.2.1+hotfix.1` |

---

## 六、发布流程

### 6.1 标准发布流程

```
1. 功能开发 → 分支开发
2. 代码审查 → 合并到 main
3. 测试验证 → 通过全部测试
4. 版本号更新 → 更新 __version__.py
5. 文档更新 → 更新 README/SKILL/CHANGELOG
6. 标签创建 → git tag -a v6.2.0
7. 推送发布 → git push && git push --tags
8. 发布说明 → GitHub Release Notes
```

### 6.2 热修复流程

```
1. 发现严重 Bug → 创建 hotfix 分支
2. 修复问题 → 最小改动原则
3. 测试验证 → 回归测试
4. 版本号更新 → PATCH +1
5. 快速发布 → 跳过候选阶段
```

---

## 七、版本号重置建议

当前版本号已虚高至 v6.1.0，建议在下个里程碑进行重置：

### 方案 A：保持当前版本（推荐）

```
继续使用 v6.x.x 系列
v6.1.0 → v6.2.0 → v6.3.0 → ... → v7.0.0（重大架构变更时）
```

**优点**：不破坏现有引用，平滑过渡
**缺点**：版本号仍然偏高

### 方案 B：重置为 v1.0.0

```
以 FinClaw 整合为新起点
v6.1.0 → v1.0.0（FinClaw 整合版）
```

**优点**：版本号清晰，重新开始
**缺点**：破坏现有引用，需要迁移

### 方案 C：重置为 v0.x.0

```
标记为开发阶段
v6.1.0 → v0.1.0（新架构版）
```

**优点**：明确表示仍在开发中
**缺点**：给人不稳定的印象

**推荐方案 A**，在 v7.0.0 时进行重大架构升级。

---

## 八、自动化工具

### 8.1 版本号检查脚本

```python
#!/usr/bin/env python3
"""版本号一致性检查"""

import re
from pathlib import Path

def check_version_consistency():
    """检查所有文件中的版本号是否一致"""
    target_version = "6.1.0"
    
    files_to_check = {
        "scripts/trend_scanner/__version__.py": r'__version__ = "(\d+\.\d+\.\d+)"',
        "scripts/trend_scanner/__init__.py": r'__version__ = "(\d+\.\d+\.\d+)"',
        "setup.py": r'version="(\d+\.\d+\.\d+)"',
    }
    
    inconsistencies = []
    
    for file_path, pattern in files_to_check.items():
        try:
            content = Path(file_path).read_text(encoding='utf-8')
            match = re.search(pattern, content)
            if match:
                version = match.group(1)
                if version != target_version:
                    inconsistencies.append(f"{file_path}: {version} != {target_version}")
        except FileNotFoundError:
            inconsistencies.append(f"{file_path}: 文件不存在")
    
    if inconsistencies:
        print("版本号不一致：")
        for issue in inconsistencies:
            print(f"  - {issue}")
        return False
    else:
        print(f"所有文件版本号一致: {target_version}")
        return True

if __name__ == "__main__":
    check_version_consistency()
```

### 8.2 版本号自动更新脚本

```python
#!/usr/bin/env python3
"""自动更新版本号"""

import re
from pathlib import Path

def update_version(new_version: str):
    """更新所有文件中的版本号"""
    files_to_update = {
        "scripts/trend_scanner/__version__.py": [
            (r'__version__ = "\d+\.\d+\.\d+"', f'__version__ = "{new_version}"'),
        ],
        "scripts/trend_scanner/__init__.py": [
            (r'__version__ = "\d+\.\d+\.\d+"', f'__version__ = "{new_version}"'),
        ],
        "setup.py": [
            (r'version="\d+\.\d+\.\d+"', f'version="{new_version}"'),
        ],
    }
    
    for file_path, replacements in files_to_update.items():
        try:
            content = Path(file_path).read_text(encoding='utf-8')
            for pattern, replacement in replacements:
                content = re.sub(pattern, replacement, content)
            Path(file_path).write_text(content, encoding='utf-8')
            print(f"已更新 {file_path}")
        except FileNotFoundError:
            print(f"跳过 {file_path}（文件不存在）")
    
    print(f"版本号已更新为 {new_version}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        update_version(sys.argv[1])
    else:
        print("用法: python update_version.py <version>")
```

---

## 九、版本号决策树

```
新增/修改代码后
    │
    ├── 是否破坏现有 API？
    │   ├── 是 → MAJOR +1
    │   └── 否 ↓
    │
    ├── 是否新增功能？
    │   ├── 是 → MINOR +1
    │   └── 否 ↓
    │
    ├── 是否修复 Bug？
    │   ├── 是 → PATCH +1
    │   └── 否 ↓
    │
    └── 无需更新版本号
```

---

## 十、版本号记录规范

### 10.1 CHANGELOG 格式

```markdown
# Changelog

## [6.2.0] - 2026-06-18

### Added
- 新增宏观数据分析模块
- 新增 --macro 参数

### Changed
- 优化数据路由性能

### Fixed
- 修复基差计算精度问题

### Deprecated
- 即将弃用 CsvSource（建议使用 DuckDB）

### Removed
- 移除废弃的 OldAnalyzer 模块

### Security
- 更新依赖版本修复安全漏洞
```

### 10.2 版本号在代码中的位置

| 文件 | 位置 | 用途 |
|------|------|------|
| `__version__.py` | `__version__` 变量 | 主版本号定义 |
| `__init__.py` | `__version__` 变量 | 模块导入时可用 |
| `setup.py` | `version` 参数 | PyPI 发布 |
| `README.md` | 标题和描述 | 用户可见 |
| `SKILL.md` | 标题和描述 | 技能定义 |

---

## 附录 A：版本号速查表

| 场景 | 示例 | 说明 |
|------|------|------|
| 新增模块 | v6.1.0 → v6.2.0 | MINOR +1 |
| 新增 CLI 参数 | v6.1.0 → v6.2.0 | MINOR +1 |
| 修复计算错误 | v6.1.0 → v6.1.1 | PATCH +1 |
| 修复文档错误 | v6.1.0 → v6.1.1 | PATCH +1 |
| 数据库表结构变更 | v6.1.0 → v7.0.0 | MAJOR +1 |
| 删除公开 API | v6.1.0 → v7.0.0 | MAJOR +1 |
| 依赖大版本升级 | v6.1.0 → v7.0.0 | MAJOR +1 |
| 性能优化 | v6.1.0 → v6.2.0 | MINOR +1 |
| 补充测试用例 | v6.1.0 → v6.1.1 | PATCH +1 |

---

## 附录 B：当前版本重映射（参考）

如果未来决定重置版本号，以下是重映射建议：

| 当前版本 | 重映射为 | 说明 |
|----------|----------|------|
| v1.0.0 | v0.1.0 | 初始版本 |
| v2.0.0 | v0.2.0 | 自适应系统 |
| v3.0.0 | v0.3.0 | 推理优先架构 |
| v3.1.0 | v0.4.0 | 机制门思想 |
| v3.2.0 | v0.5.0 | 五路径框架 |
| v5.0.0 | v0.6.0 | 因子进化引擎 |
| v6.0.0 | v0.7.0 | Reasoner深度分析 |
| v6.1.0 | v1.0.0 | FinClaw整合（新起点） |

---

*本规范由 WorkBuddy 于 2026-06-17 创建，版本 v1.0。*
