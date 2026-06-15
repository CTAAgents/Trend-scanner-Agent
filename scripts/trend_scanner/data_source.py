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
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


class DataSource(ABC):
    """数据源基类"""
    
    @abstractmethod
    def get_kline(self, symbol: str, days: int = 120, period: str = "daily") -> Optional[pd.DataFrame]:
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
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取实时行情
        
        参数:
            symbol: 品种代码
            
        返回:
            行情字典，包含 last_price, open_interest, volume 等
        """
        pass
    
    @abstractmethod
    def get_main_contracts(self, exchange: str = None) -> List[str]:
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
        'RB': 'KQ.m@SHFE.rb',
        'HC': 'KQ.m@SHFE.hc',
        'I': 'KQ.m@DCE.i',
        'J': 'KQ.m@DCE.j',
        'JM': 'KQ.m@DCE.jm',
        'SF': 'KQ.m@CZCE.SF',
        'SM': 'KQ.m@CZCE.SM',
        
        # 有色金属
        'CU': 'KQ.m@SHFE.cu',
        'AL': 'KQ.m@SHFE.al',
        'ZN': 'KQ.m@SHFE.zn',
        'PB': 'KQ.m@SHFE.pb',
        'NI': 'KQ.m@SHFE.ni',
        'SN': 'KQ.m@SHFE.sn',
        
        # 能源化工
        'SC': 'KQ.m@INE.sc',
        'FU': 'KQ.m@SHFE.fu',
        'BU': 'KQ.m@SHFE.bu',
        'RU': 'KQ.m@SHFE.ru',
        'TA': 'KQ.m@CZCE.TA',
        'MA': 'KQ.m@CZCE.MA',
        'SA': 'KQ.m@CZCE.SA',
        'FG': 'KQ.m@CZCE.FG',
        'EG': 'KQ.m@DCE.EG',
        'EB': 'KQ.m@DCE.EB',
        'PP': 'KQ.m@DCE.pp',
        'V': 'KQ.m@DCE.v',
        'L': 'KQ.m@DCE.l',
        
        # 农产品
        'CF': 'KQ.m@CZCE.CF',
        'SR': 'KQ.m@CZCE.SR',
        'AP': 'KQ.m@CZCE.AP',
        'RM': 'KQ.m@CZCE.RM',
        'OI': 'KQ.m@CZCE.OI',
        'M': 'KQ.m@DCE.m',
        'Y': 'KQ.m@DCE.y',
        'P': 'KQ.m@DCE.p',
        'C': 'KQ.m@DCE.c',
        'CS': 'KQ.m@DCE.cs',
        'A': 'KQ.m@DCE.a',
        'B': 'KQ.m@DCE.b',
        'JD': 'KQ.m@DCE.jd',
        'LH': 'KQ.m@DCE.lh',
        
        # 贵金属
        'AU': 'KQ.m@SHFE.au',
        'AG': 'KQ.m@SHFE.ag',
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
    
    def get_kline(self, symbol: str, days: int = 120, period: str = "daily") -> Optional[pd.DataFrame]:
        """获取K线数据（使用桥接器）"""
        if not self.is_available():
            return None
        
        try:
            return self._bridge.get_kline(symbol, days, period)
        except Exception as e:
            print(f"[错误] TqSdk 获取K线失败: {e}", flush=True)
            return None
    
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取实时行情（使用桥接器）"""
        if not self.is_available():
            return None
        
        try:
            return self._bridge.get_quote(symbol)
        except Exception as e:
            print(f"[错误] TqSdk 获取行情失败: {e}", flush=True)
            return None
    
    def get_main_contracts(self, exchange: str = None) -> List[str]:
        """获取主力合约列表"""
        if exchange:
            return [v for k, v in self.MAIN_CONTRACT_MAP.items() 
                    if exchange.upper() in v]
        return list(self.MAIN_CONTRACT_MAP.values())
    
    def get_active_symbols(self, min_oi: int = 10000) -> Dict[str, Dict]:
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
                        oi = getattr(quote, 'open_interest', 0) or 0
                        if oi >= min_oi:
                            active_symbols[symbol] = {
                                'name': symbol,
                                'last_price': getattr(quote, 'last_price', 0),
                                'open_interest': oi,
                                'volume': getattr(quote, 'volume', 0),
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
    
    def get_kline(self, symbol: str, days: int = 120, period: str = "daily") -> Optional[pd.DataFrame]:
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
                    required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
                    if all(col in df.columns for col in required_cols):
                        # 转换日期格式
                        df['date'] = pd.to_datetime(df['date'])
                        
                        # 只保留最近N天的数据
                        if len(df) > days:
                            df = df.tail(days)
                        
                        return df
            
            return None
            
        except Exception as e:
            print(f"读取CSV失败: {e}")
            return None
    
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """从最新K线获取行情"""
        df = self.get_kline(symbol, days=1)
        if df is not None and len(df) > 0:
            latest = df.iloc[-1]
            return {
                'symbol': symbol,
                'last_price': latest.get('close', 0),
                'open_interest': latest.get('open_interest', 0),
                'volume': latest.get('volume', 0),
            }
        return None
    
    def get_main_contracts(self, exchange: str = None) -> List[str]:
        """获取数据目录中的所有品种"""
        if not self.is_available():
            return []
        
        symbols = []
        for filename in os.listdir(self.data_dir):
            if filename.endswith('.csv'):
                symbol = filename.replace('.csv', '').split('_')[0]
                symbols.append(symbol.upper())
        
        return symbols


class DataSourceFactory:
    """数据源工厂（单例模式，全局共享一个数据源连接）"""
    
    _instance: Optional[DataSource] = None
    _source_type: str = "auto"
    
    @staticmethod
    def create(source: str = "auto", force_new: bool = False) -> DataSource:
        """
        创建或获取数据源（单例模式）
        
        参数:
            source: 数据源类型
                - "auto": 自动选择（优先 TqSdk）
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
            tqsdk = TqSdkSource()
            if tqsdk.is_available():
                DataSourceFactory._instance = tqsdk
                DataSourceFactory._source_type = "tqsdk"
            else:
                DataSourceFactory._instance = CsvSource()
                DataSourceFactory._source_type = "csv"
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
def get_kline(symbol: str, days: int = 120, source: str = "auto") -> Optional[pd.DataFrame]:
    """便捷函数：获取K线数据"""
    ds = DataSourceFactory.create(source)
    return ds.get_kline(symbol, days)


def get_quote(symbol: str, source: str = "auto") -> Optional[Dict[str, Any]]:
    """便捷函数：获取实时行情"""
    ds = DataSourceFactory.create(source)
    return ds.get_quote(symbol)


def get_active_symbols(min_oi: int = 10000) -> Dict[str, Dict]:
    """便捷函数：获取活跃品种"""
    ds = DataSourceFactory.create("tqsdk")
    if isinstance(ds, TqSdkSource):
        return ds.get_active_symbols(min_oi)
    return {}
