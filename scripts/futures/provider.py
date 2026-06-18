"""
期货数据提供者

基于TqSdk的期货数据获取（首选）
"""

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.core.market_provider import MarketProvider, MarketType

logger = logging.getLogger(__name__)

# 期货品种列表
FUTURES_SYMBOLS = [
    # 黑色系
    "RB", "HC", "SS", "I", "J", "JM", "ZC", "SF", "SM",
    # 有色金属
    "CU", "AL", "ZN", "PB", "NI", "SN",
    # 能源化工
    "SC", "FU", "LU", "BU", "TA", "MA", "PP", "EG", "EB", "PG",
    # 农产品
    "A", "B", "M", "Y", "P", "OI", "RM", "CS", "C",
    # 贵金属
    "AU", "AG",
    # 股指
    "IF", "IC", "IH", "IM",
]

# 交易所映射
EXCHANGE_MAP = {
    "RB": "SHFE", "HC": "SHFE", "SS": "SHFE", "CU": "SHFE",
    "AL": "SHFE", "ZN": "SHFE", "PB": "SHFE", "NI": "SHFE", "SN": "SHFE",
    "AU": "SHFE", "AG": "SHFE", "FU": "SHFE", "BU": "SHFE", "SP": "SHFE",
    "RU": "SHFE", "NR": "INE", "SC": "INE",
    "I": "DCE", "J": "DCE", "JM": "DCE", "M": "DCE", "Y": "DCE",
    "P": "DCE", "C": "DCE", "CS": "DCE", "A": "DCE", "B": "DCE",
    "RR": "DCE", "L": "DCE", "V": "DCE", "EB": "DCE", "EG": "DCE",
    "PG": "DCE", "JD": "DCE", "LH": "DCE",
    "TA": "CZCE", "MA": "CZCE", "SR": "CZCE", "CF": "CZCE",
    "RM": "CZCE", "OI": "CZCE", "FG": "CZCE", "SA": "CZCE",
    "ZC": "CZCE", "SF": "CZCE", "SM": "CZCE", "AP": "CZCE",
    "CJ": "CZCE", "PK": "CZCE",
    "IF": "CFFEX", "IC": "CFFEX", "IH": "CFFEX", "IM": "CFFEX",
    "T": "CFFEX", "TF": "CFFEX", "TS": "CFFEX",
}


class FuturesProvider(MarketProvider):
    """
    期货数据提供者

    基于TqSdk的期货数据获取
    """

    def __init__(self, config: Dict[str, Any]):
        """
        初始化期货数据提供者

        Args:
            config: 配置字典
        """
        super().__init__(config)
        self._api = None
        self._ensure_tqsdk_connection()

    def _ensure_tqsdk_connection(self):
        """确保TqSdk连接"""
        try:
            from tqsdk import TqApi, TqAuth
            
            user = os.environ.get("TQ_USER")
            password = os.environ.get("TQ_PASSWORD")
            
            if not user or not password:
                logger.warning("TqSdk环境变量未设置，无法获取实时数据")
                return
            
            self._api = TqApi(auth=TqAuth(user, password))
            logger.info("TqSdk连接成功")
        except ImportError:
            logger.warning("TqSdk未安装，请运行: pip install tqsdk")
        except Exception as e:
            logger.error(f"TqSdk连接失败: {e}")

    def _get_market_type(self) -> MarketType:
        """获取市场类型"""
        return MarketType.FUTURES

    def _get_exchange(self, symbol: str) -> str:
        """获取交易所代码"""
        return EXCHANGE_MAP.get(symbol, "UNKNOWN")

    def _get_main_contract_symbol(self, symbol: str) -> str:
        """获取主力连续合约代码"""
        exchange = self._get_exchange(symbol)
        # TqSdk要求品种代码小写
        symbol_lower = symbol.lower()
        return f"KQ.m@{exchange}.{symbol_lower}"

    def get_kline(
        self,
        symbol: str,
        timeframe: str = "daily",
        count: int = 100,
    ) -> pd.DataFrame:
        """
        获取期货K线数据

        Args:
            symbol: 品种代码（如 "RB", "I"）
            timeframe: 时间周期（daily/weekly/monthly/5min/15min/30min/1h）
            count: 数据条数

        Returns:
            DataFrame: K线数据

        Raises:
            RuntimeError: TqSdk未连接时抛出
        """
        if self._api is None:
            self._ensure_tqsdk_connection()
        
        if self._api is None:
            raise RuntimeError("TqSdk未连接，无法获取期货数据。请检查TQ_USER和TQ_PASSWORD环境变量。")

        try:
            # 获取主力连续合约
            contract = self._get_main_contract_symbol(symbol)
            
            # 时间周期映射（TqSdk period参数，单位：秒）
            # 300=5min, 900=15min, 1800=30min, 3600=1h, 86400=daily, 604800=weekly
            period_map = {
                "5min": 300,
                "15min": 900,
                "30min": 1800,
                "1h": 3600,
                "daily": 86400,
                "weekly": 604800,
                "monthly": 2592000,
            }
            
            period = period_map.get(timeframe, 86400)  # 默认日线
            klines = self._api.get_kline_serial(contract, period, count)
            
            # 转换为DataFrame
            df = pd.DataFrame({
                "datetime": pd.to_datetime(klines["datetime"], unit="ns"),
                "open": klines["open"],
                "high": klines["high"],
                "low": klines["low"],
                "close": klines["close"],
                "volume": klines["volume"],
                "open_interest": klines.get("open_oi", 0),
            })
            
            df.set_index("datetime", inplace=True)
            
            # 数据时效性检查
            self._check_data_timeliness(df)
            
            return df.tail(count)
            
        except Exception as e:
            logger.error(f"获取{symbol}K线数据失败: {e}")
            raise

    def _check_data_timeliness(self, df: pd.DataFrame):
        """检查数据时效性"""
        if df.empty:
            return
        
        latest_time = df.index[-1]
        now = pd.Timestamp.now()
        
        # 计算数据延迟
        if latest_time.tzinfo is None:
            delay_hours = (now - latest_time).total_seconds() / 3600
        else:
            delay_hours = (now.tz_localize(None) - latest_time).total_seconds() / 3600
        
        # 数据滞后警告
        if delay_hours > 24:
            logger.warning(f"数据滞后超过24小时，最新时间: {latest_time}")
        elif delay_hours > 4:
            logger.info(f"数据滞后{delay_hours:.1f}小时，最新时间: {latest_time}")

    def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """
        获取期货实时行情

        Args:
            symbol: 品种代码

        Returns:
            Dict: 实时行情数据

        Raises:
            RuntimeError: TqSdk未连接时抛出
        """
        if self._api is None:
            self._ensure_tqsdk_connection()
        
        if self._api is None:
            raise RuntimeError("TqSdk未连接，无法获取实时数据")

        try:
            contract = self._get_main_contract_symbol(symbol)
            quote = self._api.get_quote(contract)
            
            return {
                "symbol": symbol,
                "last_price": quote.last_price,
                "open": quote.open,
                "high": quote.highest,
                "low": quote.lowest,
                "volume": quote.volume,
                "open_interest": quote.open_interest,
                "change": quote.last_price - quote.pre_close,
                "change_pct": (quote.last_price - quote.pre_close) / quote.pre_close * 100,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"获取{symbol}实时行情失败: {e}")
            raise

    def get_symbols(self) -> List[str]:
        """
        获取期货品种列表

        Returns:
            List[str]: 品种代码列表
        """
        return FUTURES_SYMBOLS

    def get_fundamental(self, symbol: str) -> Dict[str, Any]:
        """
        获取期货基本面数据

        Args:
            symbol: 品种代码

        Returns:
            Dict: 基本面数据（库存/仓单/持仓量）
        """
        # 获取实时持仓量
        try:
            quote = self.get_realtime_quote(symbol)
            open_interest = quote.get("open_interest", 0)
        except Exception:
            open_interest = 0
        
        return {
            "symbol": symbol,
            "open_interest": open_interest,
            "timestamp": datetime.now().isoformat(),
        }

    def get_open_interest(self, symbol: str) -> float:
        """
        获取持仓量

        Args:
            symbol: 品种代码

        Returns:
            float: 持仓量
        """
        try:
            quote = self.get_realtime_quote(symbol)
            return quote.get("open_interest", 0)
        except Exception:
            return 0.0

    def close(self):
        """关闭TqSdk连接"""
        if self._api is not None:
            try:
                self._api.close()
                logger.info("TqSdk连接已关闭")
            except Exception as e:
                logger.error(f"关闭TqSdk连接失败: {e}")
            finally:
                self._api = None
