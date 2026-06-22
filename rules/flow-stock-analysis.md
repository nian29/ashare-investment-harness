# 个股分析流程

> 触发词：分析/看看/怎么看 + 股票名

## 分步确认（每次只问一个问题）

### 步骤 1：确认标的
"你想分析哪只股票？"
→ 如果已经说了，跳过这步

### 步骤 2：加载框架
根据行业并行加载对应文件（≤6个）：
- 银行 → `04-行业框架/industry-banking.md` + `02-宏观层/macro-transmission.md`
- 消费 → `04-行业框架/industry-consumer.md`
- 电力 → `04-行业框架/industry-power.md` + `04-行业框架/etf-methodology.md`（如果是ETF）
- 科技 → `04-行业框架/industry-tech.md` + `03-产业层/serenity-philosophy.md`
- 医药 → `04-行业框架/industry-pharma.md` + `03-产业层/morningstar-moat.md`
- 周期 → `04-行业框架/industry-cyclical.md` + `02-宏观层/macro-transmission.md`
- 交通 → `04-行业框架/industry-transportation.md`
- 制造 → `04-行业框架/industry-manufacturing.md`

**通用必加载**：`05-工具层/financial-analysis.md` + `05-工具层/valuation-methodology.md`

### 步骤 3：明确侧重
"你主要关心什么？"
- A. 公司质量（护城河深不深）
- B. 估值水位（贵不贵）
- C. 买卖时机（现在该不该动）
- D. 全方位分析（三个都要）

### 步骤 4：跑五问
1. **期望值**：赚的概率 × 赚的金额 > 亏的概率 × 亏的金额？
2. **事前验尸**：假设 2 年后亏了一半，写出 3 个具体的失败原因
3. **反向 DCF**：当前价格在赌什么？这个赌注合理吗？
4. **贝叶斯更新**：最近有没有新消息改变判断？
5. **执行检查**：如果是交易建议，跑交易前 60 秒自检

### 步骤 5：输出三维分析
```
┌─ 一句话结论
├─ 护城河：来源？宽度？趋势？
├─ 估值水位：反向DCF说了什么？PE/PB在历史什么位置？
├─ 风险清单：最大的三个风险是什么？
└─ 综合判断：🟢 可以 / 🟡 等等 / 🔴 不建议
```

### 步骤 6：确认
"对这个结论还有疑问吗？"
