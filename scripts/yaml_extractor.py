#!/usr/bin/env python3
"""
知识库 YAML 抽取器 —— 从 MD 文件生成 knowledge_base_v3.yaml
MD 是源头（source of truth），YAML 是派生缓存。

检测 MD 中的 <!-- YAML:key --> 标记定位要抽取的区块，
配合正则模式匹配自动提取规则、公式、指标等结构化数据。

用法:
  python yaml_extractor.py                  # 生成/更新 knowledge_base_v3.yaml
  python yaml_extractor.py --check          # 检查 MD 和 YAML 是否同步（CI 用）
  python yaml_extractor.py --diff           # 显示 MD 和 YAML 的差异
"""

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import yaml  # pip install pyyaml (std lib doesn't have yaml)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = ROOT / "knowledge"
DATA_DIR = ROOT / "data"
YAML_OUTPUT = ROOT / "knowledge_base_v3.yaml"

# === 提取器注册表 ===
# 每个提取器是一个函数 (file_path, content_lines) -> dict | None


# 规则关键词（用于过滤非规则行）
RULE_KEYWORDS = [
    "止损", "止盈", "仓位", "纪律", "必须", "禁止", "不能", "绝不",
    "强制", "上限", "不追", "不做", "不超过", "每天", "每次",
    "先确保", "先看", "缺一不可", "三维", "硬止损", "清仓",
    "买得好", "防御优先", "不需要", "一定要", "务必",
]


def is_rule_line(line_text):
    """判断一行文本是否是规则（而非描述/元数据/触发词）"""
    text = line_text.lower()
    # 过滤: 元数据类
    skip_patterns = ["node_type", "triggers:", "description:", "type:", "originsessionid",
                     "触发", "框架", "参见", "详见", "加载", "翻"]
    for sp in skip_patterns:
        if sp in text:
            return False
    # 过滤: 引用链接
    if "[[" in line_text:
        return False
    # 必须有规则关键词
    return any(kw in line_text for kw in RULE_KEYWORDS)


def extract_rules(filepath, lines):
    """从 MD 文件中提取规则"""
    rules = []
    # 只处理在"规则"或"纪律"或"检查"或"原则"段落中的行
    in_rule_section = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 检测段落标题
        if re.match(r"^#{1,3}\s", stripped):
            section_title = stripped.lower()
            in_rule_section = any(kw in section_title for kw in
                                  ["规则", "纪律", "纪律", "检查", "必须", "原则", "禁止", "不能",
                                   "绝不", "止损", "止盈", "仓位", "交易", "强制"])
            continue

        if not in_rule_section:
            continue

        # 模式 1: "- **规则名**：内容"
        m = re.match(r"[-•]\s*\*\*(.+?)\*\*[：:]\s*(.+)", stripped)
        if m:
            name, content = m.group(1).strip(), m.group(2).strip()
            if len(name) >= 2 and len(content) >= 5 and is_rule_line(name + content):
                name = re.sub(r"\*+", "", name).strip()
                content = re.sub(r"\*+", "", content).strip()
                rules.append({
                    "id": f"rule_{filepath.stem}_{len(rules):03d}",
                    "name": name[:80],
                    "content": content[:300],
                    "source_file": str(filepath.relative_to(ROOT)),
                })
                continue

        # 模式 2: "N. **规则名**：内容"
        m = re.match(r"(\d+)[\.\)]\s*\*\*(.+?)\*\*[：:]\s*(.+)", stripped)
        if m:
            name, content = m.group(2).strip(), m.group(3).strip()
            name = re.sub(r"\*+", "", name).strip()
            content = re.sub(r"\*+", "", content).strip()
            if len(name) >= 2 and len(content) >= 5 and is_rule_line(name + content):
                rules.append({
                    "id": f"rule_{filepath.stem}_{m.group(1).zfill(3)}",
                    "name": name[:80],
                    "content": content[:300],
                    "source_file": str(filepath.relative_to(ROOT)),
                })
                continue

        # 模式 3: 普通编号规则 "N. 内容"（可能有 **加粗**）
        m = re.match(r"(\d+)[\.\)]\s+(.+)", stripped)
        if m:
            content = re.sub(r"\*+", "", m.group(2).strip())
            if len(content) >= 8 and is_rule_line(content):
                rules.append({
                    "id": f"rule_{filepath.stem}_{m.group(1).zfill(3)}",
                    "name": content[:80],
                    "content": content[:300],
                    "source_file": str(filepath.relative_to(ROOT)),
                })
                continue

        # 模式 4: Markdown 表格行
        if "|" in stripped and not stripped.startswith("|---") and not stripped.startswith("|--"):
            cols = [c.strip() for c in stripped.split("|") if c.strip()]
            if len(cols) >= 2:
                left, right = cols[0], cols[-1]
                if left in ("规则", "名称", "条件", "止损线", "指标", "纪律", "---"):
                    continue
                if is_rule_line(left + right):
                    rules.append({
                        "id": f"rule_{filepath.stem}_tbl_{len(rules):03d}",
                        "name": left[:80],
                        "content": right[:300],
                        "source_file": str(filepath.relative_to(ROOT)),
                    })

    return {"rules": rules} if rules else None


def extract_sector_info(filepath, lines):
    """从行业框架文件提取行业关键指标和框架信息"""
    if "04-行业框架" not in str(filepath):
        return None

    text = "".join(lines)
    filename = filepath.stem

    # 提取文件标题（第一个 # 标题）
    title_match = re.search(r"^#\s*(.+)", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else filename

    # === 提取关键指标：解析 Markdown 表格 ===
    metrics = []
    in_table = False
    table_header = None

    for line in lines:
        stripped = line.strip()

        # 检测表格开始
        if stripped.startswith("|") and not stripped.startswith("|---") and not stripped.startswith("|--"):
            cols = [c.strip() for c in stripped.split("|") if c.strip()]

            # 跳过非指标表格（如"卖出信号"、"风险来源"、"变更记录"等）
            if any(skip in line for skip in ("信号", "风险来源", "变更", "日期", "卖出", "⚠️", "规则")):
                continue

            if table_header is None:
                # 第一行是表头
                table_header = cols
            else:
                # 数据行：要求 >= 3 列（名称+含义+标准）
                if len(cols) >= 3 and len(cols[0]) >= 2:
                    # 跳过非指标行（"乐观叙事"、"悲观叙事"等）
                    if cols[0] in ("维度", "乐观叙事"):
                        continue
                    metrics.append({
                        "name": cols[0][:60],
                        "value": " | ".join(cols[1:])[:300],
                        "source": "表格行",
                    })
        elif stripped.startswith("|---") or stripped.startswith("|--"):
            # 表头分隔行，表示确实是个表格
            in_table = True
            continue
        elif stripped.startswith("## ") or stripped == "":
            # 新段落或空行结束表格
            if table_header and metrics:
                # 只保留第一个表格（核心指标表）
                break
            table_header = None

    # 如果表格没抓到，回退到 ### 指标 N：标题模式
    if not metrics:
        for i, line in enumerate(lines):
            m = re.match(r"#{2,4}\s*(?:指标\s*\d+[：:]?\s*)?(.+)", line.strip())
            if m and any(kw in line for kw in ("指标", "净息", "不良", "拨备", "ROE", "ROA", "资本", "股息", "PB", "PE", "增长", "营收", "毛利", "净利", "产能", "利用", "车流")):
                name = m.group(1).strip()
                # 取下一行的非空文本作为描述
                desc_parts = []
                for j in range(i + 1, min(i + 5, len(lines))):
                    nl = lines[j].strip()
                    if nl.startswith("#") or nl == "":
                        continue
                    if len(nl) > 10:
                        desc_parts.append(nl[:150])
                        break
                value = desc_parts[0] if desc_parts else ""
                if len(name) >= 2:
                    metrics.append({"name": name[:60], "value": value[:300], "source": "指标标题"})

    # 如果还是没抓到，回退到列表模式
    if not metrics:
        metric_section = re.search(r"(?:核心|关键|必看)\s*指标[\s\S]*?(?=\n##|\n---|\Z)", text, re.DOTALL)
        if metric_section:
            for line in metric_section.group().split("\n"):
                line = line.strip()
                m = re.match(r"[-•]\s*(.+?)[：:]\s*(.+)", line)
                if m:
                    metrics.append({"name": m.group(1).strip()[:60], "value": m.group(2).strip()[:300], "source": "列表行"})

    # === 提取估值逻辑 ===
    valuation = ""
    # 多种模式搜索估值相关内容
    val_patterns = [
        r"(?:估值(?:逻辑|方法|看|怎么看|锚|水位|判断|区间|：|:))[\s\S]*?(?=\n### |\n## |\n---|\Z)",
        r"(?:PB\s*(?:是|锚|为|：|:))[\s\S]*?(?=\n### |\n## |\n---|\Z)",
        r"###\s*(?:估值.*|PB.*|PE.*|怎么看.*贵)\s*\n[\s\S]*?(?=\n### |\n## |\n---|\Z)",
        r"(?:综合判断|综合评估)[\s\S]*?(?=\n### |\n## |\n---|\Z)",
    ]
    for pat in val_patterns:
        val_match = re.search(pat, text, re.DOTALL)
        if val_match and len(val_match.group().strip()) > 20:
            valuation = val_match.group().strip()[:500]
            break

    # 最后一招：找任何包含 "PB"、"PE"、"贵"、"便宜"、"合理" 的段落
    if not valuation:
        for line in lines:
            if re.search(r"(?:PB|PE|贵不贵|便宜|合理估|低估|高估|估值)", line.strip()):
                idx = lines.index(line)
                # 取前后 3 行
                start = max(0, idx - 3)
                end = min(len(lines), idx + 4)
                valuation = "".join(l.strip() for l in lines[start:end])[:300]
                if len(valuation) > 20:
                    break

    # === 提取周期位置 ===
    cycle = ""
    cycle_match = re.search(r"(?:周期位置|行业周期|当前阶段)[\s\S]*?(?=\n##|\n---|\Z)", text, re.DOTALL)
    if cycle_match:
        cycle = cycle_match.group().strip()[:300]

    return {
        "sectors": [{
            "file": str(filepath.relative_to(ROOT)),
            "name": title,
            "filename": filename,
            "key_metrics": metrics,
            "valuation_logic": valuation,
            "cycle_position": cycle,
        }]
    }


def extract_formulas(filepath, lines):
    """提取公式"""
    formulas = []
    text = "".join(lines)

    for m in re.finditer(r"(?:公式|FORMULA)[：:\s]*\n?```?\n?(.+?)```?", text, re.DOTALL):
        formulas.append({"raw": m.group(1).strip()[:300], "source": str(filepath.relative_to(ROOT))})

    return {"formulas": formulas} if formulas else None


def extract_yaml_markers(filepath, lines):
    """提取 <!-- YAML:key --> 标记区块"""
    markers = {}
    text = "".join(lines)
    for m in re.finditer(r"<!--\s*YAML:(\w+)\s*-->\s*\n(.*?)(?=\n<!--|$)", text, re.DOTALL):
        key = m.group(1)
        value = m.group(2).strip()
        markers[key] = value
    return {"yaml_markers": markers} if markers else None


# 提取器列表（按优先级）
EXTRACTORS = [
    extract_yaml_markers,  # 显式标记优先
    extract_sector_info,
    extract_formulas,
    extract_rules,
]


# === 主逻辑 ===
def scan_knowledge():
    """扫描所有 MD 文件并提取结构化数据"""
    all_data = defaultdict(list)

    for md_file in sorted(KNOWLEDGE_DIR.rglob("*.md")):
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"[WARN] Cannot read {md_file}: {e}")
            continue

        for extractor in EXTRACTORS:
            result = extractor(md_file, lines)
            if result:
                for key, value in result.items():
                    if isinstance(value, list):
                        all_data[key].extend(value)
                    elif isinstance(value, dict):
                        all_data[key].append(value)

    return dict(all_data)


def load_portfolio():
    """加载持仓数据"""
    pf_file = DATA_DIR / "portfolio.json"
    if pf_file.exists():
        with open(pf_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def build_yaml(all_data, portfolio):
    """组装最终的 knowledge_base_v3.yaml 结构"""
    yaml_data = {
        "meta": {
            "version": "0.1.0",
            "generated": time.strftime("%Y-%m-%d %H:%M"),
            "source": "Auto-extracted from knowledge/*.md",
            "total_files": "35",
        },
        "stocks": [],
        "watchlist": [],
        "sectors": all_data.get("sectors", []),
        "rules": all_data.get("rules", []),
        "formulas": all_data.get("formulas", []),
        "yaml_markers": all_data.get("yaml_markers", []),
        "changelog": [{"version": "0.1.0", "date": time.strftime("%Y-%m-%d"), "changes": ["Initial extraction from MD files"]}],
    }

    # 持仓
    if portfolio:
        for h in portfolio.get("holdings", []):
            yaml_data["stocks"].append({
                "symbol": h["symbol"],
                "name": h["name"],
                "sector": h["sector"],
                "shares": h["shares"],
                "cost_basis": h["cost_basis"],
                "stop_loss_hard": h["stop_loss_hard"],
                "stop_loss_clear": h["stop_loss_clear"],
                "pct": h["pct"],
                "logic": h["logic"],
            })
        for w in portfolio.get("watchlist", []):
            yaml_data["watchlist"].append(w)

    return yaml_data


def save_yaml(yaml_data, output_path):
    """保存 YAML 文件"""
    # 自定义 YAML 输出格式
    class CustomDumper(yaml.Dumper):
        def increase_indent(self, flow=False, indentless=False):
            return super().increase_indent(flow, False)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# A股投资知识库 v3 — 从 knowledge/*.md 自动生成\n")
        f.write(f"# 生成时间: {yaml_data['meta']['generated']}\n")
        f.write("# 不要手动编辑此文件！MD 是源头，修改请改 knowledge/ 下的 MD 文件\n")
        f.write("# 然后运行: python scripts/yaml_extractor.py\n\n")
        yaml.dump(yaml_data, f, Dumper=CustomDumper, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120)


def print_diff(yaml_data):
    """打印 YAML 内容摘要"""
    print(f"\n[SUMMARY] Extracted:")
    print(f"  Rules:    {len(yaml_data.get('rules', []))}")
    print(f"  Formulas: {len(yaml_data.get('formulas', []))}")
    print(f"  Stocks:   {len(yaml_data.get('stocks', []))}")
    print(f"  Sectors:  {len(yaml_data.get('sectors', []))}")
    print(f"  Markers:  {len(yaml_data.get('yaml_markers', []))}")
    print()


def main():
    parser = argparse.ArgumentParser(description="MD -> YAML 知识抽取器")
    parser.add_argument("--check", action="store_true", help="检查是否同步（CI 模式）")
    parser.add_argument("--diff", action="store_true", help="显示抽取摘要")
    args = parser.parse_args()

    t0 = time.time()

    # 扫描 MD 文件
    all_data = scan_knowledge()

    # 加载持仓
    portfolio = load_portfolio()

    # 组装 YAML
    yaml_data = build_yaml(all_data, portfolio)

    # 输出
    if args.check:
        if YAML_OUTPUT.exists():
            print("[OK] YAML file exists")
        else:
            print("[WARN] YAML file missing, run: python scripts/yaml_extractor.py")
            sys.exit(1)
        return

    if args.diff:
        print_diff(yaml_data)
        return

    save_yaml(yaml_data, YAML_OUTPUT)

    elapsed = time.time() - t0
    print(f"[DONE] Generated {YAML_OUTPUT.name} ({elapsed:.1f}s)")
    print_diff(yaml_data)


if __name__ == "__main__":
    main()
