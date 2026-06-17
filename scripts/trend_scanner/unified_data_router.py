"""
统一数据路由层

提供单一入口点，按数据类型智能路由到最佳数据源：
- K线：  DuckDB → TqSdk → Pytdx(通达信) → CSV
- 行情：  DuckDB → TqSdk → Pytdx(通达信)
- 基差：  AkShare → Pytdx(通达信)  [新增]
- 季节性： AkShare → 本地CSV       [新增]
- 仓单：  AkShare                  [新增]

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
}

# 数据时效性阈值（小时）
DEFAULT_STALENESS_THRESHOLD = {
    "kline": 4,          # K线允许4小时滞后
    "quote": 0.5,        # 行情30分钟
    "basis": 24,         # 基差允许1天
    "seasonality": 168,  # 季节性允许1周
    "inventory": 24,     # 仓单允许1天
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
            cn_name = AKSHARE_FUTURES_MAP.get(variety)
            if not cn_name:
                return None

            # 尝试获取基差数据
            # AkShare 基差接口: ak.futures_basis_spread()
            try:
                df = ak.futures_basis_spread(symbol=cn_name)
                if df is not None and len(df) > 0:
                    latest = df.iloc[-1]
                    spot = float(latest.get('现货价格', 0) or latest.get('现货', 0) or 0)
                    futures = float(latest.get('期货价格', 0) or latest.get('期货', 0) or 0)
                    basis = spot - futures
                    basis_rate = basis / spot * 100 if spot > 0 else 0
                    return {
                        'symbol': variety,
                        'spot_price': spot,
                        'futures_price': futures,
                        'basis': basis,
                        'basis_rate': round(basis_rate, 2),
                        'date': str(latest.name) if hasattr(latest, 'name') else datetime.now().strftime('%Y-%m-%d'),
                    }
            except Exception:
                pass

            # 备选: 手动获取现货和期货价格计算基差
            try:
                # 获取期货主力合约价格
                spot_df = ak.futures_spot_price(symbol=cn_name)
                futures_df = ak.futures_main_sina(symbol=cn_name)

                if spot_df is not None and futures_df is not None:
                    spot_price = float(spot_df.iloc[-1].get('价格', 0) or spot_df.iloc[-1].iloc[-1] or 0)
                    futures_price = float(futures_df.iloc[-1].get('收盘价', 0) or futures_df.iloc[-1].iloc[-1] or 0)

                    if spot_price > 0 and futures_price > 0:
                        basis = spot_price - futures_price
                        basis_rate = basis / spot_price * 100
                        return {
                            'symbol': variety,
                            'spot_price': spot_price,
                            'futures_price': futures_price,
                            'basis': round(basis, 2),
                            'basis_rate': round(basis_rate, 2),
                            'date': datetime.now().strftime('%Y-%m-%d'),
                        }
            except Exception as e:
                logger.debug(f"AkShare 基差获取失败({variety}): {e}")

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
