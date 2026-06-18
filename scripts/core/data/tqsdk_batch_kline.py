"""
批量 K 线获取工作进程

在单个 TqApi 会话中获取多个品种的 K 线数据，
避免每个品种单独开子进程的开销。

使用方式：
    python scripts/trend_scanner/tqsdk_batch_kline.py --symbols RB,JM,I,CU --days 120 --output data/batch_klines.json
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))


def fetch_batch_klines(symbols: list, days: int = 120, period: str = "daily") -> dict:
    """
    在单个 TqApi 会话中批量获取 K 线数据

    Args:
        symbols: 品种代码列表（如 ['RB', 'JM', 'I']）
        days: 获取天数
        period: 周期

    Returns:
        {success, error, data: {symbol: {records, data}}}
    """
    try:
        import pandas as pd
        from tqsdk import TqApi, TqAuth

        tq_user = os.environ.get("TQ_USER", "")
        tq_password = os.environ.get("TQ_PASSWORD", "")

        if not tq_user or not tq_password:
            return {"success": False, "error": "TQ_USER 或 TQ_PASSWORD 未设置", "data": None}

        # 品种代码 -> TqSdk 主力合约映射
        def to_tq_symbol(code: str) -> str:
            code = code.strip().upper()
            # 已有交易所前缀
            if "." in code:
                return f"KQ.m@{code}" if not code.startswith("KQ") else code
            return f"KQ.m@SHFE.{code.lower()}"  # 默认前缀，后面按交易所修正

        # 交易所映射
        SHFE = {
            "RB",
            "HC",
            "RU",
            "NI",
            "CU",
            "AL",
            "ZN",
            "PB",
            "SN",
            "AU",
            "AG",
            "BU",
            "FU",
            "SP",
            "SS",
            "BR",
            "AO",
            "WR",
            "OP",
        }
        DCE = {
            "I",
            "J",
            "JM",
            "M",
            "Y",
            "P",
            "C",
            "CS",
            "A",
            "B",
            "JD",
            "LH",
            "PP",
            "V",
            "L",
            "EG",
            "EB",
            "PG",
            "BB",
            "FB",
            "RR",
            "LG",
        }
        CZCE = {
            "CF",
            "SR",
            "TA",
            "MA",
            "OI",
            "RM",
            "SA",
            "PF",
            "SF",
            "SM",
            "AP",
            "CJ",
            "UR",
            "ZC",
            "PK",
            "PX",
            "PR",
            "EC",
            "CY",
            "SH",
        }
        INE = {"SC", "LU", "NR", "BC"}
        CFFEX = {"IF", "IC", "IH", "IM", "T", "TF", "TL", "TS"}

        def get_exchange(code: str) -> str:
            if code in SHFE:
                return "SHFE"
            if code in DCE:
                return "DCE"
            if code in CZCE:
                return "CZCE"
            if code in INE:
                return "INE"
            if code in CFFEX:
                return "CFFEX"
            return "SHFE"

        period_map = {"daily": 86400, "1h": 3600, "15m": 900, "5m": 300, "1m": 60}
        dur_sec = period_map.get(period, 86400)

        auth = TqAuth(tq_user, tq_password)
        api = TqApi(auth=auth)

        results = {}
        kline_objs = {}

        # 订阅所有品种
        for sym in symbols:
            sym = sym.strip().upper()
            exchange = get_exchange(sym)
            tq_sym = f"KQ.m@{exchange}.{sym.lower()}"
            try:
                klines = api.get_kline_serial(tq_sym, dur_sec, data_length=days)
                kline_objs[sym] = (tq_sym, klines)
            except Exception as e:
                results[sym] = {"success": False, "error": str(e), "data": None}

        # 等待数据更新（deadline 限制）
        deadline = time.time() + 15
        try:
            api.wait_update(deadline=deadline)
        except Exception:
            pass

        # 提取数据
        for sym, (tq_sym, klines) in kline_objs.items():
            try:
                if klines is None or len(klines) == 0:
                    results[sym] = {"success": False, "error": "无数据", "data": None}
                    continue

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
                df = df.dropna()
                df = df[df["close"] > 0]

                results[sym] = {
                    "success": True,
                    "data": {
                        "symbol": sym,
                        "tq_symbol": tq_sym,
                        "records": len(df),
                        "data": df.to_dict(orient="records"),
                    },
                }
            except Exception as e:
                results[sym] = {"success": False, "error": str(e), "data": None}

        api.close()

        success_count = sum(1 for r in results.values() if r.get("success"))
        return {
            "success": True,
            "error": None,
            "data": {"results": results, "total": len(symbols), "success_count": success_count},
        }

    except SystemExit as e:
        return {"success": False, "error": f"TqSdk sys.exit: {e}", "data": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}


def main():
    parser = argparse.ArgumentParser(description="TqSdk 批量 K 线获取")
    parser.add_argument("--symbols", type=str, required=True, help="品种列表（逗号分隔）")
    parser.add_argument("--days", type=int, default=120, help="获取天数")
    parser.add_argument("--period", type=str, default="daily", help="周期")
    parser.add_argument("--output", type=str, required=True, help="输出文件路径")

    args = parser.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",")]

    result = fetch_batch_klines(symbols, args.days, args.period)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    if result["success"]:
        d = result["data"]
        print(f"SUCCESS: {d['success_count']}/{d['total']} symbols")
    else:
        print(f"FAILED: {result['error']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
