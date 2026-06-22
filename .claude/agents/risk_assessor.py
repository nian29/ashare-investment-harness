#!/usr/bin/env python3
"""
风险评估 Agent —— 单票风险检查 + 组合整体风险评估

用法:
  python .claude/agents/risk_assessor.py --portfolio
  python .claude/agents/risk_assessor.py --ticker 601288 --price 6.82
  python .claude/agents/risk_assessor.py --scenario "利率升100bp"
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from portfolio_tracker import load_portfolio


def check_stock_risk(stock, price=None):
    """单只股票风险检查"""
    risks = []

    if stock.get("pct", 0) > 20:
        risks.append({"type": "仓位超标", "severity": "HIGH",
                       "detail": f"当前仓位 {stock['pct']}% > 20% 纪律上限"})

    if price:
        hard = stock.get("stop_loss_hard")
        if hard and hard > 0:
            dist = (price - hard) / hard * 100
            if dist < 3:
                loss = stock.get("shares", 0) * (stock.get("cost_basis", 0) - hard)
                risks.append({"type": "临近硬止损", "severity": "HIGH",
                               "detail": f"距硬止损仅 {dist:.1f}%，触发预计亏损 {loss:.0f} 元"})
            elif dist < 8:
                risks.append({"type": "接近硬止损", "severity": "MEDIUM",
                               "detail": f"距硬止损 {dist:.1f}%，需密切关注"})

        clear = stock.get("stop_loss_clear")
        if clear and clear > 0 and price < clear:
            risks.append({"type": "已触发清仓线", "severity": "CRITICAL",
                           "detail": f"当前价 {price} < 清仓线 {clear}，应立即执行"})

    if stock.get("sector") == "银行" and stock.get("pct", 0) > 15:
        risks.append({"type": "银行板块集中", "severity": "MEDIUM",
                       "detail": "银行板块单一持仓 > 15%，关注不良率 + NIM"})

    return risks


def assess_portfolio_risk(portfolio):
    """组合整体风险评估"""
    holdings = portfolio.get("holdings", [])
    total = portfolio.get("total_capital", 0)
    risks = []

    # 总仓位
    invested = sum(h["shares"] * h["cost_basis"] for h in holdings)
    pct = invested / total * 100 if total else 0
    if pct > 90:
        risks.append({"type": "总仓位过高", "severity": "MEDIUM",
                       "detail": f"总仓位 {pct:.0f}%，现金储备不足"})

    # 行业集中度
    from collections import Counter
    sector_pct = Counter()
    for h in holdings:
        sector_pct[h.get("sector", "未知")] += h.get("pct", 0)
    for sector, p in sector_pct.items():
        if p > 40:
            risks.append({"type": "行业超标", "severity": "HIGH",
                           "detail": f"{sector} 占比 {p:.0f}% > 40% 上限"})

    # 单票超标
    for h in holdings:
        if h.get("pct", 0) > 20:
            risks.append({"type": "单票超标", "severity": "HIGH",
                           "detail": f"{h['name']}({h['symbol']}) 占比 {h['pct']}% > 20%"})

    # 组合股息覆盖（简化：假设平均 4%）
    div_yield_avg = 4.0  # 保守估计
    if div_yield_avg < 3:
        risks.append({"type": "组合防御性不足", "severity": "LOW",
                       "detail": f"组合平均股息率约 {div_yield_avg:.1f}%"})

    return risks


def main():
    parser = argparse.ArgumentParser(description="风险评估 Agent")
    parser.add_argument("--ticker", type=str)
    parser.add_argument("--price", type=float)
    parser.add_argument("--portfolio", action="store_true")
    parser.add_argument("--scenario", type=str)
    parser.add_argument("--json", action="store_true")

    args = parser.parse_args()
    portfolio = load_portfolio()
    emoji = {"CRITICAL": "RED", "HIGH": "HIGH", "MEDIUM": "MED", "LOW": "LOW"}

    if args.portfolio:
        risks = assess_portfolio_risk(portfolio)
        if args.json:
            print(json.dumps({"risks": risks}, ensure_ascii=False, indent=2))
        else:
            print(f"\n{'='*80}")
            print("  组合风险自检")
            print(f"{'='*80}")
            if risks:
                for r in risks:
                    print(f"  [{r['severity']}] {r['type']}: {r['detail']}")
            else:
                print("  [OK] 无重大风险")
            print()

    elif args.ticker:
        stock = None
        for h in portfolio.get("holdings", []):
            if h["symbol"] == args.ticker:
                stock = h
                break
        if not stock:
            print(f"[ERROR] 未找到: {args.ticker}")
            sys.exit(1)

        risks = check_stock_risk(stock, args.price)
        if args.json:
            print(json.dumps({"ticker": args.ticker, "name": stock["name"], "risks": risks},
                           ensure_ascii=False, indent=2))
        else:
            print(f"\n{'='*80}")
            print(f"  风险自检: {stock['name']} ({args.ticker})")
            print(f"{'='*80}")
            if args.price:
                print(f"  当前价: {args.price}  成本: {stock['cost_basis']}")
            if risks:
                for r in risks:
                    print(f"  [{r['severity']}] {r['type']}: {r['detail']}")
            else:
                print("  [OK] 无重大风险")

            if args.price and stock.get("stop_loss_hard", 0) > 0:
                dist = (args.price - stock["stop_loss_hard"]) / stock["stop_loss_hard"] * 100
                print(f"\n  距硬止损: {dist:+.1f}%")
            print()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
