#!/usr/bin/env python3
"""
投资分析师 Agent —— 加载知识框架 + 构建分析提示词

显式调用入口，不依赖 AI 自动路由。

用法:
  python .claude/agents/investment_analyst.py --ticker 601288
  python .claude/agents/investment_analyst.py --ticker 603288 --sector consumer
  python .claude/agents/investment_analyst.py --list-tickers
  python .claude/agents/investment_analyst.py --ticker 601288 --json
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

KNOWLEDGE_DIR = ROOT / "knowledge"

# 行业 → 框架文件映射
SECTOR_FILES = {
    "银行": ["04-行业框架/industry-banking-framework.md", "02-宏观层/macro-transmission-mechanism.md"],
    "食品饮料": ["04-行业框架/industry-consumer-framework.md"],
    "消费": ["04-行业框架/industry-consumer-framework.md"],
    "电力": ["04-行业框架/industry-power-framework.md"],
    "交通运输": ["04-行业框架/industry-transportation-framework.md"],
    "医药": ["04-行业框架/industry-pharma-framework.md", "03-产业层/morningstar-moat-framework.md"],
    "科技": ["04-行业框架/industry-tech-framework.md", "03-产业层/serenity-investment-philosophy.md"],
    "周期": ["04-行业框架/industry-cyclical-framework.md"],
    "制造": ["04-行业框架/industry-manufacturing-framework.md"],
    "ETF": ["04-行业框架/etf-investment-methodology.md"],
}
# 通用必加载
COMMON_FILES = ["05-工具层/financial-analysis-foundation.md", "05-工具层/valuation-methodology.md"]


def load_knowledge_files(files):
    """加载知识文件并返回合并文本"""
    combined = []
    for f in files:
        path = KNOWLEDGE_DIR / f
        if path.exists():
            content = path.read_text(encoding="utf-8")
            lines = content.split("\n")[:500]
            combined.append(f"\n## 文件: {f}\n" + "\n".join(lines))
        else:
            combined.append(f"\n## [警告] 文件不存在: {f}")
    return "\n".join(combined)


def get_stock_info(ticker, portfolio):
    """从持仓配置中获取股票信息"""
    for h in portfolio.get("holdings", []):
        if h["symbol"] == ticker:
            return h
    for w in portfolio.get("watchlist", []):
        if w["symbol"] == ticker:
            return {**w, "shares": 0, "cost_basis": w.get("target_price", 0), "pct": 0,
                    "stop_loss_hard": 0, "stop_loss_clear": 0, "logic": w.get("logic", ""), "sector": "未知"}
    return None


def build_analysis_prompt(stock, sector, price=None):
    """构建分析提示词"""
    # 行业框架文件
    files = SECTOR_FILES.get(sector, [])
    files.extend(COMMON_FILES)
    files = list(dict.fromkeys(files))

    knowledge_text = load_knowledge_files(files)

    prompt = f"""请基于以下知识框架分析 {stock.get('name', '?')} ({stock.get('symbol', '?')})。

## 持仓信息
- 名称: {stock.get('name', '?')}
- 代码: {stock.get('symbol', '?')}
- 行业: {sector}
- 成本: {stock.get('cost_basis', 'N/A')}
- 当前价格: {price or '待获取'}
- 仓位占比: {stock.get('pct', 'N/A')}%
- 硬止损: {stock.get('stop_loss_hard', 'N/A')}
- 清仓线: {stock.get('stop_loss_clear', 'N/A')}
- 买入逻辑: {stock.get('logic', 'N/A')}

## 知识框架（从以下文件加载）
{knowledge_text}

## 必须覆盖的分析维度（三维缺一不可）
1. **护城河分析**：来源？变宽还是变窄？5年后还在吗？
2. **估值分析**：反向DCF——当前价格在赌什么？PE/PB在历史什么位置？
3. **风险分析**：事前验尸——假设2年后跌50%，最可能因为什么？
4. **综合判断**：🟢 关注 / 🟡 观望 / 🔴 不建议

新人模式：解释所有术语，用简单语言。"""
    return prompt


def main():
    parser = argparse.ArgumentParser(description="投资分析师 Agent")
    parser.add_argument("--ticker", type=str, help="股票代码")
    parser.add_argument("--sector", type=str, help="行业（可选，自动推断）")
    parser.add_argument("--price", type=float, help="当前价格")
    parser.add_argument("--list-tickers", action="store_true")
    parser.add_argument("--json", action="store_true", help="JSON输出")

    args = parser.parse_args()
    portfolio = load_portfolio()

    if args.list_tickers:
        print("\n可分析标的:\n")
        for h in portfolio.get("holdings", []):
            print(f"  {h['symbol']} {h['name']:<8} [{h['sector']}] 成本 {h['cost_basis']} 仓位 {h['pct']}%")
        for w in portfolio.get("watchlist", []):
            print(f"  {w['symbol']} {w['name']:<8} [关注池]")
        return

    if not args.ticker:
        parser.print_help()
        print("\n示例: python .claude/agents/investment_analyst.py --ticker 601288")
        return

    stock = get_stock_info(args.ticker, portfolio)
    if not stock:
        print(f"[ERROR] 未找到: {args.ticker}")
        sys.exit(1)

    sector = args.sector or stock.get("sector", "未知")
    prompt = build_analysis_prompt(stock, sector, args.price)

    if args.json:
        output = {
            "ticker": args.ticker, "name": stock.get("name"), "sector": sector,
            "stock_info": stock, "analysis_prompt": prompt,
            "knowledge_files": SECTOR_FILES.get(sector, []) + COMMON_FILES,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*80}")
        print(f"  投资分析 Agent: {stock.get('name')} ({args.ticker})")
        print(f"{'='*80}\n")
        print(prompt)
        print(f"\n{'='*80}")
        print("  将以上提示词发送给 Claude，或在此对话中继续分析")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
