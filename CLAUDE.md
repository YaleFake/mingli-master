# CLAUDE.md —— 命理解读师项目规则

> 约束先行。动手前先读本文件。改规范时先改本文件、再改实践，不要反过来。

## 这个项目是什么

紫微斗数排盘 + 解读 + 出客户报告，并**把每次解读和客户反馈沉淀成可迭代的私有解读模型**。
排盘精度靠 iztro-py（确定性，不动）；解读精度靠 `records/` 反馈回路（持续迭代）。

## 目录约定（什么放哪）

```
mingli-master/
├── CLAUDE.md                    # 本文件，规则源头
├── SKILL.md                     # skill 主体，给 agent 读的工作流
├── scripts/
│   ├── true_solar_time.py       # 真太阳时校正（排盘前置，先跑这个）
│   ├── calculate_chart.py       # iztro-py 排盘（不改算法）
│   └── generate_html.py         # 填模板出 HTML（改它前先确认占位符契约）
├── templates/chart_template.html# 视觉层，只改 CSS 不动 {{占位符}} 和 class 名
├── references/                  # 解读知识库（模型的「权重」就长在这里）
│   ├── stars_reference.md
│   ├── four_hua_reference.md
│   ├── interpretation_guide.md
│   └── calibration_patterns.md  # ★ 反馈沉淀出的校正规则（由 feedback 蒸馏而来）
├── records/                     # ★ 每个客户一份记录，模型的「训练数据」
│   ├── SCHEMA.md                # 记录格式定义
│   └── YYYYMMDD_客户代号.json   # 单次解读 + 预测 + 反馈
└── samples/                     # 样例数据与样例命盘，不进客户数据
```

## 命名约定

- 客户记录：`records/YYYYMMDD_代号.json`，代号用化名/编号，**不存真实姓名身份证**（隐私先行）。
- 一个客户多次回访：同一文件内 `feedback` 数组追加，不新建文件。

## 排盘工作流（顺序不可乱）

1. **先校正再排盘**：`true_solar_time.py` → 拿到 `solar_date_for_chart` 和 `hour_index`。
   - 客户报的是钟表时间，必须经经度时差 + 均时差 + 夏令时校正。
   - 1986–1991 年夏季出生：脚本自动 -1h，务必跟客户确认是否记的是夏令时钟表。
   - 边界预警出现时：相邻两个时辰各排一盘，留到校准问答阶段定。
2. **子时规则**（iztro 源码 `fixLunarDayIndex` 实证）：晚子时(23–24点)安星按次日算，输入当天日期 + `--hour 12`；早子时(0–1点)输入当天日期 + `--hour 0`。**没有「算前一天」选项**。
3. 排盘 → 解读 → reading.json → 出 HTML。

## 模型迭代闭环（核心，别跳）

每出一份报告，就是一次「下注」。闭环：**预测 → 记录 → 客户反馈 → 算命中率 → 蒸馏规则 → 回写 references**。

1. 出报告时，每个判断标注一个**置信度**（不是装饰，是下注的概率）。
2. 客户反馈后，用 `feedback.py` 记一条 case，每个维度打 `hit / miss / partial`。
3. 累计后 `feedback.py --stats` 出**各维度命中率（胜率）**——数据说话。
4. 命中率低的维度 = 取象规则有偏差 → 在 `references/calibration_patterns.md` 写校正规则。
5. **先改 references（文档），下次解读自然用上**——这就是模型在「学习」。

> 没有反馈记录的解读 = 没有训练信号的模型。每个客户必记。

## 改动纪律

- 改 `templates/`：只动 CSS/视觉，保留全部 `{{占位符}}` 与 class 名，改完用 `samples/` 跑一遍验证 0 残留占位符。
- 改 `calculate_chart.py` 算法：原则上不改，iztro 已确定性正确；要改先在本文件记理由。
- 加解读规则：进 `references/`，不要硬编码进脚本。
