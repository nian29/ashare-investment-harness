#!/usr/bin/env python3
"""
知识库检索引擎 — 全文搜索 knowledge/ 目录下所有 MD 文件
纯 Python 标准库，零外部依赖，首次运行自动构建索引缓存

用法:
  python knowledge_search.py --keyword "止损"
  python knowledge_search.py --keyword "护城河" --category 03-产业层
  python knowledge_search.py --keyword "PE" --context 3
  python knowledge_search.py --regex "PE.*倍"
  python knowledge_search.py --list-categories
  python knowledge_search.py --index  # 强制重建索引
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# 强制 UTF-8 输出（Windows Git Bash 兼容）
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# === 配置 ===
KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
INDEX_FILE = Path(__file__).resolve().parent.parent / ".search_index.json"
CONTEXT_LINES = 2  # 默认上下文行数


# === 索引构建 ===
def build_index():
    """扫描 knowledge/ 目录，构建倒排索引"""
    index = {}
    file_count = 0

    for md_file in KNOWLEDGE_DIR.rglob("*.md"):
        category = md_file.parent.name
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            safe_print(f"[WARN] Cannot read {md_file}: {e}")
            continue

        file_count += 1
        rel_path = str(md_file.relative_to(KNOWLEDGE_DIR.parent))

        for line_num, line in enumerate(lines, start=1):
            # 提取中文词、英文词、数字
            tokens = set()
            # 中文词: 2-6 字连续中文字符
            for match in re.finditer(r"[一-鿿]{2,6}", line):
                tokens.add(match.group())
            # 英文词: 2+ 字母
            for match in re.finditer(r"[a-zA-Z]{2,}", line):
                tokens.add(match.group().lower())
            # 数字+单位组合
            for match in re.finditer(r"\d+[%倍亿万千点元股]", line):
                tokens.add(match.group())

            for token in tokens:
                if token not in index:
                    index[token] = []
                index[token].append({
                    "file": rel_path,
                    "line": line_num,
                    "category": category,
                    "text": line.strip()[:120],  # 截断长行
                })

    # 保存索引
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    return index, file_count


def load_index(force_rebuild=False):
    """加载索引，如不存在或强制重建则扫描"""
    if force_rebuild or not INDEX_FILE.exists():
        t0 = time.time()
        index, count = build_index()
        elapsed = time.time() - t0
        safe_print(f"[INDEX] Built: {count} files, {len(index)} tokens ({elapsed:.1f}s)")
        return index
    else:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)


# === 搜索 ===
def search(index, keyword, category=None, context=CONTEXT_LINES, regex_mode=False):
    """搜索索引并返回结果"""
    results = []

    if regex_mode:
        # 正则模式：遍历索引的所有 token，匹配 pattern
        pattern = re.compile(keyword, re.IGNORECASE)
        matched_tokens = [t for t in index if pattern.search(t)]
        if not matched_tokens:
            # fallback: 直接 grep 文件
            return grep_files(keyword, category, context, regex=True)
        entries = []
        for token in matched_tokens:
            entries.extend(index[token])
        results = entries
    else:
        # 关键词模式：精确匹配或模糊匹配
        if keyword in index:
            results = index[keyword]
        else:
            # 模糊匹配：包含关键词的 token
            matched = [t for t in index if keyword in t]
            if matched:
                for token in matched:
                    results.extend(index[token])
            else:
                # 最终回退：直接 grep
                return grep_files(keyword, category, context, regex=False)

    # 按 category 过滤
    if category:
        results = [r for r in results if r["category"] == category]

    # 去重（同文件同行）
    seen = set()
    unique = []
    for r in results:
        key = (r["file"], r["line"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique


def grep_files(keyword, category=None, context=CONTEXT_LINES, regex=False):
    """直接逐行 grep 文件（回退方案）"""
    results = []
    pattern = re.compile(keyword, re.IGNORECASE) if not regex else re.compile(keyword, re.IGNORECASE)

    for md_file in KNOWLEDGE_DIR.rglob("*.md"):
        cat = md_file.parent.name
        if category and cat != category:
            continue

        try:
            with open(md_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            continue

        rel_path = str(md_file.relative_to(KNOWLEDGE_DIR.parent))

        for line_num, line in enumerate(lines, start=1):
            if pattern.search(line):
                # 获取上下文
                ctx_start = max(0, line_num - context - 1)
                ctx_end = min(len(lines), line_num + context)
                ctx_lines = []
                for i in range(ctx_start, ctx_end):
                    prefix = ">>>" if i == line_num - 1 else "   "
                    ctx_lines.append(f"{prefix} {i+1}: {lines[i].rstrip()[:120]}")

                results.append({
                    "file": rel_path,
                    "line": line_num,
                    "category": cat,
                    "text": line.strip()[:120],
                    "context": ctx_lines,
                })

    return results


# === 输出安全处理 ===
import unicodedata


def strip_emoji(text):
    """去除终端无法显示的 emoji 和特殊符号"""
    cleaned = []
    for ch in text:
        # emoji 范围: U+1F000-U+1FFFF, U+2600-U+27BF, U+2300-U+23FF, U+2B00-U+2BFF
        cp = ord(ch)
        if (
            0x1F000 <= cp <= 0x1FFFF  # Emoticons, Symbols, etc
            or 0x2600 <= cp <= 0x27BF  # Misc Symbols
            or 0x2700 <= cp <= 0x27BF  # Dingbats (✅ etc)
            or cp in (0x2702, 0x2705, 0x2708, 0x2709, 0x270A, 0x270B, 0x270C, 0x270F,
                      0x2712, 0x2714, 0x2716, 0x2728, 0x2733, 0x2734, 0x2744, 0x2747,
                      0x274C, 0x274E, 0x2753, 0x2754, 0x2755, 0x2757, 0x2763, 0x2764,
                      0x2795, 0x2796, 0x2797, 0x27A1, 0x27B0, 0x27BF)
        ):
            continue
        try:
            ch.encode("gbk")
            cleaned.append(ch)
        except UnicodeEncodeError:
            cleaned.append("?")
    return "".join(cleaned)


def safe_print(text):
    """安全打印，自动去除终端不支持的字符"""
    print(strip_emoji(text))


# === 输出 ===
def format_results(results, keyword, elapsed):
    """格式化搜索结果"""
    if not results:
        safe_print(f"\n[SEARCH] 「{keyword}」-- no results\n")
        return

    from collections import defaultdict
    by_file = defaultdict(list)
    for r in results:
        by_file[r["file"]].append(r)

    safe_print(f"\n[SEARCH] 「{keyword}」-- {len(results)} hits ({elapsed:.2f}s)")
    safe_print("=" * 70)

    for file_path, entries in sorted(by_file.items()):
        cat = entries[0]["category"]
        safe_print(f"\n[FILE] {file_path}  [{cat}]")
        safe_print("-" * 50)
        for e in entries[:5]:
            safe_print(f"  L{e['line']:>4d}: {e['text']}")
            if "context" in e and e["context"]:
                for ctx_line in e["context"]:
                    safe_print(f"        {ctx_line}")
        if len(entries) > 5:
            safe_print(f"  ... +{len(entries) - 5} more, use --context to expand")

    safe_print(f"\n{'=' * 70}\n")


def list_categories():
    """列出所有分类及文件数"""
    cats = {}
    for d in sorted(KNOWLEDGE_DIR.iterdir()):
        if d.is_dir():
            md_count = len(list(d.glob("*.md")))
            cats[d.name] = md_count

    safe_print("\n[CATEGORIES] Knowledge base categories:\n")
    for name, count in cats.items():
        safe_print(f"  {name}  ({count} files)")
    safe_print("")


# === 入口 ===
def main():
    parser = argparse.ArgumentParser(
        description="A股投资知识库检索引擎",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--keyword", "-k", type=str, help="搜索关键词")
    parser.add_argument("--regex", "-r", type=str, help="正则表达式搜索")
    parser.add_argument("--category", "-c", type=str, help="限定分类 (如 '04-行业框架')")
    parser.add_argument("--context", "-n", type=int, default=CONTEXT_LINES, help="上下文行数")
    parser.add_argument("--list-categories", action="store_true", help="列出所有分类")
    parser.add_argument("--index", action="store_true", help="强制重建索引")

    args = parser.parse_args()

    if args.list_categories:
        list_categories()
        return

    query = args.keyword or args.regex
    if not query:
        parser.print_help()
        safe_print("\nExample: python knowledge_search.py --keyword ??")
        return

    regex_mode = bool(args.regex)
    query_display = args.regex or args.keyword

    t0 = time.time()
    index = load_index(force_rebuild=args.index)
    results = search(index, query, args.category, args.context, regex_mode)
    elapsed = time.time() - t0

    format_results(results, query_display, elapsed)


if __name__ == "__main__":
    main()
