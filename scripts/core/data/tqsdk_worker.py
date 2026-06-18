"""
TqSdk 工作进程

解决 TqSdk 的 sys.exit() 问题：
- 在独立子进程中运行 TqSdk
- 通过 JSON 文件交换数据
- 主进程不会被 sys.exit() 终止

使用方式：
    python scripts/trend_scanner/tqsdk_worker.py --symbol RB --days 120 --output data/tqsdk_output.json
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path


# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent))


def fetch_kline(symbol: str, days: int = 120, period: str = "daily") -> dict:
    """
    获取 K 线数据

    Args:
        symbol: 品种代码（如 "RB", "JM"）
        days: 获取天数
        period: 周期（daily/1h/15m 等）

    Returns:
        数据字典，包含 success, data, error 字段
    """
    try:
        from tqsdk import TqApi, TqAuth

        # 获取认证信息
        tq_user = os.environ.get("TQ_USER", "")
        tq_password = os.environ.get("TQ_PASSWORD", "")

        if not tq_user or not tq_password:
            return {"success": False, "error": "TQ_USER 或 TQ_PASSWORD 环境变量未设置", "data": None}

        auth = TqAuth(tq_user, tq_password)

        # 主力合约映射（完整版）
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

        # 获取 TqSdk 符号
        tq_symbol = MAIN_CONTRACT_MAP.get(symbol.upper())
        if not tq_symbol:
            # 尝试作为直接合约代码
            code = symbol.lower()
            if code.startswith("rb") or code.startswith("hc"):
                tq_symbol = f"SHFE.{code}"
            elif code.startswith("i") or code.startswith("j") or code.startswith("jm"):
                tq_symbol = f"DCE.{code}"
            elif code.startswith("cu") or code.startswith("al"):
                tq_symbol = f"SHFE.{code}"
            elif code.startswith("sc"):
                tq_symbol = f"INE.{code}"
            else:
                tq_symbol = symbol

        # 周期映射
        period_map = {
            "daily": 86400,
            "1h": 3600,
            "15m": 900,
            "5m": 300,
            "1m": 60,
        }
        dur_sec = period_map.get(period, 86400)

        # 获取数据（deadline 限制等待时间，避免盘前无数据时无限阻塞）
        api = TqApi(auth=auth)
        klines = api.get_kline_serial(tq_symbol, dur_sec, data_length=days)
        deadline = time.time() + 10  # 最多等待 10 秒
        try:
            api.wait_update(deadline=deadline)
        except Exception:
            pass  # 超时异常可忽略，klines 已有历史数据

        if klines is None or len(klines) == 0:
            api.close()
            return {"success": False, "error": f"无法获取 {symbol} 的数据", "data": None}

        # 转换为标准格式
        import pandas as pd

        df = pd.DataFrame(
            {
                "date": pd.to_datetime(klines["datetime"], unit="ns"),
                "open": klines["open"],
                "high": klines["high"],
                "low": klines["low"],
                "close": klines["close"],
                "volume": klines["volume"],
                "open_interest": klines["close_oi"],
            }
        )

        # 去除无效数据
        df = df.dropna()
        df = df[df["close"] > 0]

        api.close()

        # 转换为字典
        data = {
            "symbol": symbol,
            "tq_symbol": tq_symbol,
            "period": period,
            "records": len(df),
            "columns": list(df.columns),
            "data": df.to_dict(orient="records"),
        }

        return {"success": True, "error": None, "data": data}

    except SystemExit as e:
        # 捕获 TqSdk 的 sys.exit()
        return {"success": False, "error": f"TqSdk sys.exit: {e}", "data": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}


def fetch_quote(symbol: str) -> dict:
    """
    获取实时行情

    Args:
        symbol: 品种代码

    Returns:
        行情字典
    """
    try:
        from tqsdk import TqApi, TqAuth

        tq_user = os.environ.get("TQ_USER", "")
        tq_password = os.environ.get("TQ_PASSWORD", "")

        if not tq_user or not tq_password:
            return {"success": False, "error": "TQ_USER 或 TQ_PASSWORD 环境变量未设置", "data": None}

        auth = TqAuth(tq_user, tq_password)

        # 主力合约映射
        MAIN_CONTRACT_MAP = {
            "RB": "KQ.m@SHFE.rb",
            "I": "KQ.m@DCE.i",
            "J": "KQ.m@DCE.j",
            "JM": "KQ.m@DCE.jm",
            "CU": "KQ.m@SHFE.cu",
            "NI": "KQ.m@SHFE.ni",
            "SC": "KQ.m@INE.sc",
            "CF": "KQ.m@CZCE.CF",
            "AU": "KQ.m@SHFE.au",
            "AG": "KQ.m@SHFE.ag",
        }

        tq_symbol = MAIN_CONTRACT_MAP.get(symbol.upper(), symbol)

        api = TqApi(auth=auth)
        quote = api.get_quote(tq_symbol)
        deadline = time.time() + 10
        try:
            api.wait_update(deadline=deadline)
        except Exception:
            pass

        data = {
            "symbol": symbol,
            "last_price": getattr(quote, "last_price", 0),
            "open_interest": getattr(quote, "open_interest", 0),
            "volume": getattr(quote, "volume", 0),
            "bid_price1": getattr(quote, "bid_price1", 0),
            "ask_price1": getattr(quote, "ask_price1", 0),
            "highest": getattr(quote, "highest", 0),
            "lowest": getattr(quote, "lowest", 0),
            "pre_close": getattr(quote, "pre_close", 0),
        }

        api.close()

        return {"success": True, "error": None, "data": data}

    except SystemExit as e:
        return {"success": False, "error": f"TqSdk sys.exit: {e}", "data": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}


def fetch_all_symbols(exchanges: list = None) -> dict:
    """
    获取所有主力合约品种

    Args:
        exchanges: 交易所列表，默认 ['SHFE', 'DCE', 'CZCE', 'INE', 'CFFEX']

    Returns:
        {success, error, data: {symbols: [...]}}
    """
    try:
        from tqsdk import TqApi, TqAuth

        tq_user = os.environ.get("TQ_USER", "")
        tq_password = os.environ.get("TQ_PASSWORD", "")

        if not tq_user or not tq_password:
            return {"success": False, "error": "TQ_USER 或 TQ_PASSWORD 环境变量未设置", "data": None}

        if exchanges is None:
            exchanges = ["SHFE", "DCE", "CZCE", "INE", "CFFEX"]

        auth = TqAuth(tq_user, tq_password)
        api = TqApi(auth=auth)

        all_symbols = []

        for exchange in exchanges:
            try:
                instruments = api.query_quotes(ins_class="FUTURE", exchange_id=exchange)

                # 提取品种代码（去掉到期月份）
                variety_set = set()
                for inst in instruments:
                    parts = inst.split(".")
                    if len(parts) == 2:
                        contract = parts[1]
                        variety = "".join([c for c in contract if c.isalpha()])
                        variety_set.add(variety)

                # 创建主力合约代码
                for variety in variety_set:
                    main_contract = f"KQ.m@{exchange}.{variety}"
                    symbol_code = variety.upper()
                    all_symbols.append(
                        {"symbol": symbol_code, "tq_symbol": main_contract, "exchange": exchange, "variety": variety}
                    )

            except Exception as e:
                print(f"获取 {exchange} 品种失败: {e}", file=sys.stderr)
                continue

        api.close()

        return {"success": True, "error": None, "data": {"symbols": all_symbols, "count": len(all_symbols)}}

    except SystemExit as e:
        return {"success": False, "error": f"TqSdk sys.exit: {e}", "data": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}


def fetch_quotes_batch(tq_symbols: list) -> dict:
    """
    批量获取行情数据

    Args:
        tq_symbols: TqSdk 品种代码列表

    Returns:
        {success, error, data: {quotes: {...}}}
    """
    try:
        from tqsdk import TqApi, TqAuth

        tq_user = os.environ.get("TQ_USER", "")
        tq_password = os.environ.get("TQ_PASSWORD", "")

        if not tq_user or not tq_password:
            return {"success": False, "error": "TQ_USER 或 TQ_PASSWORD 环境变量未设置", "data": None}

        auth = TqAuth(tq_user, tq_password)
        api = TqApi(auth=auth)

        quotes = {}

        # 一次性订阅所有品种（不分批，减少连接开销）
        quote_objs = {}
        for tq_symbol in tq_symbols:
            try:
                quote_objs[tq_symbol] = api.get_quote(tq_symbol)
            except:
                continue

        # 一次性等待数据更新
        try:
            api.wait_update(deadline=time.time() + 15)
        except Exception:
            pass

        # 提取数据
        for tq_symbol, quote in quote_objs.items():
            try:
                oi = getattr(quote, "open_interest", 0) or 0
                quotes[tq_symbol] = {
                    "tq_symbol": tq_symbol,
                    "last_price": getattr(quote, "last_price", 0),
                    "open_interest": oi,
                    "volume": getattr(quote, "volume", 0),
                    "bid_price1": getattr(quote, "bid_price1", 0),
                    "ask_price1": getattr(quote, "ask_price1", 0),
                    "highest": getattr(quote, "highest", 0),
                    "lowest": getattr(quote, "lowest", 0),
                    "pre_close": getattr(quote, "pre_close", 0),
                }
            except:
                continue

        api.close()

        return {"success": True, "error": None, "data": {"quotes": quotes, "count": len(quotes)}}

    except SystemExit as e:
        return {"success": False, "error": f"TqSdk sys.exit: {e}", "data": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}


def main():
    parser = argparse.ArgumentParser(description="TqSdk 工作进程")
    parser.add_argument(
        "--action", choices=["kline", "quote", "symbols", "quotes_batch"], required=True, help="操作类型"
    )
    parser.add_argument("--symbol", type=str, help="品种代码")
    parser.add_argument("--symbols", type=str, help="品种列表（逗号分隔）")
    parser.add_argument("--days", type=int, default=120, help="获取天数")
    parser.add_argument("--period", type=str, default="daily", help="周期")
    parser.add_argument("--output", type=str, required=True, help="输出文件路径")

    args = parser.parse_args()

    # 执行操作
    if args.action == "kline":
        result = fetch_kline(args.symbol, args.days, args.period)
    elif args.action == "quote":
        result = fetch_quote(args.symbol)
    elif args.action == "symbols":
        result = fetch_all_symbols()
    elif args.action == "quotes_batch":
        if not args.symbols:
            result = {"success": False, "error": "quotes_batch 需要 --symbols 参数", "data": None}
        else:
            tq_symbols = [s.strip() for s in args.symbols.split(",")]
            result = fetch_quotes_batch(tq_symbols)
    else:
        result = {"success": False, "error": f"未知操作: {args.action}", "data": None}

    # 输出结果
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    # 打印状态
    if result["success"]:
        print(f"SUCCESS: {args.action} {args.symbol}")
    else:
        print(f"FAILED: {result['error']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
