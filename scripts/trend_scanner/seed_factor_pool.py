"""
种子因子池管理器

从研报中提取因子逻辑，构建高质量种子因子池。
基于 FactorEngine 论文的知识注入引导模块思想。

流程：
    研报 → report_parser.py 提取 → 结构化因子逻辑 → 代码生成 → 种子因子池

版本：v1.0
创建日期：2026-06-16
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class SeedFactor:
    """种子因子"""
    name: str
    code: str
    logic: str                    # 因子逻辑描述
    economic_rationale: str       # 经济原理解释
    source: str                   # 来源（研报名称/URL）
    category: str = 'unknown'     # 分类：momentum/value/volatility/volume/composite
    status: str = 'pending'       # 状态：pending/validated/evolved/discarded
    evaluation: Dict = field(default_factory=dict)
    created_at: str = ''
    updated_at: str = ''

    def to_dict(self) -> Dict:
        return asdict(self)


class SeedFactorPool:
    """
    种子因子池管理器

    管理从研报中提取的种子因子，支持：
    - 添加种子因子
    - 验证种子因子
    - 状态管理
    - 导出到因子知识库
    """

    def __init__(self, pool_path: str = None):
        """
        初始化种子因子池

        Args:
            pool_path: 种子因子池文件路径
        """
        if pool_path is None:
            pool_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', 'data', 'seed_factors.json'
            )
        self.pool_path = pool_path
        self.pool: List[SeedFactor] = self._load_pool()

    def add_seed(self, name: str, code: str, logic: str,
                 economic_rationale: str, source: str,
                 category: str = 'unknown') -> str:
        """
        添加种子因子

        Args:
            name: 因子名称
            code: 因子代码（必须定义 factor(df) 函数）
            logic: 因子逻辑描述
            economic_rationale: 经济原理解释
            source: 来源
            category: 分类

        Returns:
            因子名称
        """
        seed = SeedFactor(
            name=name,
            code=code,
            logic=logic,
            economic_rationale=economic_rationale,
            source=source,
            category=category,
            status='pending',
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

        # 检查是否已存在
        existing = [s for s in self.pool if s.name == name]
        if existing:
            logger.warning(f"种子因子已存在，将覆盖: {name}")
            self.pool = [s for s in self.pool if s.name != name]

        self.pool.append(seed)
        self._save_pool()

        logger.info(f"添加种子因子: {name} (来源: {source})")
        return name

    def get_pending_seeds(self) -> List[SeedFactor]:
        """获取待验证的种子因子"""
        return [s for s in self.pool if s.status == 'pending']

    def get_validated_seeds(self) -> List[SeedFactor]:
        """获取已验证的种子因子"""
        return [s for s in self.pool if s.status == 'validated']

    def get_evolved_seeds(self) -> List[SeedFactor]:
        """获取已进化的种子因子"""
        return [s for s in self.pool if s.status == 'evolved']

    def get_by_category(self, category: str) -> List[SeedFactor]:
        """按分类获取种子因子"""
        return [s for s in self.pool if s.category == category]

    def update_status(self, name: str, status: str, evaluation: Dict = None):
        """
        更新种子因子状态

        Args:
            name: 因子名称
            status: 新状态
            evaluation: 评估结果
        """
        for seed in self.pool:
            if seed.name == name:
                seed.status = status
                seed.updated_at = datetime.now().isoformat()
                if evaluation:
                    seed.evaluation = evaluation
                break
        self._save_pool()

    def remove_seed(self, name: str) -> bool:
        """移除种子因子"""
        original_len = len(self.pool)
        self.pool = [s for s in self.pool if s.name != name]
        if len(self.pool) < original_len:
            self._save_pool()
            return True
        return False

    def get_summary(self) -> Dict:
        """获取种子因子池摘要"""
        categories = {}
        for seed in self.pool:
            cat = seed.category
            if cat not in categories:
                categories[cat] = 0
            categories[cat] += 1

        statuses = {}
        for seed in self.pool:
            st = seed.status
            if st not in statuses:
                statuses[st] = 0
            statuses[st] += 1

        return {
            'total': len(self.pool),
            'categories': categories,
            'statuses': statuses,
        }

    def export_to_knowledge_base(self, kb_path: str = None) -> int:
        """
        导出已验证/已进化的种子到因子知识库

        Args:
            kb_path: 因子知识库路径

        Returns:
            导出数量
        """
        if kb_path is None:
            kb_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', 'data', 'factor_knowledge.json'
            )

        # 加载现有知识库
        kb = {'factors': [], 'metadata': {'version': '1.0', 'total_factors': 0}}
        if os.path.exists(kb_path):
            try:
                with open(kb_path, 'r', encoding='utf-8') as f:
                    kb = json.load(f)
            except Exception:
                pass

        # 导出已验证/已进化的种子
        exported = 0
        for seed in self.pool:
            if seed.status in ('validated', 'evolved'):
                # 检查是否已存在
                existing_names = [f.get('name') for f in kb['factors']]
                if seed.name not in existing_names:
                    kb['factors'].append({
                        'id': f"seed_{len(kb['factors']) + 1:03d}",
                        'name': seed.name,
                        'code': seed.code,
                        'description': seed.logic,
                        'logic': seed.economic_rationale,
                        'source': seed.source,
                        'category': seed.category,
                        'evaluation': seed.evaluation,
                        'created_at': seed.created_at,
                    })
                    exported += 1

        kb['metadata']['total_factors'] = len(kb['factors'])
        kb['metadata']['last_updated'] = datetime.now().isoformat()

        # 保存
        with open(kb_path, 'w', encoding='utf-8') as f:
            json.dump(kb, f, ensure_ascii=False, indent=2)

        logger.info(f"导出 {exported} 个种子因子到知识库: {kb_path}")
        return exported

    def _load_pool(self) -> List[SeedFactor]:
        """加载种子因子池"""
        if os.path.exists(self.pool_path):
            try:
                with open(self.pool_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return [SeedFactor(**item) for item in data.get('seeds', [])]
            except Exception as e:
                logger.error(f"加载种子因子池失败: {e}")
        return []

    def _save_pool(self):
        """保存种子因子池"""
        os.makedirs(os.path.dirname(self.pool_path), exist_ok=True)
        data = {
            'seeds': [s.to_dict() for s in self.pool],
            'summary': self.get_summary(),
            'updated_at': datetime.now().isoformat(),
        }
        with open(self.pool_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_from_report_parser(self, report_path: str = None) -> int:
        """
        从 report_parser 的输出中加载因子

        Args:
            report_path: 报告解析结果路径

        Returns:
            加载的因子数量
        """
        if report_path is None:
            report_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', 'data', 'report_factors.json'
            )

        if not os.path.exists(report_path):
            logger.warning(f"报告解析结果不存在: {report_path}")
            return 0

        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            count = 0
            for factor in data.get('factors', []):
                name = factor.get('name', f'report_factor_{count}')
                code = factor.get('code', '')
                logic = factor.get('logic', '')
                rationale = factor.get('economic_rationale', '')
                source = factor.get('source', 'research_report')

                if code and 'def factor' in code:
                    self.add_seed(
                        name=name,
                        code=code,
                        logic=logic,
                        economic_rationale=rationale,
                        source=source,
                        category=self._classify_factor(logic),
                    )
                    count += 1

            logger.info(f"从报告中加载 {count} 个种子因子")
            return count

        except Exception as e:
            logger.error(f"加载报告因子失败: {e}")
            return 0

    def _classify_factor(self, logic: str) -> str:
        """根据逻辑描述自动分类因子"""
        logic_lower = logic.lower()

        if any(k in logic_lower for k in ['动量', 'momentum', '趋势', 'trend']):
            return 'momentum'
        elif any(k in logic_lower for k in ['价值', 'value', '估值', 'pe', 'pb']):
            return 'value'
        elif any(k in logic_lower for k in ['波动', 'volatility', '风险', 'risk']):
            return 'volatility'
        elif any(k in logic_lower for k in ['量', 'volume', '换手', 'turnover']):
            return 'volume'
        else:
            return 'composite'


# ============================================================
# 预置种子因子（从研报常见因子逻辑中提取）
# ============================================================

PRESET_SEED_FACTORS = [
    {
        'name': 'adaptive_momentum',
        'code': '''def factor(df):
    """自适应动量因子：根据波动率调整动量窗口"""
    import pandas as pd
    import numpy as np
    vol = df['close'].pct_change().rolling(20).std()
    vol_median = vol.rolling(60).median()
    vol_ratio = vol / vol_median.replace(0, np.nan)
    # 高波动时缩短窗口，低波动时延长窗口
    window = (20 / vol_ratio).clip(5, 60).fillna(20).astype(int)
    result = pd.Series(0.0, index=df.index)
    for i in range(60, len(df)):
        w = window.iloc[i]
        if w > 0 and i >= w:
            result.iloc[i] = df['close'].iloc[i] / df['close'].iloc[i - w] - 1
    return result.fillna(0)
''',
        'logic': '根据波动率自适应调整动量窗口，高波动时用短窗口快速响应，低波动时用长窗口过滤噪声',
        'economic_rationale': '期货市场波动率具有聚集性，高波动期趋势反转快，需要短窗口捕捉；低波动期趋势稳定，长窗口更可靠',
        'source': 'preset',
        'category': 'momentum',
    },
    {
        'name': 'volatility_adjusted_trend',
        'code': '''def factor(df):
    """波动率调整趋势因子：EMA 距离除以 ATR"""
    import pandas as pd
    import numpy as np
    ema20 = df['close'].ewm(span=20, adjust=False).mean()
    ema60 = df['close'].ewm(span=60, adjust=False).mean()
    high, low, close = df['high'], df['low'], df['close']
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    # 趋势距离 / ATR，标准化到风险单位
    return ((ema20 - ema60) / atr.replace(0, np.nan)).fillna(0)
''',
        'logic': 'EMA20/EMA60 趋势距离除以 ATR，将趋势强度标准化到风险单位',
        'economic_rationale': '单纯的趋势距离（EMA20-EMA60）在不同品种间不可比，除以 ATR 后可以跨品种比较趋势强度',
        'source': 'preset',
        'category': 'momentum',
    },
    {
        'name': 'volume_breakout',
        'code': '''def factor(df):
    """成交量突破因子：当日成交量 / 20日均量"""
    import pandas as pd
    vol_ratio = df['volume'] / df['volume'].rolling(20).mean().replace(0, 1)
    # 成交量突破配合价格方向
    price_change = df['close'].pct_change()
    return (vol_ratio * price_change.apply(lambda x: 1 if x > 0 else -1)).fillna(0)
''',
        'logic': '成交量突破（当日量/20日均量）乘以价格方向，放量上涨为正，放量下跌为负',
        'economic_rationale': '成交量是市场参与度的直接指标，放量配合价格方向是趋势确认的经典信号',
        'source': 'preset',
        'category': 'volume',
    },
    {
        'name': 'regime_adaptive_rsi',
        'code': '''def factor(df):
    """市场状态自适应 RSI：趋势行情用 RSI 突破，震荡行情用 RSI 反转"""
    import pandas as pd
    import numpy as np
    # 计算 ADX 判断市场状态
    period = 14
    high, low, close = df['high'], df['low'], df['close']
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0)
    plus_di = 100 * plus_dm.rolling(period).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.rolling(period).mean() / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.rolling(period).mean()
    # 计算 RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    # 趋势行情：RSI > 50 做多，< 50 做空
    # 震荡行情：RSI > 70 做空，< 30 做多
    is_trending = adx > 25
    trend_signal = (rsi - 50) / 50
    range_signal = -(rsi - 50) / 50
    result = trend_signal.where(is_trending, range_signal)
    return result.fillna(0)
''',
        'logic': '根据 ADX 判断市场状态，趋势行情用 RSI 突破逻辑，震荡行情用 RSI 反转逻辑',
        'economic_rationale': 'RSI 在趋势和震荡行情中的有效逻辑不同：趋势中应顺势（RSI>50做多），震荡中应逆势（RSI>70做空）',
        'source': 'preset',
        'category': 'composite',
    },
    {
        'name': 'multi_timeframe_momentum',
        'code': '''def factor(df):
    """多时间框架动量因子：5日+20日+60日动量加权"""
    import pandas as pd
    mom5 = df['close'].pct_change(5)
    mom20 = df['close'].pct_change(20)
    mom60 = df['close'].pct_change(60)
    # 短期动量权重高，长期动量权重低
    result = 0.5 * mom5 + 0.3 * mom20 + 0.2 * mom60
    return result.fillna(0)
''',
        'logic': '多时间框架动量加权：5日(50%) + 20日(30%) + 60日(20%)',
        'economic_rationale': '不同时间框架的动量信号可以互补：短期动量响应快但噪声大，长期动量稳定但滞后',
        'source': 'preset',
        'category': 'momentum',
    },
]


def init_preset_seeds(pool: SeedFactorPool) -> int:
    """
    初始化预置种子因子

    Args:
        pool: 种子因子池

    Returns:
        新增数量
    """
    count = 0
    for preset in PRESET_SEED_FACTORS:
        existing = [s for s in pool.pool if s.name == preset['name']]
        if not existing:
            pool.add_seed(**preset)
            count += 1
    return count
