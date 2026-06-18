"""
数据源适配器模块

提供统一的数据获取接口，支持多种数据源：
- TqSdk（首选）：期货实时行情、历史K线
- 通达信 MCP（备选）：A股/港股/美股数据
- 本地 CSV（兜底）：用户导入的历史数据

使用方式：
    from trend_scanner.data_source import DataSourceFactory

    # 自动选择数据源
    ds = DataSourceFactory.create()
    df = ds.get_kline("RB", days=120)

    # 指定 TqSdk
    ds = DataSourceFactory.create(source="tqsdk")
    df = ds.get_kline("RB", days=120)
"""

import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import pandas as pd


class DataSource(ABC):
    """数据源基类"""

    @abstractmethod
    def get_kline(self, symbol: str, days: int = 120, period: str = "daily", **kwargs) -> pd.DataFrame | None:
        """
        获取K线数据

        参数:
            symbol: 品种代码（如 "RB", "I", "AU"）
            days: 获取天数
            period: 周期（daily/1h/15m 等）

        返回:
            DataFrame，包含 date, open, high, low, close, volume, open_interest 列
        """
        pass

    @abstractmethod
    def get_quote(self, symbol: str) -> dict[str, Any] | None:
        """
        获取实时行情

        参数:
            symbol: 品种代码

        返回:
            行情字典，包含 last_price, open_interest, volume 等
        """
        pass

    @abstractmethod
    def get_main_contracts(self, exchange: str = None) -> list[str]:
        """
        获取主力合约列表

        参数:
            exchange: 交易所（SHFE/DCE/CZCE/CFFEX/INE），None表示全部

        返回:
            主力合约代码列表
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查数据源是否可用"""
        pass


class TqSdkSource(DataSource):
    """TqSdk 数据源（使用桥接器解决 sys.exit 问题）"""

    # 主力合约映射
    MAIN_CONTRACT_MAP = {
        # 黑色系
        "RB": "KQ.m@SHFE.rb",
        "HC": "KQ.m@SHFE.hc",
        "I": "KQ.m@DCE.i",
        "J": "KQ.m@DCE.j",
        "JM": "KQ.m@DCE.jm",
        "SF": "KQ.m@CZCE.SF",
        "SM": "KQ.m@CZCE.SM",
        # 有色金属
        "CU": "KQ.m@SHFE.cu",
        "AL": "KQ.m@SHFE.al",
        "ZN": "KQ.m@SHFE.zn",
        "PB": "KQ.m@SHFE.pb",
        "NI": "KQ.m@SHFE.ni",
        "SN": "KQ.m@SHFE.sn",
        # 能源化工
        "SC": "KQ.m@INE.sc",
        "FU": "KQ.m@SHFE.fu",
        "BU": "KQ.m@SHFE.bu",
        "RU": "KQ.m@SHFE.ru",
        "TA": "KQ.m@CZCE.TA",
        "MA": "KQ.m@CZCE.MA",
        "SA": "KQ.m@CZCE.SA",
        "FG": "KQ.m@CZCE.FG",
        "EG": "KQ.m@DCE.EG",
        "EB": "KQ.m@DCE.EB",
        "PP": "KQ.m@DCE.pp",
        "V": "KQ.m@DCE.v",
        "L": "KQ.m@DCE.l",
        # 农产品
        "CF": "KQ.m@CZCE.CF",
        "SR": "KQ.m@CZCE.SR",
        "AP": "KQ.m@CZCE.AP",
        "RM": "KQ.m@CZCE.RM",
        "OI": "KQ.m@CZCE.OI",
        "M": "KQ.m@DCE.m",
        "Y": "KQ.m@DCE.y",
        "P": "KQ.m@DCE.p",
        "C": "KQ.m@DCE.c",
        "CS": "KQ.m@DCE.cs",
        "A": "KQ.m@DCE.a",
        "B": "KQ.m@DCE.b",
        "JD": "KQ.m@DCE.jd",
        "LH": "KQ.m@DCE.lh",
        # 贵金属
        "AU": "KQ.m@SHFE.au",
        "AG": "KQ.m@SHFE.ag",
        # 中金所 - 股指期货
        "IF": "KQ.m@CFFEX.if",
        "IC": "KQ.m@CFFEX.ic",
        "IH": "KQ.m@CFFEX.ih",
        "IM": "KQ.m@CFFEX.im",
        # 中金所 - 国债期货
        "T": "KQ.m@CFFEX.t",
        "TF": "KQ.m@CFFEX.tf",
        "TL": "KQ.m@CFFEX.tl",
        "TS": "KQ.m@CFFEX.ts",
        # 上期所 - 补充品种
        "AO": "KQ.m@SHFE.ao",
        "BR": "KQ.m@SHFE.br",
        "SP": "KQ.m@SHFE.sp",
        "SS": "KQ.m@SHFE.ss",
        "WR": "KQ.m@SHFE.wr",
        "AD": "KQ.m@SHFE.ad",
        "OP": "KQ.m@SHFE.op",
        # 上期能源 - 补充品种
        "BC": "KQ.m@INE.bc",
        "EC": "KQ.m@INE.ec",
        "LU": "KQ.m@INE.lu",
        "NR": "KQ.m@INE.nr",
        # 大商所 - 补充品种
        "BB": "KQ.m@DCE.bb",
        "BZ": "KQ.m@DCE.bz",
        "FB": "KQ.m@DCE.fb",
        "LF": "KQ.m@DCE.lf",
        "LG": "KQ.m@DCE.lg",
        "PG": "KQ.m@DCE.pg",
        "PPF": "KQ.m@DCE.ppf",
        "RR": "KQ.m@DCE.rr",
        "VF": "KQ.m@DCE.vf",
        # 郑商所 - 补充品种
        "CJ": "KQ.m@CZCE.CJ",
        "CY": "KQ.m@CZCE.CY",
        "JR": "KQ.m@CZCE.JR",
        "LR": "KQ.m@CZCE.LR",
        "PF": "KQ.m@CZCE.PF",
        "PK": "KQ.m@CZCE.PK",
        "PL": "KQ.m@CZCE.PL",
        "PM": "KQ.m@CZCE.PM",
        "PR": "KQ.m@CZCE.PR",
        "PX": "KQ.m@CZCE.PX",
        "RI": "KQ.m@CZCE.RI",
        "RS": "KQ.m@CZCE.RS",
        "SH": "KQ.m@CZCE.SH",
        "UR": "KQ.m@CZCE.UR",
        "WH": "KQ.m@CZCE.WH",
        "ZC": "KQ.m@CZCE.ZC",
    }

    def __init__(self):
        self._bridge = None
        self._initialize()

    def _initialize(self):
        """初始化 TqSdk 桥接器"""
        try:
            from .tqsdk_bridge import TqSdkBridge

            self._bridge = TqSdkBridge()
        except ImportError:
            pass

    def is_available(self) -> bool:
        """检查 TqSdk 是否可用"""
        if self._bridge is None:
            return False
        return self._bridge.is_available()

    def get_kline(self, symbol: str, days: int = 120, period: str = "daily", **kwargs) -> pd.DataFrame | None:
        """获取K线数据（使用桥接器）"""
        if not self.is_available():
            return None

        try:
            return self._bridge.get_kline(symbol, days, period)
        except Exception as e:
            print(f"[错误] TqSdk 获取K线失败: {e}", flush=True)
            return None

    def get_quote(self, symbol: str) -> dict[str, Any] | None:
        """获取实时行情（使用桥接器）"""
        if not self.is_available():
            return None

        try:
            return self._bridge.get_quote(symbol)
        except Exception as e:
            print(f"[错误] TqSdk 获取行情失败: {e}", flush=True)
            return None

    def get_main_contracts(self, exchange: str = None) -> list[str]:
        """获取主力合约列表"""
        if exchange:
            return [v for k, v in self.MAIN_CONTRACT_MAP.items() if exchange.upper() in v]
        return list(self.MAIN_CONTRACT_MAP.values())

    def get_active_symbols(self, min_oi: int = 10000) -> dict[str, dict]:
        """
        获取活跃品种（持仓量大于阈值）

        参数:
            min_oi: 最小持仓量

        返回:
            {symbol: {name, last_price, open_interest, volume}}
        """
        if not self.is_available():
            return {}

        try:
            from tqsdk import TqApi

            active_symbols = {}

            with TqApi(auth=self._auth) as api:
                # 获取主要品种的行情
                quotes = {}
                for symbol, tq_symbol in list(self.MAIN_CONTRACT_MAP.items())[:20]:  # 限制数量
                    try:
                        quotes[symbol] = api.get_quote(tq_symbol)
                    except:
                        continue

                # 等待数据更新
                api.wait_update()

                # 筛选活跃品种
                for symbol, quote in quotes.items():
                    try:
                        oi = getattr(quote, "open_interest", 0) or 0
                        if oi >= min_oi:
                            active_symbols[symbol] = {
                                "name": symbol,
                                "last_price": getattr(quote, "last_price", 0),
                                "open_interest": oi,
                                "volume": getattr(quote, "volume", 0),
                            }
                    except:
                        continue

            return active_symbols

        except Exception as e:
            print(f"TqSdk 获取活跃品种失败: {e}")
            return {}


class CsvSource(DataSource):
    """本地CSV数据源"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir

    def is_available(self) -> bool:
        """检查数据目录是否存在"""
        return os.path.exists(self.data_dir)

    def get_kline(self, symbol: str, days: int = 120, period: str = "daily") -> pd.DataFrame | None:
        """从CSV文件获取K线数据"""
        try:
            # 尝试不同的文件名格式
            possible_files = [
                f"{symbol.upper()}.csv",
                f"{symbol.lower()}.csv",
                f"{symbol}_daily.csv",
                f"{symbol}_{period}.csv",
            ]

            for filename in possible_files:
                filepath = os.path.join(self.data_dir, filename)
                if os.path.exists(filepath):
                    df = pd.read_csv(filepath)

                    # 标准化列名
                    df.columns = [c.lower() for c in df.columns]

                    # 确保必要的列存在
                    required_cols = ["date", "open", "high", "low", "close", "volume"]
                    if all(col in df.columns for col in required_cols):
                        # 转换日期格式
                        df["date"] = pd.to_datetime(df["date"])

                        # 只保留最近N天的数据
                        if len(df) > days:
                            df = df.tail(days)

                        return df

            return None

        except Exception as e:
            print(f"读取CSV失败: {e}")
            return None

    def get_quote(self, symbol: str) -> dict[str, Any] | None:
        """从最新K线获取行情"""
        df = self.get_kline(symbol, days=1)
        if df is not None and len(df) > 0:
            latest = df.iloc[-1]
            return {
                "symbol": symbol,
                "last_price": latest.get("close", 0),
                "open_interest": latest.get("open_interest", 0),
                "volume": latest.get("volume", 0),
            }
        return None

    def get_main_contracts(self, exchange: str = None) -> list[str]:
        """获取数据目录中的所有品种"""
        if not self.is_available():
            return []

        symbols = []
        for filename in os.listdir(self.data_dir):
            if filename.endswith(".csv"):
                symbol = filename.replace(".csv", "").split("_")[0]
                symbols.append(symbol.upper())

        return symbols


class LocalDBSource(DataSource):
    """本地数据库数据源（SQLite + DuckDB）"""

    def __init__(self, db_dir: str = "data"):
        """
        初始化本地数据库数据源

        Args:
            db_dir: 数据库目录
        """
        self.db_dir = db_dir
        self._sync_manager = None

    @property
    def sync_manager(self):
        """延迟初始化同步管理器"""
        if self._sync_manager is None:
            from trend_scanner.storage.data_sync import DataSyncManager

            sqlite_path = os.path.join(self.db_dir, "meta.db")
            duckdb_path = os.path.join(self.db_dir, "market.db")
            self._sync_manager = DataSyncManager(sqlite_path=sqlite_path, duckdb_path=duckdb_path)
        return self._sync_manager

    def get_kline(self, symbol: str, days: int = 120, period: str = "daily", **kwargs) -> pd.DataFrame | None:
        """
        获取K线数据（优先从本地DB，其次从TqSdk）

        Args:
            symbol: 品种代码
            days: 获取天数
            period: 周期
            **kwargs: allow_tqsdk_fallback (bool) - 是否允许 TqSdk 兜底

        Returns:
            DataFrame
        """
        allow_tqsdk = kwargs.get("allow_tqsdk_fallback", True)
        return self.sync_manager.get_kline(symbol, days, period, allow_tqsdk_fallback=allow_tqsdk)

    def get_quote(self, symbol: str) -> dict[str, Any] | None:
        """
        获取实时行情（从本地DB）

        Args:
            symbol: 品种代码

        Returns:
            行情字典
        """
        # 从 SQLite 获取品种信息
        symbol_info = self.sync_manager.sqlite.get_symbol(symbol)
        if symbol_info:
            return {
                "symbol": symbol,
                "last_price": symbol_info.get("last_price"),
                "open_interest": symbol_info.get("open_interest"),
                "volume": symbol_info.get("volume"),
            }
        return None

    def get_main_contracts(self, exchange: str = None) -> list[str]:
        """
        获取主力合约列表

        Args:
            exchange: 交易所

        Returns:
            主力合约列表
        """
        symbols = self.sync_manager.sqlite.get_all_symbols(exchange=exchange, active_only=True)
        return [s["symbol"] for s in symbols]

    def get_active_symbols(self, min_oi: int = 10000) -> dict[str, dict]:
        """
        获取活跃品种

        Args:
            min_oi: 最小持仓量

        Returns:
            活跃品种字典
        """
        symbols = self.sync_manager.get_active_symbols(min_oi=min_oi)
        result = {}
        for s in symbols:
            result[s["symbol"]] = {
                "name": s.get("name", s["symbol"]),
                "last_price": s.get("last_price", 0),
                "open_interest": s.get("open_interest", 0),
                "volume": s.get("volume", 0),
            }
        return result

    def is_available(self) -> bool:
        """检查数据源是否可用"""
        try:
            # 检查数据库文件是否存在
            sqlite_path = os.path.join(self.db_dir, "meta.db")
            duckdb_path = os.path.join(self.db_dir, "market.db")

            if os.path.exists(sqlite_path) and os.path.exists(duckdb_path):
                # 检查是否有数据
                stats = self.sync_manager.get_statistics()
                sqlite_stats = stats.get("sqlite", {})
                if sqlite_stats.get("total_symbols", 0) > 0:
                    return True

            return False

        except:
            return False


class DataSourceFactory:
    """数据源工厂（单例模式，全局共享一个数据源连接）"""

    _instance: DataSource | None = None
    _source_type: str = "auto"
    _health_cache: dict[str, Any] | None = None

    @staticmethod
    def check_health(source: str = "tqsdk", test_symbol: str = "RB") -> dict[str, Any]:
        """
        快速健康检查：用一次 quote 调用验证数据源连通性。

        Args:
            source: 数据源类型（目前仅支持 tqsdk）
            test_symbol: 用于测试的品种代码

        Returns:
            {
                'available': bool,
                'source': str,
                'latency_ms': float,
                'error': str or None
            }
        """
        if source == "tqsdk":
            try:
                from .tqsdk_bridge import TqSdkBridge

                bridge = TqSdkBridge(timeout=10)  # 健康检查用更短超时

                t0 = time.time()
                quote = bridge.get_quote(test_symbol)
                latency = (time.time() - t0) * 1000

                if quote and quote.get("last_price", 0) > 0:
                    DataSourceFactory._health_cache = {
                        "available": True,
                        "source": "tqsdk",
                        "latency_ms": round(latency, 1),
                        "error": None,
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    DataSourceFactory._health_cache = {
                        "available": False,
                        "source": "tqsdk",
                        "latency_ms": round(latency, 1),
                        "error": "quote 返回空数据",
                        "timestamp": datetime.now().isoformat(),
                    }
            except Exception as e:
                DataSourceFactory._health_cache = {
                    "available": False,
                    "source": "tqsdk",
                    "latency_ms": 0,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
        else:
            DataSourceFactory._health_cache = {
                "available": False,
                "source": source,
                "latency_ms": 0,
                "error": f"不支持的健康检查数据源: {source}",
                "timestamp": datetime.now().isoformat(),
            }

        return DataSourceFactory._health_cache

    @staticmethod
    def get_health() -> dict[str, Any] | None:
        """获取最近一次健康检查结果（缓存）"""
        return DataSourceFactory._health_cache

    @staticmethod
    def create(source: str = "auto", force_new: bool = False) -> DataSource:
        """
        创建或获取数据源（单例模式）

        参数:
            source: 数据源类型
                - "auto": 自动选择（优先本地DB，其次TqSdk，最后CSV）
                - "localdb": 本地数据库
                - "tqsdk": TqSdk
                - "csv": 本地CSV
            force_new: 强制创建新实例（用于测试或连接重置）

        返回:
            DataSource 实例（全局共享）
        """
        # 如果已有实例且类型匹配且不强制新建，直接返回
        if DataSourceFactory._instance is not None and not force_new:
            if source == DataSourceFactory._source_type or source == "auto":
                return DataSourceFactory._instance

        # 创建新实例
        if source == "auto":
            # 优先级：本地DB > TqSdk（禁止模拟数据兜底）
            localdb = LocalDBSource()
            if localdb.is_available():
                DataSourceFactory._instance = localdb
                DataSourceFactory._source_type = "localdb"
            else:
                tqsdk = TqSdkSource()
                if tqsdk.is_available():
                    DataSourceFactory._instance = tqsdk
                    DataSourceFactory._source_type = "tqsdk"
                else:
                    raise RuntimeError(
                        "无法获取真实数据：本地数据库不可用且 TqSdk 连接失败。"
                        "请检查：1) data/market.duckdb 是否存在；2) TqSdk 环境变量 TQ_USER/TQ_PASSWORD 是否设置。"
                    )
                    DataSourceFactory._source_type = "csv"
        elif source == "localdb":
            DataSourceFactory._instance = LocalDBSource()
            DataSourceFactory._source_type = "localdb"
        elif source == "tqsdk":
            DataSourceFactory._instance = TqSdkSource()
            DataSourceFactory._source_type = "tqsdk"
        elif source == "csv":
            DataSourceFactory._instance = CsvSource()
            DataSourceFactory._source_type = "csv"
        else:
            raise ValueError(f"不支持的数据源类型: {source}")

        return DataSourceFactory._instance

    @staticmethod
    def reset():
        """重置单例（用于测试）"""
        DataSourceFactory._instance = None
        DataSourceFactory._source_type = "auto"

    @staticmethod
    def get_source_type() -> str:
        """获取当前数据源类型"""
        return DataSourceFactory._source_type


# 便捷函数
def get_kline(symbol: str, days: int = 120, source: str = "auto") -> pd.DataFrame | None:
    """便捷函数：获取K线数据"""
    ds = DataSourceFactory.create(source)
    return ds.get_kline(symbol, days)


def get_quote(symbol: str, source: str = "auto") -> dict[str, Any] | None:
    """便捷函数：获取实时行情"""
    ds = DataSourceFactory.create(source)
    return ds.get_quote(symbol)


def get_active_symbols(min_oi: int = 10000, source: str = "auto") -> dict[str, dict]:
    """便捷函数：获取活跃品种"""
    ds = DataSourceFactory.create(source)
    if hasattr(ds, "get_active_symbols"):
        return ds.get_active_symbols(min_oi)
    return {}
