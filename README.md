# A股投资助手 Harness

将价值投资框架工程化为可执行的 AI 助手系统。

## 是什么

- 35 个领域知识文件（Markdown），覆盖银行/消费/电力/医药/科技等 9 大行业
- 结构化知识库（YAML），从 MD 自动抽取，支持程序化检索
- 3 个 CLI 工具：知识搜索、持仓跟踪、YAML 抽取
- AI 路由系统（CLAUDE.md + rules/），按触发词自动加载对应框架

## 快速开始

```bash
# 搜索知识库
python scripts/knowledge_search.py --keyword "止损"

# 查看持仓状态
python scripts/portfolio_tracker.py

# 用实时价格计算预警
python scripts/portfolio_tracker.py --prices "6.82,32.50,1.42,12.80"

# 重建 YAML 知识库
python scripts/yaml_extractor.py
```

## 目录

```
├── CLAUDE.md               # AI 路由主控（触发词 → 框架加载）
├── rules/                   # 分步确认流程（按需加载）
├── knowledge/               # 领域知识（35 个 MD，8 个分类）
│   ├── 00-哲学层/           投资大师框架
│   ├── 01-决策系统/         期望值+事前验尸+贝叶斯
│   ├── 02-宏观层/           利率传导+危机模型+声音光谱
│   ├── 03-产业层/           护城河分析+瓶颈理论
│   ├── 04-行业框架/         9 大行业特化分析
│   ├── 05-工具层/           财务+估值+季报+卖出+行为
│   ├── 06-执行层/           持仓模板+交易自检+选股流程
│   ├── 07-基础/             新人模式+学习计划+打新
│   └── 08-日志/             每日行情+交易记录
├── scripts/                 CLI 工具
├── data/                    持仓配置
└── templates/               报告模板
```

## 设计原则

- **MD 是源头，YAML 是缓存** — 修改知识改 MD，运行 `yaml_extractor.py` 同步
- **薄主控 + 厚模块** — CLAUDE.md 不到 100 行，流程文件按需加载
- **新人模式是架构级特性** — 所有输出用简单语言，不给黑话
- **三维缺一不可** — 护城河 + 估值 + 风险，分析个股必须全部覆盖

## 约束

- 始终用中文回复
- 不推荐具体买卖，给分析框架和概率判断
- 时效性数据必须实时获取，不凭记忆

## 在 Claude Code 中使用

1. 在 Claude Code 中切换到项目目录：
   ```bash
   cd /g/ashare-investment-harness
   ```
   或直接打开项目：`/open G:/ashare-investment-harness`

2. 对话中自然说出触发词，系统自动加载对应框架：

   | 你说 | 系统做 |
   |------|--------|
   | "帮我看看农行" / "分析海天" | 加载对应行业框架 + 财务速查 + 估值方法论，跑五问，输出三维分析 |
   | "今天怎么样了" | 确认交易日 → 拉数据 → 框架分析 → 生成日报 |
   | "能买吗/能卖吗/要不要卖" | 加载卖出框架 + 行为金融 → 逐条跑检查 → 给明确判断 |
   | "什么叫护城河" / "教我" | 切换学习模式 → 生活例子解释 → 检查理解 → 记录进度 |
   | "止损规则是什么" | 触发 `knowledge_search.py` 从 35 个 MD 中检索 |

3. 所有分析自动遵守：
   - **三维缺一不可**（护城河 + 估值 + 风险）
   - **事前验尸**（假设 2 年后亏一半，最可能因为什么）
   - **反向 DCF**（当前价格在赌什么事发生）
   - **新人模式**（所有黑话自动翻译成大白话）

4. 日常维护：
   ```bash
   # 知识改了，同步 YAML
   python scripts/yaml_extractor.py

   # 收盘后更新价格缓存
   python scripts/cache_update.py --prices "6.82,32.50,1.42,12.80"

   # 用缓存做预警检查
   python scripts/portfolio_tracker.py --cache
   ```

## Agents（显式调用）

不依赖 AI 自动路由，需要时直接运行：

```bash
# 查看可分析的标的
python .claude/agents/investment_analyst.py --list-tickers

# 生成某只股票的分析上下文（加载知识框架 + 构建 prompt）
python .claude/agents/investment_analyst.py --ticker 601288 --json

# 组合整体风险评估
python .claude/agents/risk_assessor.py --portfolio

# 单只股票风险自检
python .claude/agents/risk_assessor.py --ticker 603288 --price 32.50
```
