#!/usr/bin/env python3
"""洗掉 knowledge/ 所有 MD 文件的 YAML frontmatter"""
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = ROOT / "knowledge"

count = 0
stripped_bytes = 0

for md_file in sorted(KNOWLEDGE_DIR.rglob("*.md")):
    with open(md_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 检测 frontmatter: 文件必须以 --- 开头
    if not content.startswith("---"):
        continue

    # 找到第二个 --- (frontmatter 结束)
    end = content.find("---", 3)
    if end == -1:
        continue

    # 去掉 frontmatter 块 + 后面的空行
    body = content[end + 3:].lstrip("\n")

    old_size = len(content.encode("utf-8"))
    new_size = len(body.encode("utf-8"))
    stripped_bytes += old_size - new_size

    with open(md_file, "w", encoding="utf-8") as f:
        f.write(body)

    count += 1
    print(f"  [OK] {md_file.relative_to(KNOWLEDGE_DIR)}")

print(f"\n[DONE] Stripped frontmatter from {count} files, saved {stripped_bytes:,} bytes")
