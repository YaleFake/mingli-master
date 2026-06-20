# records/ 记录格式

一个客户一个文件：`records/YYYYMMDD_代号.json`。模型的训练数据就是这些文件。

## 字段

```jsonc
{
  "code": "客户代号",                 // 化名/编号，不存真实身份信息
  "chart_input": {                    // 排盘输入（校正后）
    "solar_date": "1971-6-28",
    "hour_index": 1,                  // true_solar_time.py 输出
    "gender": "男",
    "longitude": 116.41,
    "true_solar_applied": true,       // 是否做了真太阳时校正
    "dst_applied": false
  },
  "predictions": [                    // 报告里每个判断 = 一次下注
    {"dimension": "命盘底色", "claim": "思维型，爱推翻自己", "confidence": 70},
    {"dimension": "事业",     "claim": "适合台前/影响力角色", "confidence": 75},
    {"dimension": "感情",     "claim": "沟通是缘分关键",     "confidence": 65}
  ],
  "feedback": [                       // 可多次回访，往数组追加
    {
      "date": "2026-06-20",
      "by": "客户自评",
      "results": [                    // verdict: hit / partial / miss
        {"dimension": "命盘底色", "verdict": "hit",     "note": "很准"},
        {"dimension": "事业",     "verdict": "partial", "note": "方向对，行业偏技术"},
        {"dimension": "感情",     "verdict": "miss",    "note": "实际很少冲突"}
      ],
      "calibration_note": "巨门化禄此客户偏内向，沟通强但不外放——化禄不必然外向"
    }
  ]
}
```

## verdict 评分（用于算命中率/胜率）

- `hit` = 1.0
- `partial` = 0.5
- `miss` = 0.0

dimension 用固定词表，便于跨客户聚合：
`命盘底色 / 事业 / 财运 / 感情 / 当前大限 / 健康 / 六亲 / 流年`

## 用法

- 新建：`python3 scripts/feedback.py --new --code 客户代号`
- 出胜率：`python3 scripts/feedback.py --stats`
