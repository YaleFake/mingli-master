#!/usr/bin/env python3
"""反馈记录 + 模型胜率统计

模型迭代闭环的度量端：累计客户反馈，算各维度命中率（胜率），并对比
「预测置信度 vs 实际命中率」找出过度自信/取象偏差的维度——数据说话。

用法:
    python3 feedback.py --new --code 客户代号        # 在 records/ 生成一条空白记录骨架
    python3 feedback.py --stats                       # 汇总所有记录，出胜率报告
    python3 feedback.py --stats --min 75              # 标红命中率低于 75% 的维度
"""
import argparse
import glob
import json
import os
from collections import defaultdict
from datetime import date

RECORDS_DIR = os.path.join(os.path.dirname(__file__), '..', 'records')
VERDICT_SCORE = {'hit': 1.0, 'partial': 0.5, 'miss': 0.0}
DIMENSIONS = ['命盘底色', '事业', '财运', '感情', '当前大限', '健康', '六亲', '流年']


def new_record(code):
    os.makedirs(RECORDS_DIR, exist_ok=True)
    fname = f"{date.today().strftime('%Y%m%d')}_{code}.json"
    path = os.path.join(RECORDS_DIR, fname)
    if os.path.exists(path):
        print(f'已存在，未覆盖: {path}')
        return
    skeleton = {
        "code": code,
        "chart_input": {
            "solar_date": "", "hour_index": None, "gender": "",
            "longitude": None, "true_solar_applied": True, "dst_applied": False
        },
        "predictions": [
            {"dimension": "命盘底色", "claim": "", "confidence": 70}
        ],
        "feedback": [
            {"date": date.today().strftime('%Y-%m-%d'), "by": "客户自评",
             "results": [{"dimension": "命盘底色", "verdict": "hit", "note": ""}],
             "calibration_note": ""}
        ]
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(skeleton, f, ensure_ascii=False, indent=2)
    print(f'已创建记录骨架: records/{fname}\n按 records/SCHEMA.md 填写，回访反馈往 feedback 数组追加。')


def load_records():
    recs = []
    for p in sorted(glob.glob(os.path.join(RECORDS_DIR, '*.json'))):
        try:
            with open(p, 'r', encoding='utf-8') as f:
                recs.append((os.path.basename(p), json.load(f)))
        except Exception as e:
            print(f'⚠ 跳过无法解析的文件 {p}: {e}')
    return recs


def stats(min_rate):
    recs = load_records()
    if not recs:
        print('records/ 暂无记录。先用 --new 建记录，出完报告后填反馈。')
        return

    # 各维度：命中分数列表 + 对应置信度
    dim_scores = defaultdict(list)
    dim_conf = defaultdict(list)
    calib_notes = []
    n_clients = len(recs)
    n_feedback = 0

    for fname, r in recs:
        conf_map = {p['dimension']: p.get('confidence') for p in r.get('predictions', [])}
        for fb in r.get('feedback', []):
            n_feedback += 1
            if fb.get('calibration_note'):
                calib_notes.append((r.get('code', fname), fb['calibration_note']))
            for res in fb.get('results', []):
                dim = res['dimension']
                score = VERDICT_SCORE.get(res.get('verdict'))
                if score is None:
                    continue
                dim_scores[dim].append(score)
                if conf_map.get(dim) is not None:
                    dim_conf[dim].append((conf_map[dim], score))

    print('=' * 56)
    print(f'  模型胜率报告   客户 {n_clients} 人 · 反馈 {n_feedback} 次')
    print('=' * 56)
    print(f'{"维度":<8}{"样本":>4}{"命中率":>8}{"均置信":>8}{"校准差":>8}  判断')
    print('-' * 56)

    overall = []
    rows = sorted(dim_scores.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))
    for dim, scores in rows:
        n = len(scores)
        hit_rate = sum(scores) / n * 100
        overall.extend(scores)
        conf_pairs = dim_conf.get(dim, [])
        avg_conf = sum(c for c, _ in conf_pairs) / len(conf_pairs) if conf_pairs else None
        gap = (avg_conf - hit_rate) if avg_conf is not None else None
        if hit_rate < min_rate:
            verdict = '★需校正取象规则'
        elif gap is not None and gap > 12:
            verdict = '过度自信，调低置信度'
        elif gap is not None and gap < -12:
            verdict = '偏保守，可调高'
        else:
            verdict = '稳定'
        conf_s = f'{avg_conf:5.0f}%' if avg_conf is not None else '  -- '
        gap_s = f'{gap:+5.0f}' if gap is not None else '  -- '
        print(f'{dim:<8}{n:>4}{hit_rate:>7.0f}%{conf_s:>8}{gap_s:>8}  {verdict}')

    print('-' * 56)
    if overall:
        print(f'{"整体":<8}{len(overall):>4}{sum(overall)/len(overall)*100:>7.0f}%')

    if calib_notes:
        print('\n校准笔记（待蒸馏进 references/calibration_patterns.md）：')
        for code, note in calib_notes:
            print(f'  · [{code}] {note}')
    print('\n下一步：命中率低/过度自信的维度，把校正规则写进 references/，下次解读自动生效。')


def main():
    p = argparse.ArgumentParser(description='反馈记录与模型胜率统计')
    p.add_argument('--new', action='store_true', help='新建记录骨架')
    p.add_argument('--code', help='客户代号（配合 --new）')
    p.add_argument('--stats', action='store_true', help='输出胜率统计')
    p.add_argument('--min', type=float, default=75, help='命中率告警阈值，默认 75')
    args = p.parse_args()

    if args.new:
        if not args.code:
            p.error('--new 需要 --code 客户代号')
        new_record(args.code)
    elif args.stats:
        stats(args.min)
    else:
        p.print_help()


if __name__ == '__main__':
    main()
