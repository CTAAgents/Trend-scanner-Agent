"""
统一数据路由层

提供单一入口点，按数据类型智能路由到最佳数据源：
- K线：  DuckDB → TqSdk → Pytdx(通达信) → CSV
- 行情：  DuckDB → TqSdk → Pytdx(通达信)
- 基差：  AkShare → Pytdx(通达信)
- 季节性： AkShare → 本地CSV
- 仓单：  AkShare
- 龙虎榜： AkShare
- 保证金： AkShare
- 宏观：  AkShare
- 交割：  AkShare

设计原则：
1. 扩展不替换 — 兼容现有 DataSource 体系
2. 配置驱动 — 路由优先级可通过 config.json 调整
3. 自动 Fallback — 按优先级链逐级降级
4. 统一返回格式 — DataResponse 标准化所有输出
5. 数据时效性 — 内置检查机制

使用方式：
    from trend_scanner.unified_data_router import UnifiedDataRouter

    router = UnifiedDataRouter()
    resp = router.get_kline("RB", days=120)
    if resp.ok:
        df = resp.data
        print(f"数据来源: {resp.source}, 回退: {resp.fallback_used}")
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Sequence
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 统一返回格式
# ---------------------------------------------------------------------------

@dataclass
class DataResponse:
    """统一数据返回格式"""
    ok: bool = False
    source: str = ""              # 'duckdb', 'tqsdk', 'pytdx', 'akshare', 'csv'
    fallback_used: bool = False   # 是否使用了降级数据源
    data_type: str = ""           # 'kline', 'quote', 'basis', 'seasonality', 'inventory'
    count: int = 0                # 数据条数
    data: Any = None              # DataFrame 或 Dict
    error: Optional[str] = None
    timestamp: str = ""           # ISO 格式获取时间
    staleness_hours: float = 0.0  # 数据滞后小时数（0=实时）

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ok': self.ok,
            'source': self.source,
            'fallback_used': self.fallback_used,
            'data_type': self.data_type,
            'count': self.count,
            'error': self.error,
            'timestamp': self.timestamp,
            'staleness_hours': self.staleness_hours,
        }


# ---------------------------------------------------------------------------
# 默认路由配置
# ---------------------------------------------------------------------------

DEFAULT_ROUTING = {
    "kline":        ["duckdb", "tqsdk", "pytdx", "csv"],
    "quote":        ["duckdb", "tqsdk", "pytdx"],
    "basis":        ["akshare", "pytdx"],
    "seasonality":  ["akshare", "csv"],
    "inventory":    ["akshare"],
    "top_list":     ["akshare"],
    "margin":       ["akshare"],
    "macro":        ["akshare"],
    "delivery":     ["akshare"],
}

# 数据时效性阈值（小时）
DEFAULT_STALENESS_THRESHOLD = {
    "kline": 4,          # K线允许4小时滞后
    "quote": 0.5,        # 行情30分钟
    "basis": 24,         # 基差允许1天
    "seasonality": 168,  # 季节性允许1周
    "inventory": 24,     # 仓单允许1天
    "top_list": 24,      # 龙虎榜允许1天
    "margin": 168,       # 保证金允许1周
    "macro": 168,        # 宏观数据允许1周
    "delivery": 720,     # 交割数据允许1月
}


# ---------------------------------------------------------------------------
# 品种代码标准化
# ---------------------------------------------------------------------------

# 交易所 → pytdx market 编号
PYTDX_MARKET_MAP = {
    "SHFE": 29,
    "DCE":  28,
    "CZCE": 30,
    "CFFEX": 47,
    "INE":  48,
}

# 品种 → 交易所映射（常见品种）
VARIETY_EXCHANGE_MAP = {
    # 黑色系
    "RB": "SHFE", "HC": "SHFE", "I": "DCE", "J": "DCE", "JM": "DCE",
    "SF": "CZCE", "SM": "CZCE",
    # 有色
    "CU": "SHFE", "AL": "SHFE", "ZN": "SHFE", "PB": "SHFE",
    "NI": "SHFE", "SN": "SHFE", "AO": "SHFE", "SS": "SHFE",
    # 能源化工
    "SC": "INE", "FU": "SHFE", "BU": "SHFE", "RU": "SHFE",
    "TA": "CZCE", "MA": "CZCE", "SA": "CZCE", "FG": "CZCE",
    "EG": "DCE", "EB": "DCE", "PP": "DCE", "V": "DCE", "L": "DCE",
    "PG": "DCE", "LU": "INE", "NR": "INE", "BC": "INE", "EC": "INE",
    # 农产品
    "CF": "CZCE", "SR": "CZCE", "AP": "CZCE", "RM": "CZCE", "OI": "CZCE",
    "M": "DCE", "Y": "DCE", "P": "DCE", "C": "DCE", "CS": "DCE",
    "A": "DCE", "B": "DCE", "JD": "DCE", "LH": "DCE",
    # 贵金属
    "AU": "SHFE", "AG": "SHFE",
    # 中金所
    "IF": "CFFEX", "IC": "CFFEX", "IH": "CFFEX", "IM": "CFFEX",
    "T": "CFFEX", "TF": "CFFEX", "TL": "CFFEX", "TS": "CFFEX",
}

# 品种 → AkShare 代码映射
# AkShare 期货品种代码格式与我们的统一格式有差异，需要转换
AKSHARE_FUTURES_MAP = {
    "RB": "螺纹钢", "HC": "热卷", "I": "铁矿石", "J": "焦炭", "JM": "焦煤",
    "CU": "沪铜", "AL": "沪铝", "ZN": "沪锌", "NI": "沪镍",
    "AU": "沪金", "AG": "沪银",
    "SC": "原油", "FU": "燃料油", "BU": "沥青", "RU": "橡胶",
    "TA": "PTA", "MA": "甲醇", "SA": "纯碱",
    "CF": "棉花", "SR": "白糖", "M": "豆粕", "Y": "豆油", "P": "棕榈油",
    "C": "玉米", "CS": "淀粉",
}


def normalize_symbol(symbol: str) -> str:
    """将各种格式的品种代码标准化为大写短代码

    Examples:
        "SHFE.rb" → "RB"
        "KQ.m@SHFE.rb" → "RB"
        "rb" → "RB"
        "RB" → "RB"
    """
    s = symbol.strip().upper()
    # 移除 TqSdk 主力合约前缀
    if s.startswith("KQ.M@"):
        s = s[5:]  # "KQ.m@SHFE.rb" → "SHFE.RB"
    # 移除交易所前缀
    for ex in ["SHFE.", "DCE.", "CZCE.", "CFFEX.", "INE."]:
        if s.startswith(ex):
            s = s[len(ex):]
            break
    # 移除合约月（如 RB2609 → RB）
    import re
    s = re.sub(r'\d{3,4}$', '', s)
    return s


# ---------------------------------------------------------------------------
# PytdxSource — 通达信 Python 直连
# ---------------------------------------------------------------------------

class PytdxSource:
    """通达信数据源（通过 pytdx 直连行情服务器）

    作为 TqSdk 的备选数据源，提供 K线/行情数据。
    """

    def __init__(self, host: str = '119.147.212.81', port: int = 7709):
        self._host = host
        self._port = port
        self._api = None
        self._connected = False

    def _ensure_connection(self) -> bool:
        """确保连接可用"""
        if self._connected and self._api is not None:
            return True
        try:
            from pytdx.hq import TdxHq_API
            self._api = TdxHq_API()
            self._connected = self._api.connect(self._host, self._port)
            return self._connected
        except Exception as e:
            logger.debug(f"pytdx 连接失败: {e}")
            self._connected = False
            return False

    def is_available(self) -> bool:
        """检查可用性"""
        return self._ensure_connection()

    def _get_market_code(self, symbol: str) -> tuple:
        """品种代码 → (market, code) 转换

        返回:
            (market_int, code_str) 或 None
        """
        variety = normalize_symbol(symbol)
        exchange = VARIETY_EXCHANGE_MAP.get(variety)
        if not exchange:
            return None
        market = PYTDX_MARKET_MAP.get(exchange)
        if market is None:
            return None

        # 构建合约代码（需要当月主力月份）
        # pytdx 格式: 小写品种+4位年月，如 "rb2610"
        # 如果传入的是具体合约（如 jm2609），直接使用
        import re
        if re.search(r'\d{3,4}$', symbol.lower()):
            # 已有合约月
            code = symbol.lower().split('.')[-1]  # 去掉交易所前缀
            if not code[0].isdigit():
                code = re.sub(r'^[A-Za-z]+\.', '', code)  # 再去一层
            # 补零：郑商所3位，其他4位
            if exchange == "CZCE":
                # CZCE 格式: CF609 → pytdx 用 CF609
                code = variety.lower() + self._get_czce_month()
            else:
                code = variety.lower() + self._get_nearest_month(variety)
        else:
            if exchange == "CZCE":
                code = variety.lower() + self._get_czce_month()
            else:
                code = variety.lower() + self._get_nearest_month(variety)

        return (market, code)

    def _get_nearest_month(self, variety: str) -> str:
        """获取最近的主力合约月份（4位）"""
        now = datetime.now()
        # 期货合约月份通常是 01,05,09 或 01,05,10 等模式
        # 简化处理：用当前年+下一个月
        year = now.year % 100
        month = now.month + 1
        if month > 12:
            year += 1
            month = 1
        return f"{year:02d}{month:02d}"

    def _get_czce_month(self) -> str:
        """郑商所3位合约月份"""
        now = datetime.now()
        year = now.year % 10  # 1位年份
        month = now.month + 1
        if month > 12:
            year = (now.year + 1) % 10
            month = 1
        return f"{year}{month:02d}"

    def get_kline(self, symbol: str, days: int = 120, period: str = "daily") -> Optional[pd.DataFrame]:
        """获取K线数据"""
        if not self._ensure_connection():
            return None

        mc = self._get_market_code(symbol)
        if mc is None:
            return None

        market, code = mc

        # period 映射
        category_map = {
            "daily": 4,     # 日线
            "1h": 5,        # 60分钟
            "15m": 6,       # 15分钟
            "30m": 5,       # 30分钟 → 用60分钟近似
            "5m": 7,        # 5分钟
        }
        category = category_map.get(period, 4)

        try:
            # 每次最多800条，分批获取
            all_bars = []
            start = 0
            batch_size = 800
            needed = days + 10  # 多取一点缓冲

            while len(all_bars) < needed:
                data = self._api.get_security_bars(category, market, code, start, batch_size)
                if not data:
                    break
                all_bars.extend(data)
                if len(data) < batch_size:
                    break
                start += batch_size

            if not all_bars:
                return None

            df = self._api.to_df(all_bars)
            if df is None or len(df) == 0:
                return None

            # 标准化列名
            col_map = {
                'datetime': 'date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'vol': 'volume',
                'amount': 'amount',
            }
            df = df.rename(columns=col_map)

            # 添加 open_interest 列（pytdx 可能没有）
            if 'open_interest' not in df.columns:
                if 'oi' in df.columns:
                    df['open_interest'] = df['oi']
                else:
                    df['open_interest'] = 0

            # 确保必要列存在
            required = ['date', 'open', 'high', 'low', 'close', 'volume', 'open_interest']
            for col in required:
                if col not in df.columns:
                    return None

            df = df[required].tail(days)
            df['date'] = pd.to_datetime(df['date'])
            df = df.reset_index(drop=True)
            return df

        except Exception as e:
            logger.debug(f"pytdx get_kline 失败: {e}")
            return None

    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取实时行情"""
        if not self._ensure_connection():
            return None

        mc = self._get_market_code(symbol)
        if mc is None:
            return None

        market, code = mc

        try:
            data = self._api.get_security_quotes([(market, code)])
            if not data:
                return None

            q = data[0]
            return {
                'symbol': symbol,
                'last_price': q.get('price', 0),
                'open': q.get('open', 0),
                'high': q.get('high', 0),
                'low': q.get('low', 0),
                'pre_close': q.get('last_close', 0),
                'volume': q.get('vol', 0),
                'open_interest': q.get('oi', 0),
                'bid_price1': q.get('bid1', 0),
                'ask_price1': q.get('ask1', 0),
            }

        except Exception as e:
            logger.debug(f"pytdx get_quote 失败: {e}")
            return None

    def disconnect(self):
        """断开连接"""
        if self._api and self._connected:
            try:
                self._api.disconnect()
            except:
                pass
            self._connected = False


# ---------------------------------------------------------------------------
# AkShareSource — 基差/季节性/仓单
# ---------------------------------------------------------------------------

class AkShareSource:
    """AkShare 数据源（基差、季节性、仓单等辅助数据）

    仅用于 TqSdk 无法覆盖的数据维度（基差、季节性），
    不作为 K线/行情的主力数据源。
    """

    def is_available(self) -> bool:
        try:
            import akshare
            return True
        except ImportError:
            return False

    def get_basis(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取基差数据

        基差 = 现货价格 - 期货价格

        返回:
            {
                'symbol': str,
                'spot_price': float,
                'futures_price': float,
                'basis': float,
                'basis_rate': float,  # 基差率 = 基差/现货
                'date': str,
            }
        """
        try:
            import akshare as ak
            variety = normalize_symbol(symbol)

            # 使用 futures_spot_price() 获取基差数据
            df = ak.futures_spot_price()
            if df is not None and len(df) > 0:
                # 过滤当前品种
                variety_row = df[df['symbol'] == variety]
                if len(variety_row) > 0:
                    latest = variety_row.iloc[0]
                    spot = float(latest.get('spot_price', 0) or 0)
                    futures = float(latest.get('dominant_contract_price', 0) or 0)
                    basis = float(latest.get('dom_basis', 0) or 0)
                    basis_rate = float(latest.get('dom_basis_rate', 0) or 0) * 100

                    return {
                        'symbol': variety,
                        'spot_price': spot,
                        'futures_price': futures,
                        'basis': basis,
                        'basis_rate': round(basis_rate, 2),
                        'date': str(latest.get('date', datetime.now().strftime('%Y%m%d'))),
                    }

            return None

        except Exception as e:
            logger.debug(f"AkShare get_basis 异常: {e}")
            return None

    def get_seasonality(self, symbol: str, years: int = 5) -> Optional[Dict[str, Any]]:
        """获取季节性规律数据

        返回各月份的历史平均涨跌幅，用于判断季节性趋势。

        返回:
            {
                'symbol': str,
                'monthly_avg_change': Dict[int, float],  # {1: 2.3, 2: -1.5, ...}
                'strong_months': List[int],               # 历史上涨概率>60%的月份
                'weak_months': List[int],                  # 历史下跌概率>60%的月份
                'current_month_signal': float,             # 当前月份的平均变化
                'years_covered': int,
            }
        """
        try:
            import akshare as ak
            variety = normalize_symbol(symbol)
            cn_name = AKSHARE_FUTURES_MAP.get(variety)
            if not cn_name:
                return None

            # 获取历史主力合约日线
            try:
                df = ak.futures_main_sina(symbol=cn_name, start_date=f"{datetime.now().year - years}0101",
                                          end_date=datetime.now().strftime('%Y%m%d'))
                if df is None or len(df) == 0:
                    return None

                # 标准化列名
                df.columns = [c.lower().strip() for c in df.columns]
                date_col = 'date' if 'date' in df.columns else df.columns[0]
                close_col = 'close' if 'close' in df.columns else '收盘价' if '收盘价' in df.columns else df.columns[-1]

                df[date_col] = pd.to_datetime(df[date_col])
                df[close_col] = pd.to_numeric(df[close_col], errors='coerce')
                df = df.dropna(subset=[close_col])

                if len(df) < 100:
                    return None

                # 按月份计算平均涨跌幅
                df['month'] = df[date_col].dt.month
                df['monthly_return'] = df[close_col].pct_change() * 100

                monthly_avg = {}
                monthly_pos_rate = {}
                for month in range(1, 13):
                    month_data = df[df['month'] == month]['monthly_return'].dropna()
                    if len(month_data) > 10:
                        monthly_avg[month] = round(month_data.mean(), 2)
                        monthly_pos_rate[month] = round((month_data > 0).mean() * 100, 1)

                # 识别强势/弱势月份
                strong_months = [m for m, r in monthly_pos_rate.items() if r >= 60]
                weak_months = [m for m, r in monthly_pos_rate.items() if r <= 40]

                current_month = datetime.now().month
                current_signal = monthly_avg.get(current_month, 0)

                return {
                    'symbol': variety,
                    'monthly_avg_change': monthly_avg,
                    'monthly_pos_rate': monthly_pos_rate,
                    'strong_months': strong_months,
                    'weak_months': weak_months,
                    'current_month_signal': current_signal,
                    'current_month_pos_rate': monthly_pos_rate.get(current_month, 0),
                    'years_covered': years,
                }

            except Exception as e:
                logger.debug(f"AkShare 季节性获取失败({variety}): {e}")
                return None

        except Exception as e:
            logger.debug(f"AkShare get_seasonality 异常: {e}")
            return None

    def get_inventory(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取仓单数据

        返回:
            {
                'symbol': str,
                'warehouse_receipts': int,
                'change': int,
                'date': str,
            }
        """
        try:
            import akshare as ak
            variety = normalize_symbol(symbol)
            cn_name = AKSHARE_FUTURES_MAP.get(variety)
            if not cn_name:
                return None

            try:
                df = ak.futures_inventory_99(symbol=cn_name)
                if df is not None and len(df) > 0:
                    latest = df.iloc[-1]
                    return {
                        'symbol': variety,
                        'warehouse_receipts': int(latest.iloc[-2] if len(latest) >= 2 else 0),
                        'change': int(latest.iloc[-1] if len(latest) >= 1 else 0),
                        'date': str(latest.name) if hasattr(latest, 'name') else datetime.now().strftime('%Y-%m-%d'),
                    }
            except Exception as e:
                logger.debug(f"AkShare 仓单获取失败({variety}): {e}")

            return None

        except Exception as e:
            logger.debug(f"AkShare get_inventory 异常: {e}")
            return None

    def get_top_list(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取龙虎榜数据（交易所每日公布的多空持仓排名）

        支持交易所：DCE（大商所）、SHFE（上期所）、CZCE（郑商所）

        返回:
            {
                'symbol': str,
                'date': str,
                'exchange': str,
                'top_buy': List[Dict],   # 多头前10名: [{rank, broker, volume, change}, ...]
                'top_sell': List[Dict],  # 空头前10名
                'net_buy': int,          # 多头总持仓量
                'net_sell': int,         # 空头总持仓量
                'concentration_buy': float,   # 多头集中度(%)
                'concentration_sell': float,  # 空头集中度(%)
                'interpretation': str,        # 一句话解读
            }
        """
        try:
            import akshare as ak
            variety = normalize_symbol(symbol)
            exchange = VARIETY_EXCHANGE_MAP.get(variety, '')
            if not exchange:
                return None

            # 根据交易所选择数据源
            date_str = datetime.now().strftime('%Y%m%d')
            df = None

            if exchange == 'DCE':
                # 大商所持仓排名
                for d in range(5):
                    try:
                        test_date = (datetime.now() - timedelta(days=d)).strftime('%Y%m%d')
                        df = ak.futures_dce_position_rank(date=test_date)
                        if df is not None and len(df) > 0:
                            date_str = test_date
                            break
                    except Exception:
                        continue

            elif exchange == 'SHFE':
                # 上期所持仓排名
                for d in range(5):
                    try:
                        test_date = (datetime.now() - timedelta(days=d)).strftime('%Y%m%d')
                        df = ak.futures_shfe_warehouse_receipt(date=test_date)
                        if df is not None and len(df) > 0:
                            date_str = test_date
                            break
                    except Exception:
                        continue

            elif exchange == 'CZCE':
                # 郑商所持仓排名
                for d in range(5):
                    try:
                        test_date = (datetime.now() - timedelta(days=d)).strftime('%Y%m%d')
                        df = ak.futures_czce_warehouse_receipt(date=test_date)
                        if df is not None and len(df) > 0:
                            date_str = test_date
                            break
                    except Exception:
                        continue

            if df is None or len(df) == 0:
                return None

            # 解析多空头排名
            top_buy = []
            top_sell = []

            # 标准化列名
            cols = [str(c).strip() for c in df.columns]

            # 查找关键列
            name_col = None
            buy_vol_col = None
            sell_vol_col = None
            buy_change_col = None
            sell_change_col = None

            for i, c in enumerate(cols):
                c_lower = c.lower()
                if '会员' in c or '经纪' in c or '公司' in c:
                    name_col = i
                elif ('买' in c or '多' in c) and ('持仓' in c or '量' in c):
                    buy_vol_col = i
                elif ('卖' in c or '空' in c) and ('持仓' in c or '量' in c):
                    sell_vol_col = i
                elif ('买' in c or '多' in c) and ('增减' in c or '变化' in c):
                    buy_change_col = i
                elif ('卖' in c or '空' in c) and ('增减' in c or '变化' in c):
                    sell_change_col = i

            # 如果找不到明确的买卖列，尝试按位置推断
            if buy_vol_col is None and sell_vol_col is None:
                # 大商所格式：会员简称, 持仓量, 增减, 持仓量, 增减
                # 前半部分是多头，后半部分是空头
                numeric_cols = []
                for i, c in enumerate(cols):
                    if i == name_col:
                        continue
                    try:
                        # 测试是否为数值列
                        test_val = df.iloc[0, i] if len(df) > 0 else None
                        if test_val is not None and pd.notna(test_val):
                            float(test_val)
                            numeric_cols.append(i)
                    except (ValueError, TypeError):
                        continue

                if len(numeric_cols) >= 4:
                    buy_vol_col = numeric_cols[0]
                    buy_change_col = numeric_cols[1]
                    sell_vol_col = numeric_cols[2]
                    sell_change_col = numeric_cols[3]

            # 解析数据
            if name_col is not None:
                for idx, row in df.iterrows():
                    broker = str(row.iloc[name_col]) if pd.notna(row.iloc[name_col]) else ''
                    if not broker or broker == 'nan':
                        continue

                    buy_vol = int(row.iloc[buy_vol_col]) if buy_vol_col is not None and pd.notna(row.iloc[buy_vol_col]) else 0
                    sell_vol = int(row.iloc[sell_vol_col]) if sell_vol_col is not None and pd.notna(row.iloc[sell_vol_col]) else 0
                    buy_chg = int(row.iloc[buy_change_col]) if buy_change_col is not None and pd.notna(row.iloc[buy_change_col]) else 0
                    sell_chg = int(row.iloc[sell_change_col]) if sell_change_col is not None and pd.notna(row.iloc[sell_change_col]) else 0

                    if buy_vol > 0:
                        top_buy.append({
                            'rank': len(top_buy) + 1,
                            'broker': broker,
                            'volume': buy_vol,
                            'change': buy_chg,
                        })
                    if sell_vol > 0:
                        top_sell.append({
                            'rank': len(top_sell) + 1,
                            'broker': broker,
                            'volume': sell_vol,
                            'change': sell_chg,
                        })

            # 按持仓量排序
            top_buy.sort(key=lambda x: x['volume'], reverse=True)
            top_sell.sort(key=lambda x: x['volume'], reverse=True)

            # 重新排名
            for i, item in enumerate(top_buy[:10]):
                item['rank'] = i + 1
            for i, item in enumerate(top_sell[:10]):
                item['rank'] = i + 1

            # 计算集中度
            total_buy = sum(e['volume'] for e in top_buy)
            total_sell = sum(e['volume'] for e in top_sell)
            top5_buy = sum(e['volume'] for e in top_buy[:5])
            top5_sell = sum(e['volume'] for e in top_sell[:5])

            concentration_buy = (top5_buy / total_buy * 100) if total_buy > 0 else 0
            concentration_sell = (top5_sell / total_sell * 100) if total_sell > 0 else 0

            # 生成解读
            parts = []
            if concentration_buy > 60:
                parts.append(f"多头集中度高({concentration_buy:.0f}%)，主力做多意愿强")
            elif concentration_buy > 40:
                parts.append(f"多头集中度适中({concentration_buy:.0f}%)")
            elif concentration_buy > 0:
                parts.append(f"多头分散({concentration_buy:.0f}%)")

            if concentration_sell > 60:
                parts.append(f"空头集中度高({concentration_sell:.0f}%)，主力做空意愿强")
            elif concentration_sell > 40:
                parts.append(f"空头集中度适中({concentration_sell:.0f}%)")
            elif concentration_sell > 0:
                parts.append(f"空头分散({concentration_sell:.0f}%)")

            # 净多空判断
            if total_buy > 0 and total_sell > 0:
                net = total_buy - total_sell
                if net > total_buy * 0.1:
                    parts.append("净多头占优")
                elif net < -total_sell * 0.1:
                    parts.append("净空头占优")
                else:
                    parts.append("多空均衡")

            return {
                'symbol': variety,
                'date': f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
                'exchange': exchange,
                'top_buy': top_buy[:10],
                'top_sell': top_sell[:10],
                'net_buy': total_buy,
                'net_sell': total_sell,
                'concentration_buy': round(concentration_buy, 1),
                'concentration_sell': round(concentration_sell, 1),
                'interpretation': "；".join(parts) if parts else "数据有限",
            }

        except Exception as e:
            logger.debug(f"AkShare get_top_list 异常: {e}")
            return None
            logger.debug(f"AkShare get_top_list 异常: {e}")
            return None

    def get_margin(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取保证金数据

        返回:
            {
                'symbol': str,
                'exchange_margin_ratio': float,  # 交易所保证金比例(%)
                'broker_margin_ratio': float,    # 经纪商保证金比例(%)
                'margin_per_lot': float,          # 每手保证金(元)
                'contract_multiplier': int,       # 合约乘数
                'date': str,
            }
        """
        try:
            import akshare as ak
            variety = normalize_symbol(symbol)

            # 使用 futures_fees_info() 获取保证金和手续费数据
            df = ak.futures_fees_info()
            if df is not None and len(df) > 0:
                # 过滤当前品种（按品种代码或品种名称）
                variety_row = df[
                    (df['品种代码'] == variety) |
                    (df['品种名称'].str.contains(AKSHARE_FUTURES_MAP.get(variety, variety), case=False, na=False))
                ]
                if len(variety_row) > 0:
                    row = variety_row.iloc[0]
                    # 提取保证金比例
                    exchange_margin = float(row.get('做多保证金率', 0) or 0) * 100
                    broker_margin = exchange_margin * 1.05  # 经纪商通常加收5%
                    margin_per_lot = float(row.get('做多1手保证金', 0) or 0)
                    contract_multiplier = int(row.get('合约乘数', 0) or 0)

                    return {
                        'symbol': variety,
                        'exchange_margin_ratio': round(exchange_margin, 2),
                        'broker_margin_ratio': round(broker_margin, 2),
                        'margin_per_lot': round(margin_per_lot, 2),
                        'contract_multiplier': contract_multiplier,
                        'date': datetime.now().strftime('%Y-%m-%d'),
                    }

            return None

        except Exception as e:
            logger.debug(f"AkShare get_margin 异常: {e}")
            return None
            logger.debug(f"AkShare get_margin 异常: {e}")
            return None

    def get_macro(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取宏观经济数据（GDP、CPI、PMI、利率等）

        返回:
            {
                'symbol': str,
                'indicators': Dict[str, Any],  # {指标名: 值}
                'gdp_growth': float,           # GDP同比增速(%)
                'cpi_yoy': float,              # CPI同比(%)
                'pmi': float,                  # 制造业PMI
                'interest_rate': float,        # 基准利率(%)
                'date': str,
                'interpretation': str,
                'commodity_specific': Dict,    # 品种特定宏观关联
            }
        """
        try:
            import akshare as ak
            variety = normalize_symbol(symbol)
            indicators = {}

            # 品种-宏观指标关联映射
            COMMODITY_MACRO_MAP = {
                # 黑色系 - 关联房地产/基建
                'RB': {'sector': 'black', 'macro_focus': ['PMI', '房地产投资', '基建投资'], 'interpretation_prefix': '黑色系'},
                'HC': {'sector': 'black', 'macro_focus': ['PMI', '房地产投资'], 'interpretation_prefix': '黑色系'},
                'I': {'sector': 'black', 'macro_focus': ['PMI', '粗钢产量'], 'interpretation_prefix': '黑色系'},
                'J': {'sector': 'black', 'macro_focus': ['PMI', '焦化开工率'], 'interpretation_prefix': '黑色系'},
                'JM': {'sector': 'black', 'macro_focus': ['PMI', '焦化开工率'], 'interpretation_prefix': '黑色系'},
                # 有色金属 - 关联全球制造业
                'CU': {'sector': 'nonferrous', 'macro_focus': ['PMI', '全球制造业'], 'interpretation_prefix': '有色金属'},
                'AL': {'sector': 'nonferrous', 'macro_focus': ['PMI', '电力成本'], 'interpretation_prefix': '有色金属'},
                'ZN': {'sector': 'nonferrous', 'macro_focus': ['PMI', '镀锌需求'], 'interpretation_prefix': '有色金属'},
                'NI': {'sector': 'nonferrous', 'macro_focus': ['PMI', '不锈钢需求'], 'interpretation_prefix': '有色金属'},
                # 能源化工 - 关联原油/通胀
                'SC': {'sector': 'energy', 'macro_focus': ['原油价格', '通胀'], 'interpretation_prefix': '能源'},
                'FU': {'sector': 'energy', 'macro_focus': ['原油价格', '航运需求'], 'interpretation_prefix': '能源'},
                'BU': {'sector': 'energy', 'macro_focus': ['原油价格', '基建需求'], 'interpretation_prefix': '能源'},
                'RU': {'sector': 'energy', 'macro_focus': ['汽车产销', '轮胎需求'], 'interpretation_prefix': '化工'},
                'TA': {'sector': 'chemical', 'macro_focus': ['纺织需求', 'PTA开工率'], 'interpretation_prefix': '化工'},
                'MA': {'sector': 'chemical', 'macro_focus': ['煤化工', '甲醇开工率'], 'interpretation_prefix': '化工'},
                # 农产品 - 关联通胀/天气
                'M': {'sector': 'agriculture', 'macro_focus': ['CPI', '大豆压榨'], 'interpretation_prefix': '农产品'},
                'Y': {'sector': 'agriculture', 'macro_focus': ['CPI', '油脂需求'], 'interpretation_prefix': '农产品'},
                'P': {'sector': 'agriculture', 'macro_focus': ['CPI', '棕榈油产量'], 'interpretation_prefix': '农产品'},
                'C': {'sector': 'agriculture', 'macro_focus': ['CPI', '饲料需求'], 'interpretation_prefix': '农产品'},
                'CF': {'sector': 'agriculture', 'macro_focus': ['纺织需求', '棉花库存'], 'interpretation_prefix': '农产品'},
                'SR': {'sector': 'agriculture', 'macro_focus': ['CPI', '白糖产量'], 'interpretation_prefix': '农产品'},
                # 贵金属 - 关联避险/通胀
                'AU': {'sector': 'precious', 'macro_focus': ['避险需求', '实际利率'], 'interpretation_prefix': '贵金属'},
                'AG': {'sector': 'precious', 'macro_focus': ['避险需求', '工业需求'], 'interpretation_prefix': '贵金属'},
            }

            commodity_info = COMMODITY_MACRO_MAP.get(variety, {'sector': 'other', 'macro_focus': [], 'interpretation_prefix': '品种'})

            # GDP
            try:
                gdp_df = ak.macro_china_gdp()
                if gdp_df is not None and len(gdp_df) > 0:
                    latest = gdp_df.iloc[0]  # 最新数据在第一行
                    for col in gdp_df.columns:
                        if '同比' in str(col) or '增速' in str(col):
                            indicators['gdp_growth'] = float(latest[col]) if pd.notna(latest[col]) else None
                            break
            except Exception:
                pass

            # CPI
            try:
                cpi_df = ak.macro_china_cpi_yearly()
                if cpi_df is not None and len(cpi_df) > 0:
                    latest = cpi_df.iloc[-1]
                    indicators['cpi_yoy'] = float(latest.get('今值', None)) if pd.notna(latest.get('今值', None)) else None
            except Exception:
                pass

            # PMI
            try:
                pmi_df = ak.macro_china_pmi()
                if pmi_df is not None and len(pmi_df) > 0:
                    latest = pmi_df.iloc[0]  # 最新数据在第一行
                    indicators['pmi'] = float(latest.get('制造业-指数', None)) if pd.notna(latest.get('制造业-指数', None)) else None
            except Exception:
                pass

            if not indicators:
                return None

            # 品种特定解读
            pmi = indicators.get('pmi')
            gdp = indicators.get('gdp_growth')
            cpi = indicators.get('cpi_yoy')
            parts = []

            # 通用解读
            if pmi is not None:
                if pmi > 50:
                    parts.append(f"PMI={pmi:.1f}，制造业扩张")
                else:
                    parts.append(f"PMI={pmi:.1f}，制造业收缩")
            if gdp is not None:
                if gdp > 5:
                    parts.append(f"GDP增速{gdp:.1f}%，经济较强")
                elif gdp > 0:
                    parts.append(f"GDP增速{gdp:.1f}%，经济温和增长")
                else:
                    parts.append(f"GDP增速{gdp:.1f}%，经济衰退风险")

            # 品种特定解读
            prefix = commodity_info['interpretation_prefix']
            if commodity_info['sector'] == 'black':
                if pmi is not None and pmi > 50:
                    parts.append(f"{prefix}板块：PMI扩张利好需求")
                elif pmi is not None and pmi < 49:
                    parts.append(f"{prefix}板块：PMI收缩利空需求")
            elif commodity_info['sector'] == 'energy':
                parts.append(f"{prefix}板块：关注原油价格和通胀走势")
            elif commodity_info['sector'] == 'agriculture':
                if cpi is not None and cpi > 2:
                    parts.append(f"{prefix}板块：CPI偏高，通胀支撑价格")
                elif cpi is not None and cpi < 0:
                    parts.append(f"{prefix}板块：CPI为负，通缩压力")
            elif commodity_info['sector'] == 'precious':
                parts.append(f"{prefix}板块：关注实际利率和避险情绪")

            return {
                'symbol': variety,
                'indicators': indicators,
                'gdp_growth': indicators.get('gdp_growth'),
                'cpi_yoy': indicators.get('cpi_yoy'),
                'pmi': indicators.get('pmi'),
                'interest_rate': indicators.get('interest_rate'),
                'date': datetime.now().strftime('%Y-%m-%d'),
                'interpretation': "；".join(parts) if parts else "数据有限",
                'commodity_specific': commodity_info,
            }

        except Exception as e:
            logger.debug(f"AkShare get_macro 异常: {e}")
            return None

    def get_delivery(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取交割数据（交割月、交割量、仓单注册量）

        返回:
            {
                'symbol': str,
                'delivery_month': str,           # 交割月份
                'next_delivery_date': str,       # 下次交割日
                'registered_warrants': int,      # 注册仓单量
                'delivery_volume': int,          # 交割量
                'days_to_delivery': int,         # 距离交割天数
                'interpretation': str,
            }
        """
        try:
            import akshare as ak
            variety = normalize_symbol(symbol)
            cn_name = AKSHARE_FUTURES_MAP.get(variety)
            if not cn_name:
                return None

            # 计算交割月（商品期货通常在1/5/9月或合约月份交割）
            now = datetime.now()
            delivery_months = [1, 5, 9]  # 黑色系、农产品等常见交割月
            if variety in ['CU', 'AL', 'ZN', 'PB', 'NI', 'SN']:  # 有色系
                delivery_months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

            # 找到最近的交割月
            next_delivery = None
            for month in delivery_months:
                if month > now.month:
                    next_delivery = datetime(now.year, month, 15)  # 通常月中交割
                    break
            if next_delivery is None:
                next_delivery = datetime(now.year + 1, delivery_months[0], 15)

            days_to_delivery = (next_delivery - now).days

            # 获取仓单数据
            registered_warrants = 0
            try:
                inv = self.get_inventory(symbol)
                if inv:
                    registered_warrants = inv.get('warehouse_receipts', 0)
            except Exception:
                pass

            interpretation = ""
            if days_to_delivery <= 30:
                interpretation = f"距交割月{days_to_delivery}天，注意移仓换月风险"
            elif days_to_delivery <= 60:
                interpretation = f"距交割月{days_to_delivery}天，关注交割逻辑"
            else:
                interpretation = f"距交割月{days_to_delivery}天，交割因素影响较小"

            return {
                'symbol': variety,
                'delivery_month': next_delivery.strftime('%Y-%m'),
                'next_delivery_date': next_delivery.strftime('%Y-%m-%d'),
                'registered_warrants': registered_warrants,
                'delivery_volume': 0,
                'days_to_delivery': days_to_delivery,
                'interpretation': interpretation,
            }

        except Exception as e:
            logger.debug(f"AkShare get_delivery 异常: {e}")
            return None


# ---------------------------------------------------------------------------
# UnifiedDataRouter — 统一数据路由器
# ---------------------------------------------------------------------------

class UnifiedDataRouter:
    """统一期货数据路由器

    特性：
    - 单一入口：所有数据请求通过此类
    - 智能路由：按数据类型使用不同优先级链
    - 自动 Fallback：逐级降级直到获取到数据
    - 配置驱动：优先级可从 config.json 加载
    - 时效性检查：数据过期自动触发刷新
    - 回写缓存：远程数据自动回写本地 DuckDB
    """

    def __init__(self, config_path: Optional[str] = None, db_dir: str = "data"):
        self._db_dir = db_dir
        self._routing = dict(DEFAULT_ROUTING)
        self._staleness_threshold = dict(DEFAULT_STALENESS_THRESHOLD)
        self._sources: Dict[str, Any] = {}  # 缓存各数据源实例
        self._config_path = config_path

        # 加载配置
        if config_path and os.path.exists(config_path):
            self._load_config(config_path)

    def _load_config(self, config_path: str):
        """从 config.json 加载路由配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)

            data_routing = cfg.get('data_routing', {})
            if data_routing:
                # 合并路由优先级
                for dtype, priorities in data_routing.get('priorities', {}).items():
                    self._routing[dtype] = priorities

                # 合并时效性阈值
                for dtype, hours in data_routing.get('staleness_threshold', {}).items():
                    self._staleness_threshold[dtype] = hours

                # 加载数据库路径
                if 'db_dir' in data_routing:
                    self._db_dir = data_routing['db_dir']

            logger.info(f"数据路由配置已加载: {data_routing}")

        except Exception as e:
            logger.warning(f"加载路由配置失败，使用默认值: {e}")

    # ---- 数据源获取（延迟初始化） ----

    def _get_source(self, source_name: str) -> Optional[Any]:
        """获取数据源实例（延迟初始化 + 缓存）"""
        if source_name in self._sources:
            return self._sources[source_name]

        source = None
        try:
            if source_name == "duckdb":
                from trend_scanner.storage.data_sync import DataSyncManager
                sqlite_path = os.path.join(self._db_dir, 'meta.db')
                duckdb_path = os.path.join(self._db_dir, 'market.db')
                source = DataSyncManager(sqlite_path=sqlite_path, duckdb_path=duckdb_path)

            elif source_name == "tqsdk":
                from trend_scanner.tqsdk_bridge import TqSdkBridge
                source = TqSdkBridge()

            elif source_name == "pytdx":
                source = PytdxSource()

            elif source_name == "akshare":
                source = AkShareSource()

            elif source_name == "csv":
                from trend_scanner.data_source import CsvSource
                source = CsvSource(data_dir=self._db_dir)

        except Exception as e:
            logger.debug(f"初始化数据源 {source_name} 失败: {e}")

        if source is not None:
            self._sources[source_name] = source
        return source

    def _try_source(self, source_name: str, method: str, **kwargs) -> Optional[Any]:
        """尝试从单个数据源获取数据

        参数:
            source_name: 数据源名称
            method: 方法名 ('get_kline', 'get_quote', 'get_basis', 等)
            **kwargs: 方法参数

        返回:
            数据结果（DataFrame/Dict）或 None
        """
        source = self._get_source(source_name)
        if source is None:
            return None

        # 检查数据源可用性
        if hasattr(source, 'is_available') and callable(source.is_available):
            if not source.is_available():
                return None
        # DuckDB (DataSyncManager) 无 is_available，检查鸭子类型方式
        if source_name == "duckdb":
            try:
                stats = source.get_statistics()
                if not stats or not stats.get('sqlite', {}).get('total_symbols', 0):
                    return None
            except Exception:
                return None

        # 调用对应方法
        handler = getattr(source, method, None)
        if handler is None:
            # DuckDB 路由: get_kline 方法在 DataSyncManager 上
            if source_name == "duckdb" and method == "get_kline":
                return source.get_kline(
                    kwargs.get('symbol'),
                    days=kwargs.get('days', 120),
                    timeframe=kwargs.get('period', 'daily'),
                    allow_tqsdk_fallback=False,  # 路由层自己管 fallback
                )
            elif source_name == "duckdb" and method == "get_quote":
                # DuckDB 没有 get_quote，从 SQLite 获取
                quote = source.sqlite.get_symbol(kwargs.get('symbol'))
                if quote:
                    return {
                        'symbol': quote.get('symbol', kwargs.get('symbol')),
                        'last_price': quote.get('last_price', 0),
                        'open_interest': quote.get('open_interest', 0),
                        'volume': quote.get('volume', 0),
                    }
                return None
            return None

        # 调用方法
        try:
            return handler(**kwargs)
        except Exception as e:
            logger.debug(f"数据源 {source_name}.{method} 调用失败: {e}")
            return None

    # ---- 公开 API ----

    def get_kline(self, symbol: str, days: int = 120, period: str = "daily") -> DataResponse:
        """获取K线数据（智能路由）

        优先级: DuckDB → TqSdk → Pytdx → CSV
        """
        variety = normalize_symbol(symbol)
        ts = datetime.now().isoformat()

        # 时效性检查
        staleness = self._check_staleness(variety, 'kline')

        for i, source_name in enumerate(self._routing.get('kline', DEFAULT_ROUTING['kline'])):
            result = self._try_source(
                source_name, 'get_kline',
                symbol=variety, days=days, period=period,
            )

            if result is not None:
                count = len(result) if isinstance(result, pd.DataFrame) else 0
                # 远程数据回写本地缓存
                if source_name in ('tqsdk', 'pytdx') and isinstance(result, pd.DataFrame):
                    self._cache_kline(variety, result, period, source_name)

                return DataResponse(
                    ok=True,
                    source=source_name,
                    fallback_used=(i > 0),
                    data_type='kline',
                    count=count,
                    data=result,
                    error=None,
                    timestamp=ts,
                    staleness_hours=staleness if source_name == 'duckdb' else 0.0,
                )

        return DataResponse(
            ok=False, source="", fallback_used=False, data_type='kline',
            count=0, data=None, error="所有数据源均无法获取K线数据", timestamp=ts,
            staleness_hours=staleness,
        )

    def get_quote(self, symbol: str) -> DataResponse:
        """获取实时行情（智能路由）

        优先级: DuckDB → TqSdk → Pytdx
        """
        variety = normalize_symbol(symbol)
        ts = datetime.now().isoformat()

        staleness = self._check_staleness(variety, 'quote')

        for i, source_name in enumerate(self._routing.get('quote', DEFAULT_ROUTING['quote'])):
            result = self._try_source(source_name, 'get_quote', symbol=variety)

            if result is not None:
                # 远程数据回写本地
                if source_name in ('tqsdk', 'pytdx'):
                    self._cache_quote(variety, result, source_name)

                return DataResponse(
                    ok=True, source=source_name, fallback_used=(i > 0),
                    data_type='quote', count=1, data=result, error=None,
                    timestamp=ts, staleness_hours=staleness if source_name == 'duckdb' else 0.0,
                )

        return DataResponse(
            ok=False, source="", fallback_used=False, data_type='quote',
            count=0, data=None, error="所有数据源均无法获取行情数据", timestamp=ts,
            staleness_hours=staleness,
        )

    def get_basis(self, symbol: str) -> DataResponse:
        """获取基差数据 [新增]

        优先级: AkShare → Pytdx
        """
        variety = normalize_symbol(symbol)
        ts = datetime.now().isoformat()

        staleness = self._check_staleness(variety, 'basis')

        for i, source_name in enumerate(self._routing.get('basis', DEFAULT_ROUTING['basis'])):
            result = self._try_source(source_name, 'get_basis', symbol=variety)

            if result is not None:
                return DataResponse(
                    ok=True, source=source_name, fallback_used=(i > 0),
                    data_type='basis', count=1, data=result, error=None,
                    timestamp=ts, staleness_hours=staleness,
                )

        return DataResponse(
            ok=False, source="", fallback_used=False, data_type='basis',
            count=0, data=None, error="无法获取基差数据（AkShare/Pytdx 均不可用）",
            timestamp=ts, staleness_hours=staleness,
        )

    def get_seasonality(self, symbol: str, years: int = 5) -> DataResponse:
        """获取季节性规律数据 [新增]

        优先级: AkShare → CSV
        """
        variety = normalize_symbol(symbol)
        ts = datetime.now().isoformat()

        staleness = self._check_staleness(variety, 'seasonality')

        for i, source_name in enumerate(self._routing.get('seasonality', DEFAULT_ROUTING['seasonality'])):
            result = self._try_source(source_name, 'get_seasonality', symbol=variety, years=years)

            if result is not None:
                return DataResponse(
                    ok=True, source=source_name, fallback_used=(i > 0),
                    data_type='seasonality', count=1, data=result, error=None,
                    timestamp=ts, staleness_hours=staleness,
                )

        return DataResponse(
            ok=False, source="", fallback_used=False, data_type='seasonality',
            count=0, data=None, error="无法获取季节性数据", timestamp=ts,
            staleness_hours=staleness,
        )

    def get_inventory(self, symbol: str) -> DataResponse:
        """获取仓单数据 [新增]

        优先级: AkShare
        """
        variety = normalize_symbol(symbol)
        ts = datetime.now().isoformat()

        staleness = self._check_staleness(variety, 'inventory')

        for i, source_name in enumerate(self._routing.get('inventory', DEFAULT_ROUTING['inventory'])):
            result = self._try_source(source_name, 'get_inventory', symbol=variety)

            if result is not None:
                return DataResponse(
                    ok=True, source=source_name, fallback_used=(i > 0),
                    data_type='inventory', count=1, data=result, error=None,
                    timestamp=ts, staleness_hours=staleness,
                )

        return DataResponse(
            ok=False, source="", fallback_used=False, data_type='inventory',
            count=0, data=None, error="无法获取仓单数据", timestamp=ts,
            staleness_hours=staleness,
        )

    def get_top_list(self, symbol: str) -> DataResponse:
        """获取龙虎榜数据 [新增]

        优先级: AkShare
        """
        variety = normalize_symbol(symbol)
        ts = datetime.now().isoformat()
        staleness = self._check_staleness(variety, 'top_list')

        for i, source_name in enumerate(self._routing.get('top_list', DEFAULT_ROUTING['top_list'])):
            result = self._try_source(source_name, 'get_top_list', symbol=variety)
            if result is not None:
                return DataResponse(
                    ok=True, source=source_name, fallback_used=(i > 0),
                    data_type='top_list', count=1, data=result, error=None,
                    timestamp=ts, staleness_hours=staleness,
                )

        return DataResponse(
            ok=False, source="", fallback_used=False, data_type='top_list',
            count=0, data=None, error="无法获取龙虎榜数据", timestamp=ts,
            staleness_hours=staleness,
        )

    def get_margin(self, symbol: str) -> DataResponse:
        """获取保证金数据 [新增]

        优先级: AkShare
        """
        variety = normalize_symbol(symbol)
        ts = datetime.now().isoformat()
        staleness = self._check_staleness(variety, 'margin')

        for i, source_name in enumerate(self._routing.get('margin', DEFAULT_ROUTING['margin'])):
            result = self._try_source(source_name, 'get_margin', symbol=variety)
            if result is not None:
                return DataResponse(
                    ok=True, source=source_name, fallback_used=(i > 0),
                    data_type='margin', count=1, data=result, error=None,
                    timestamp=ts, staleness_hours=staleness,
                )

        return DataResponse(
            ok=False, source="", fallback_used=False, data_type='margin',
            count=0, data=None, error="无法获取保证金数据", timestamp=ts,
            staleness_hours=staleness,
        )

    def get_macro(self, symbol: str) -> DataResponse:
        """获取宏观经济数据 [新增]

        优先级: AkShare
        """
        variety = normalize_symbol(symbol)
        ts = datetime.now().isoformat()
        staleness = self._check_staleness(variety, 'macro')

        for i, source_name in enumerate(self._routing.get('macro', DEFAULT_ROUTING['macro'])):
            result = self._try_source(source_name, 'get_macro', symbol=variety)
            if result is not None:
                return DataResponse(
                    ok=True, source=source_name, fallback_used=(i > 0),
                    data_type='macro', count=1, data=result, error=None,
                    timestamp=ts, staleness_hours=staleness,
                )

        return DataResponse(
            ok=False, source="", fallback_used=False, data_type='macro',
            count=0, data=None, error="无法获取宏观经济数据", timestamp=ts,
            staleness_hours=staleness,
        )

    def get_delivery(self, symbol: str) -> DataResponse:
        """获取交割数据 [新增]

        优先级: AkShare
        """
        variety = normalize_symbol(symbol)
        ts = datetime.now().isoformat()
        staleness = self._check_staleness(variety, 'delivery')

        for i, source_name in enumerate(self._routing.get('delivery', DEFAULT_ROUTING['delivery'])):
            result = self._try_source(source_name, 'get_delivery', symbol=variety)
            if result is not None:
                return DataResponse(
                    ok=True, source=source_name, fallback_used=(i > 0),
                    data_type='delivery', count=1, data=result, error=None,
                    timestamp=ts, staleness_hours=staleness,
                )

        return DataResponse(
            ok=False, source="", fallback_used=False, data_type='delivery',
            count=0, data=None, error="无法获取交割数据", timestamp=ts,
            staleness_hours=staleness,
        )

    # ---- 时效性检查 ----

    def _check_staleness(self, symbol: str, data_type: str) -> float:
        """检查数据时效性

        返回:
            滞后小时数（0 = 实时或无法判断）
        """
        # 从本地 DB 检查最新数据时间
        duckdb = self._get_source('duckdb')
        if duckdb is None:
            return 0.0

        try:
            if data_type == 'kline':
                date_range = duckdb.duckdb.get_kline_date_range(symbol, timeframe='daily')
                if date_range and date_range.get('latest_date'):
                    latest = pd.Timestamp(date_range['latest_date'])
                    now = pd.Timestamp.now()
                    # 如果是交易日下午3点后，今天应该有数据
                    hours = (now - latest).total_seconds() / 3600
                    return max(0, hours)
            elif data_type == 'quote':
                # 从 SQLite 检查行情更新时间
                sqlite = duckdb.sqlite
                symbol_info = sqlite.get_symbol(symbol)
                if symbol_info and symbol_info.get('updated_at'):
                    latest = pd.Timestamp(symbol_info['updated_at'])
                    now = pd.Timestamp.now()
                    hours = (now - latest).total_seconds() / 3600
                    return max(0, hours)
        except Exception as e:
            logger.debug(f"时效性检查失败({symbol}/{data_type}): {e}")

        return 0.0

    def check_data_timeliness(self, symbol: str) -> Dict[str, Any]:
        """公开的时效性检查接口

        返回:
            {
                'symbol': str,
                'kline': {'staleness_hours': float, 'status': str},
                'quote': {'staleness_hours': float, 'status': str},
                'overall_status': str,  # 'fresh' | 'stale' | 'critical'
            }
        """
        variety = normalize_symbol(symbol)
        kline_staleness = self._check_staleness(variety, 'kline')
        quote_staleness = self._check_staleness(variety, 'quote')

        kline_threshold = self._staleness_threshold.get('kline', 4)
        quote_threshold = self._staleness_threshold.get('quote', 0.5)

        def _status(hours, threshold):
            if hours == 0:
                return 'unknown'
            if hours <= threshold:
                return 'fresh'
            if hours <= threshold * 3:
                return 'stale'
            return 'critical'

        max_staleness = max(kline_staleness, quote_staleness)
        overall = 'fresh'
        if max_staleness > max(kline_threshold, quote_threshold) * 3:
            overall = 'critical'
        elif max_staleness > max(kline_threshold, quote_threshold):
            overall = 'stale'

        return {
            'symbol': variety,
            'kline': {
                'staleness_hours': kline_staleness,
                'status': _status(kline_staleness, kline_threshold),
                'threshold_hours': kline_threshold,
            },
            'quote': {
                'staleness_hours': quote_staleness,
                'status': _status(quote_staleness, quote_threshold),
                'threshold_hours': quote_threshold,
            },
            'overall_status': overall,
        }

    def is_data_stale(self, symbol: str, data_type: str = 'kline') -> bool:
        """判断数据是否过期"""
        staleness = self._check_staleness(symbol, data_type)
        threshold = self._staleness_threshold.get(data_type, 4)
        return staleness > threshold

    # ---- 缓存回写 ----

    def _cache_kline(self, symbol: str, df: pd.DataFrame, timeframe: str, source: str):
        """远程 K 线数据回写本地 DuckDB"""
        duckdb_mgr = self._get_source('duckdb')
        if duckdb_mgr is None:
            return
        try:
            duckdb_mgr.duckdb.save_klines(symbol, df, timeframe=timeframe, source=source)
        except Exception as e:
            logger.debug(f"K线缓存回写失败({symbol}): {e}")

    def _cache_quote(self, symbol: str, quote: Dict, source: str):
        """远程行情数据回写本地"""
        duckdb_mgr = self._get_source('duckdb')
        if duckdb_mgr is None:
            return
        try:
            duckdb_mgr.duckdb.save_quote(symbol, quote, source=source)
            duckdb_mgr.sqlite.update_symbol_quote(symbol, quote)
        except Exception as e:
            logger.debug(f"行情缓存回写失败({symbol}): {e}")

    # ---- 路由配置管理 ----

    def get_routing_config(self) -> Dict[str, Any]:
        """获取当前路由配置"""
        return {
            'priorities': dict(self._routing),
            'staleness_threshold': dict(self._staleness_threshold),
            'db_dir': self._db_dir,
        }

    def update_routing(self, data_type: str, priorities: List[str]):
        """动态更新路由优先级

        参数:
            data_type: 数据类型 ('kline', 'quote', 'basis', 等)
            priorities: 优先级列表 (如 ['tqsdk', 'pytdx', 'csv'])
        """
        valid_sources = {'duckdb', 'tqsdk', 'pytdx', 'akshare', 'csv'}
        cleaned = [s for s in priorities if s in valid_sources]
        if cleaned:
            self._routing[data_type] = cleaned
            logger.info(f"路由优先级已更新: {data_type} → {cleaned}")

    def get_available_sources(self) -> Dict[str, bool]:
        """检查所有数据源可用性"""
        result = {}
        for name in ['duckdb', 'tqsdk', 'pytdx', 'akshare', 'csv']:
            source = self._get_source(name)
            if source is not None:
                if hasattr(source, 'is_available') and callable(source.is_available):
                    result[name] = source.is_available()
                elif name == 'duckdb':
                    # DataSyncManager 无 is_available，检查统计信息
                    try:
                        stats = source.get_statistics()
                        result[name] = bool(stats and stats.get('sqlite', {}).get('total_symbols', 0) > 0)
                    except Exception:
                        result[name] = False
                else:
                    result[name] = True  # 有实例但无 is_available，假定可用
            else:
                result[name] = False
        return result

    # ---- 兼容接口 ----

    def get_kline_df(self, symbol: str, days: int = 120, period: str = "daily") -> Optional[pd.DataFrame]:
        """兼容旧接口：返回 DataFrame 或 None"""
        resp = self.get_kline(symbol, days, period)
        return resp.data if resp.ok else None

    def get_quote_dict(self, symbol: str) -> Optional[Dict[str, Any]]:
        """兼容旧接口：返回 Dict 或 None"""
        resp = self.get_quote(symbol)
        return resp.data if resp.ok else None


# ---------------------------------------------------------------------------
# 模块级便捷函数
# ---------------------------------------------------------------------------

_router_instance: Optional[UnifiedDataRouter] = None


def get_router(config_path: Optional[str] = None, db_dir: str = "data") -> UnifiedDataRouter:
    """获取全局路由器实例（单例）"""
    global _router_instance
    if _router_instance is None:
        _router_instance = UnifiedDataRouter(config_path=config_path, db_dir=db_dir)
    return _router_instance


def reset_router():
    """重置路由器（用于测试）"""
    global _router_instance
    _router_instance = None
