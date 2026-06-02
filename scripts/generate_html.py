#!/usr/bin/env python3
"""HTML 命盘生成脚本

读取排盘数据 JSON + 解读文字，填充 HTML 模板，输出最终命盘文件。

用法:
    python3 generate_html.py --chart chart_data.json --reading reading.json --output mingpan.html
"""
import argparse
import json
import os
import sys

HOUR_NAMES_MAP = {
    0: '早子时', 1: '丑时', 2: '寅时', 3: '卯时',
    4: '辰时', 5: '巳时', 6: '午时', 7: '未时',
    8: '申时', 9: '酉时', 10: '戌时', 11: '亥时', 12: '晚子时',
}

# 宫位在 4x4 网格中的排列顺序（外圈顺时针）
# Row 1: 巳(0) 午(1) 未(2) 申(3)
# Row 2: 辰(11) [center] [center] 酉(4)
# Row 3: 卯(10) [center] [center] 戌(5)
# Row 4: 寅(9) 丑(8) 子(7) 亥(6)
GRID_ORDER = [
    # row 1: indices 0,1,2,3
    {'index': None, 'row': 1, 'col': 1},  # 巳 - will be filled by branch mapping
    {'index': None, 'row': 1, 'col': 2},  # 午
    {'index': None, 'row': 1, 'col': 3},  # 未
    {'index': None, 'row': 1, 'col': 4},  # 申
    # row 2
    {'index': None, 'row': 2, 'col': 1},  # 辰
    # center occupies row 2-3, col 2-3
    {'index': None, 'row': 2, 'col': 4},  # 酉
    # row 3
    {'index': None, 'row': 3, 'col': 1},  # 卯
    {'index': None, 'row': 3, 'col': 4},  # 戌
    # row 4
    {'index': None, 'row': 4, 'col': 1},  # 寅
    {'index': None, 'row': 4, 'col': 2},  # 丑
    {'index': None, 'row': 4, 'col': 3},  # 子
    {'index': None, 'row': 4, 'col': 4},  # 亥
]

BRANCH_GRID_MAP = {
    '巳': (1, 1), '午': (1, 2), '未': (1, 3), '申': (1, 4),
    '辰': (2, 1),                          '酉': (2, 4),
    '卯': (3, 1),                          '戌': (3, 4),
    '寅': (4, 1), '丑': (4, 2), '子': (4, 3), '亥': (4, 4),
}


def build_palace_cell(p, soul_branch, body_branch, current_decadal_branch):
    branch = p['earthly_branch']
    name = p['name']
    major = p['major_stars']
    minor = p['minor_stars']
    mutagens = p['mutagens']

    classes = ['palace']
    if branch == soul_branch:
        classes.append('active')
    if branch == current_decadal_branch:
        classes.append('current-limit')

    stars_html = ''
    if major:
        for s in major:
            mut = next((m['mutagen'] for m in mutagens if m['star'] == s), None)
            if mut:
                stars_html += f'<span class="star main">{s}</span>\n'
                stars_html += f'<span class="star four-hua">{s}{mut}</span>\n'
            else:
                stars_html += f'<span class="star main">{s}</span>\n'
        for s in minor:
            mut = next((m['mutagen'] for m in mutagens if m['star'] == s), None)
            if mut:
                stars_html += f'<span class="star">{s}</span>\n'
                stars_html += f'<span class="star four-hua">{s}{mut}★</span>\n'
            else:
                stars_html += f'<span class="star">{s}</span>\n'
    else:
        stars_html = '<span class="star empty">空宫</span>\n'

    badges = ''
    for tag in p['tags']:
        if tag == '命宫':
            badges += '<div class="palace-badge badge-ming">命宫</div>\n'
        elif tag == '身宫':
            badges += '<div class="palace-badge badge-body">身宫</div>\n'

    if branch == current_decadal_branch and '命宫' not in p['tags'] and '身宫' not in p['tags']:
        badges += '<div class="palace-badge badge-limit">当前大限</div>\n'

    return f'''<div class="{' '.join(classes)}">
      <div class="palace-name">{name}</div>
      <div class="palace-dizhi">{branch}</div>
      <div class="palace-stars">{stars_html}</div>
      {badges}
    </div>'''


def build_palace_grid(palaces, soul_branch, body_branch, current_decadal_branch):
    grid = {}
    for p in palaces:
        branch = p['earthly_branch']
        if branch in BRANCH_GRID_MAP:
            row, col = BRANCH_GRID_MAP[branch]
            grid[(row, col)] = build_palace_cell(p, soul_branch, body_branch, current_decadal_branch)

    cells = []
    for row in range(1, 5):
        for col in range(1, 5):
            if row in (2, 3) and col in (2, 3):
                continue  # center area
            cell = grid.get((row, col), '<div class="palace"></div>')
            cells.append(cell)

    return '\n    '.join(cells)


def build_four_hua_tags(year_mutagens):
    mutagen_classes = {
        '化禄': 'hua-lu', '化权': 'hua-quan',
        '化科': 'hua-ke', '化忌': 'hua-ji',
    }
    tags = []
    for m in year_mutagens:
        cls = mutagen_classes.get(m['mutagen'], '')
        tags.append(f'<span class="hua-tag {cls}">{m["star"]}{m["mutagen"]}</span>')
    return '\n        '.join(tags)


def build_reading_cards(reading):
    cn_nums = ['一', '二', '三', '四', '五', '六', '七']
    cards = []
    for i, card in enumerate(reading.get('cards', [])):
        num = cn_nums[i] if i < len(cn_nums) else str(i + 1)
        classes = ['reading-card']
        if card.get('full'):
            classes.append('full')
        if card.get('highlight'):
            classes.append('highlight')
        if card.get('teal'):
            classes.append('teal-highlight')

        prob_html = ''
        if card.get('probabilities'):
            for pb in card['probabilities']:
                prob_html += f'''<div class="prob-bar">
                    <span class="prob-label">{pb['label']}</span>
                    <div class="prob-track"><div class="prob-fill" style="width:{pb['pct']}%"></div></div>
                    <span class="prob-pct">{pb['pct']}%</span>
                </div>\n'''

        cards.append(f'''<div class="{' '.join(classes)}" data-num="{num}">
      <div class="card-title">{card['title']}</div>
      <div class="card-stars-badge">{card.get('badge', '')}</div>
      <div class="card-body">{card['body']}</div>
      {f'<div style="margin-top:16px;">{prob_html}</div>' if prob_html else ''}
    </div>''')

    return '\n    '.join(cards)


def build_hand_section(hand_data):
    if not hand_data or not hand_data.get('items'):
        return ''

    cards_html = ''
    for item in hand_data['items']:
        conflict_tag = ''
        if item.get('status') == 'match':
            conflict_tag = f'<div class="conflict-tag match">{item["status_text"]}</div>'
        elif item.get('status') == 'conflict':
            conflict_tag = f'<div class="conflict-tag conflict">{item["status_text"]}</div>'
            if item.get('resolution'):
                conflict_tag += f'<div style="font-size:11px;color:var(--ivory-dim);margin-top:6px;line-height:1.7;">取舍：{item["resolution"]}</div>'

        cards_html += f'''<div class="hand-card">
        <div class="hand-card-title">{item['title']}</div>
        <div class="hand-card-body">{item['body']}</div>
        {conflict_tag}
      </div>\n'''

    return f'''<div class="section-title">手相互证</div>
  <div class="hand-section">
    <div class="hand-grid">{cards_html}</div>
  </div>'''


def build_calibration(questions):
    cn_nums = ['一', '二', '三', '四', '五']
    html = ''
    for i, q in enumerate(questions[:5]):
        num = cn_nums[i] if i < len(cn_nums) else str(i + 1)
        hint = f'<span>{q["hint"]}</span>' if q.get('hint') else ''
        html += f'''<div class="cal-q">
        <div class="cal-num">{num}</div>
        <div class="cal-text">{q['text']}{hint}</div>
      </div>\n'''
    return html


def generate_html(chart_data, reading_data, template_path):
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()

    soul_branch = chart_data['soul_palace_branch']
    body_branch = chart_data['body_palace_branch']

    # Find soul palace stars
    soul_palace = next((p for p in chart_data['palaces'] if '命宫' in p.get('tags', [])), None)
    soul_stars = '·'.join(soul_palace['major_stars']) if soul_palace and soul_palace['major_stars'] else '空宫（借对宫星曜）'

    # Find current decadal (based on age - approximate)
    hour_name = HOUR_NAMES_MAP.get(chart_data['hour_index'], '丑时')

    # Determine current decadal palace
    current_decadal_branch = ''
    if reading_data.get('current_decadal_branch'):
        current_decadal_branch = reading_data['current_decadal_branch']

    # Build palace grid
    palace_cells = build_palace_grid(
        chart_data['palaces'], soul_branch, body_branch, current_decadal_branch
    )

    # Build four hua tags
    four_hua_tags = build_four_hua_tags(chart_data['year_mutagens'])

    # Build reading cards
    reading_cards = build_reading_cards(reading_data)

    # Build hand section
    hand_section = build_hand_section(reading_data.get('hand_reading'))

    # Build calibration
    calibration = build_calibration(reading_data.get('calibration_questions', []))

    # Date info
    solar = chart_data.get('solar_date', '')
    lunar = chart_data.get('lunar_date', '')
    chinese = chart_data.get('chinese_date', '')
    year_stem = chart_data['palaces'][0]['heavenly_stem'] if chart_data['palaces'] else ''

    # Extract year stem/branch from chinese_date
    parts = chinese.split() if chinese else []
    year_sb = parts[0] if parts else ''
    year_stem_char = year_sb[0] if len(year_sb) >= 2 else ''
    year_branch_char = year_sb[1] if len(year_sb) >= 2 else ''

    date_info = f'公历 {solar}' if solar else ''
    lunar_info = f'农历 {lunar}' if lunar else ''

    replacements = {
        '{{YEAR_STEM}}': year_stem_char,
        '{{YEAR_BRANCH}}': year_branch_char,
        '{{HOUR_NAME}}': hour_name,
        '{{LUNAR_DATE}}': lunar,
        '{{GENDER}}': chart_data['gender'],
        '{{FIVE_ELEMENTS}}': chart_data['five_elements'],
        '{{SOUL_PALACE_BRANCH}}': soul_branch,
        '{{SOUL_PALACE_STARS}}': soul_stars,
        '{{CURRENT_DECADAL}}': reading_data.get('current_decadal_display', ''),
        '{{PALACE_CELLS}}': palace_cells,
        '{{FOUR_HUA_TAGS}}': four_hua_tags,
        '{{DATE_INFO}}': date_info,
        '{{LUNAR_INFO}}': lunar_info,
        '{{READING_CARDS}}': reading_cards,
        '{{HAND_SECTION}}': hand_section,
        '{{CALIBRATION_QUESTIONS}}': calibration,
    }

    html = template
    for key, val in replacements.items():
        html = html.replace(key, str(val))

    return html


def main():
    parser = argparse.ArgumentParser(description='命盘 HTML 生成')
    parser.add_argument('--chart', required=True, help='排盘数据 JSON 文件')
    parser.add_argument('--reading', required=True, help='解读数据 JSON 文件')
    parser.add_argument('--template', help='HTML 模板路径（默认使用内置模板）')
    parser.add_argument('--output', required=True, help='输出 HTML 文件路径')

    args = parser.parse_args()

    with open(args.chart, 'r', encoding='utf-8') as f:
        chart_data = json.load(f)

    with open(args.reading, 'r', encoding='utf-8') as f:
        reading_data = json.load(f)

    template_path = args.template
    if not template_path:
        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'chart_template.html')
        template_path = os.path.abspath(template_path)

    html = generate_html(chart_data, reading_data, template_path)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'命盘已生成: {args.output}')


if __name__ == '__main__':
    main()
