#!/usr/bin/env python3
"""
数据缓存管理 —— 本地 CSV 缓存近 3 日持仓股价，作为 akshare 失败时的降级数据源

用法:
  python cache_update.py                          # 交互式输入价格，写入缓存
  python cache_update.py --prices "6.82,32.50,1.42,12.80"   # 批量写入
  python cache_update.py --read                    # 读取最新缓存
"""

import argparse
import csv
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"


def load_portfolio():
    with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def read_cache():
    """读取最新缓存数据"""
    cache_files = sorted(CACHE_DIR.glob("prices_*.csv"))
    if not cache_files:
        return None, None, {}

    latest = cache_files[-1]
    # 从文件名提取日期: prices_20260622.csv
    cache_date = latest.stem.replace("prices_", "")

    prices = {}
    with open(latest, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            prices[row["symbol"]] = {
                "name": row["name"],
                "price": float(row["price"]),
            }

    return latest, cache_date, prices


def write_cache(prices_dict):
    """写入今日缓存"""
    today = date.today().strftime("%Y%m%d")
    cache_file = CACHE_DIR / f"prices_{today}.csv"

    with open(cache_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", "name", "price", "updated"])
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for symbol, info in prices_dict.items():
            writer.writerow([symbol, info["name"], info["price"], now])

    print(f"[OK] Cached {len(prices_dict)} prices to {cache_file.name}")

    # 清理超过 3 天的旧缓存
    cutoff = date.today() - timedelta(days=3)
    for old in CACHE_DIR.glob("prices_*.csv"):
        try:
            file_date_str = old.stem.replace("prices_", "")
            file_date = datetime.strptime(file_date_str, "%Y%m%d").date()
            if file_date < cutoff:
                old.unlink()
                print(f"[CLEAN] Removed stale cache: {old.name}")
        except (ValueError, OSError):
            pass


def show_cache():
    """显示缓存状态"""
    cache_file, cache_date, prices = read_cache()
    if not cache_file:
        print("[CACHE] No cache found. Run with --prices to create.")
        return

    age = date.today() - datetime.strptime(cache_date, "%Y%m%d").date()
    freshness = "新鲜" if age.days == 0 else f"{age.days}天前" if age.days <= 3 else "过期"

    print(f"\n[CACHE] {cache_file.name} ({freshness})")
    print("-" * 50)
    total_value = 0
    portfolio = load_portfolio()
    for h in portfolio["holdings"]:
        symbol = h["symbol"]
        if symbol in prices:
            p = prices[symbol]
            pos_value = h["shares"] * p["price"]
            pnl = (p["price"] - h["cost_basis"]) / h["cost_basis"] * 100
            total_value += pos_value
            print(f"  {h['name']:<8} {p['price']:>7.2f}  ({pnl:>+5.1f}%)  = {pos_value:>8,.0f}")
        else:
            print(f"  {h['name']:<8} (no data)")
    print(f"  {'─'*40}")
    print(f"  当前市值: {total_value:,.0f}  已投: {sum(h['shares']*h['cost_basis'] for h in portfolio['holdings']):,.0f}")
    print()


def main():
    parser = argparse.ArgumentParser(description="持仓股价缓存管理")
    parser.add_argument("--prices", type=str, help="价格列表（逗号分隔，与 portfolio.json 顺序一致）")
    parser.add_argument("--read", action="store_true", help="读取最新缓存")
    args = parser.parse_args()

    if args.read:
        show_cache()
        return

    portfolio = load_portfolio()

    if args.prices:
        values = [float(x.strip()) for x in args.prices.split(",")]
        symbols = [h["symbol"] for h in portfolio["holdings"]]
        if len(values) != len(symbols):
            print(f"[ERROR] Need {len(symbols)} prices, got {len(values)}")
            sys.exit(1)
        prices_dict = {}
        for s, h, v in zip(symbols, portfolio["holdings"], values):
            prices_dict[s] = {"name": h["name"], "price": v}
        write_cache(prices_dict)
        show_cache()
    else:
        # 交互式输入
        print("\nEnter current prices (press Enter to skip):")
        prices_dict = {}
        for h in portfolio["holdings"]:
            val = input(f"  {h['name']}({h['symbol']}): ").strip()
            if val:
                prices_dict[h["symbol"]] = {"name": h["name"], "price": float(val)}
        if prices_dict:
            write_cache(prices_dict)
            show_cache()
        else:
            print("[CACHE] No data entered, nothing cached.")


if __name__ == "__main__":
    main()
