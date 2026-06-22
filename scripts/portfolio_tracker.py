#!/usr/bin/env python3
"""
持仓跟踪工具 —— 止损预警 + 盈亏计算 + 仓位检查

用法:
  python portfolio_tracker.py                  # 静态持仓概览（成本+止损线）
  python portfolio_tracker.py --live           # 手动输入实时价格后计算预警
  python portfolio_tracker.py --prices "6.72,32.50,1.42,12.80"  # 用给定价格计算
  python portfolio_tracker.py --alerts-only    # 只看预警
  python portfolio_tracker.py --json           # JSON输出
"""

import argparse
import json
import sys
from pathlib import Path

# 强制 UTF-8 输出（Windows Git Bash 兼容）
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"


def load_portfolio():
    """加载持仓配置"""
    with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def calc_summary(portfolio, prices=None):
    """计算持仓摘要，如果给定了实时价格则计算动态盈亏"""
    holdings = portfolio["holdings"]
    summary = []

    for h in holdings:
        entry = {
            "name": h["name"],
            "symbol": h["symbol"],
            "shares": h["shares"],
            "cost": h["cost_basis"],
            "cost_total": h["shares"] * h["cost_basis"],
            "stop_hard": h["stop_loss_hard"],
            "stop_clear": h["stop_loss_clear"],
            "stop_hard_loss": round(h["shares"] * (h["cost_basis"] - h["stop_loss_hard"]), 2),
            "stop_clear_loss": round(h["shares"] * (h["cost_basis"] - h["stop_loss_clear"]), 2),
            "pct": h["pct"],
            "sector": h["sector"],
            "logic": h["logic"],
            "note": h.get("note", ""),
        }

        if prices:
            price = prices.get(h["symbol"])
            if price:
                entry["price_now"] = price
                entry["pnl_pct"] = round((price - h["cost_basis"]) / h["cost_basis"] * 100, 2)
                entry["pnl_amount"] = round(h["shares"] * (price - h["cost_basis"]), 2)
                entry["dist_to_stop_hard"] = round((price - h["stop_loss_hard"]) / h["stop_loss_hard"] * 100, 2)
                entry["dist_to_stop_clear"] = round((price - h["stop_loss_clear"]) / h["stop_loss_clear"] * 100, 2)

                # 预警等级
                dist = entry["dist_to_stop_hard"]
                if dist <= 3:
                    entry["alert"] = "RED"
                elif dist <= 8:
                    entry["alert"] = "YELLOW"
                else:
                    entry["alert"] = "GREEN"

        summary.append(entry)

    return summary


def print_table(summary, portfolio):
    """打印持仓表格"""
    has_prices = "price_now" in summary[0] if summary else False

    if has_prices:
        print(f"\n{'='*80}")
        print(f"  持仓跟踪 · 实时模式")
        print(f"{'='*80}")
        print(f"{'名称':<12} {'现价':>7} {'成本':>7} {'盈亏%':>8} {'盈亏额':>9} {'距硬止损%':>9} {'预警':>6}")
        print(f"{'-'*80}")
        for s in summary:
            alert_tag = {"RED": "!! 危险", "YELLOW": "! 关注", "GREEN": "安全"}[s["alert"]]
            print(f"{s['name']:<12} {s['price_now']:>7.2f} {s['cost']:>7.3f} {s['pnl_pct']:>+7.2f}% {s['pnl_amount']:>+8.0f} {s['dist_to_stop_hard']:>+8.2f}% {alert_tag:>6}")
        print(f"{'='*80}")
    else:
        print(f"\n{'='*80}")
        print(f"  持仓跟踪 · 静态模式（成本+止损线）")
        print(f"{'='*80}")
        print(f"{'名称':<12} {'数量':>6} {'成本':>7} {'成本总额':>10} {'硬止损':>7} {'清仓':>7} {'硬止损亏':>9} {'仓位%':>6}")
        print(f"{'-'*80}")
        for s in summary:
            print(f"{s['name']:<12} {s['shares']:>6} {s['cost']:>7.3f} {s['cost_total']:>10.0f} {s['stop_hard']:>7.2f} {s['stop_clear']:>7.2f} {s['stop_hard_loss']:>9.0f} {s['pct']:>5}%")

    # 汇总
    total_cost = sum(s["cost_total"] for s in summary)
    print(f"\n  已投: {total_cost:.0f}  现金: {portfolio['cash_remaining']:.0f}  总资金: {portfolio['total_capital']:.0f}  仓位: {total_cost/portfolio['total_capital']*100:.0f}%")
    print(f"{'='*80}\n")

    # 超标检查
    for s in summary:
        if s["pct"] > 20:
            print(f"  !! 超标警告: {s['name']} 仓位 {s['pct']}% > 20% 纪律上限")
            if s.get("note"):
                print(f"     备注: {s['note']}")

    # 预警汇总
    if has_prices:
        reds = [s for s in summary if s["alert"] == "RED"]
        yellows = [s for s in summary if s["alert"] == "YELLOW"]
        if reds:
            print(f"\n  !! 红色预警（距硬止损 < 3%）:")
            for s in reds:
                print(f"     {s['name']}: 距硬止损 {s['dist_to_stop_hard']:.1f}%, 触发即亏 {s['stop_hard_loss']:.0f} 元")
        if yellows:
            print(f"\n  ! 黄色关注（距硬止损 < 8%）:")
            for s in yellows:
                print(f"     {s['name']}: 距硬止损 {s['dist_to_stop_hard']:.1f}%")
        if not reds and not yellows:
            print(f"\n  [OK] 所有持仓距硬止损均 > 8%，无需预警")

    # 关注池
    watchlist = portfolio.get("watchlist", [])
    if watchlist:
        print(f"\n  关注池:")
        for w in watchlist:
            print(f"     {w['name']}({w['symbol']}) — 目标 {w.get('target_price', 'N/A')} — {w['logic']}")

    print()


def parse_prices(prices_str, portfolio):
    """解析价格输入: '6.72,32.50,1.42,12.80'"""
    values = [float(x.strip()) for x in prices_str.split(",")]
    symbols = [h["symbol"] for h in portfolio["holdings"]]
    if len(values) != len(symbols):
        print(f"[ERROR] 需要 {len(symbols)} 个价格（顺序: {', '.join(symbols)}），给了 {len(values)} 个")
        sys.exit(1)
    return dict(zip(symbols, values))


def interactive_prices(portfolio):
    """交互式输入价格"""
    print("\n请输入实时价格（直接回车跳过）:")
    prices = {}
    for h in portfolio["holdings"]:
        val = input(f"  {h['name']}({h['symbol']}): ").strip()
        if val:
            prices[h["symbol"]] = float(val)
    return prices if prices else None


def main():
    parser = argparse.ArgumentParser(description="A股持仓跟踪工具")
    parser.add_argument("--live", action="store_true", help="交互式输入实时价格")
    parser.add_argument("--prices", type=str, help="价格列表（逗号分隔，按JSON顺序: 601288,603288,561560,600377）")
    parser.add_argument("--alerts-only", action="store_true", help="只看预警")
    parser.add_argument("--json", action="store_true", help="JSON输出")

    args = parser.parse_args()

    portfolio = load_portfolio()

    # 获取价格
    prices = None
    if args.live:
        prices = interactive_prices(portfolio)
    elif args.prices:
        prices = parse_prices(args.prices, portfolio)

    summary = calc_summary(portfolio, prices)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif args.alerts_only and prices:
        reds = [s for s in summary if s["alert"] == "RED"]
        yellows = [s for s in summary if s["alert"] == "YELLOW"]
        if reds:
            for s in reds:
                print(f"RED: {s['name']} 距硬止损 {s['dist_to_stop_hard']:.1f}%")
        if yellows:
            for s in yellows:
                print(f"YELLOW: {s['name']} 距硬止损 {s['dist_to_stop_hard']:.1f}%")
        if not reds and not yellows:
            print("[OK] No alerts")
    else:
        print_table(summary, portfolio)


if __name__ == "__main__":
    main()
