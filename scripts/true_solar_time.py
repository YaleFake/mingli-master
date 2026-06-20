#!/usr/bin/env python3
"""真太阳时校正 —— 紫微排盘纠错前置模块

把"客户报的钟表时间 + 出生地"换算成真太阳时，再换算成 calculate_chart.py
需要的时辰索引（0=早子 … 11=亥 12=晚子），并自动处理跨日。

为什么需要：客户报的是钟表时间（区时，中国统一 UTC+8 / 东经120°基准），
但紫微排盘要用出生地的真太阳时。两者差异来自三项：
  1) 经度时差：出生地经度 ≠ 120°E 造成的固定偏差，每偏 1° = 4 分钟
  2) 均时差(EoT)：地球轨道椭圆+黄赤交角造成的季节性偏差，全年 -14 ~ +16 分钟
  3) 夏令时(DST)：中国 1986–1991 年夏季实行过夏令时，钟表 +1 小时
这三项叠加可达 ±1 小时以上，足以把人推过一个时辰边界 → 排错命宫。

子时换日依据（iztro 源码 src/utils/index.ts）：
  fixLunarDayIndex(lunarDay, timeIndex) = timeIndex>=12 ? lunarDay : lunarDay-1
  即：晚子时(23:00–24:00, index 12) 安星按"次日"算；早子时(00:00–01:00, index 0)
  按当天算。所以本脚本对真太阳时落在 23:00–24:00 的，输出 index 12 + 当天日期；
  落在 00:00–01:00 的，输出 index 0 + 当天日期。iztro 会在内部正确处理。

用法:
    python3 true_solar_time.py --date 1991-8-15 --time 23:30 --city 北京
    python3 true_solar_time.py --date 1991-8-15 --time 14:00 --lon 113.27   # 广州经度
    python3 true_solar_time.py --date 1988-6-20 --time 14:00 --city 上海    # 自动识别夏令时
    python3 true_solar_time.py --date 1991-8-15 --time 23:30 --city 北京 --json
"""
import argparse
import json
import math
import sys
from datetime import datetime, timedelta

# ── 主要城市经度表（东经，度）。不在表里用 --lon 手动给经度 ──
CITY_LON = {
    '北京': 116.41, '上海': 121.47, '天津': 117.20, '重庆': 106.55,
    '广州': 113.27, '深圳': 114.06, '香港': 114.17, '澳门': 113.55,
    '杭州': 120.16, '南京': 118.80, '苏州': 120.62, '宁波': 121.55,
    '成都': 104.07, '武汉': 114.31, '西安': 108.95, '郑州': 113.62,
    '长沙': 112.94, '南昌': 115.86, '合肥': 117.23, '济南': 117.00,
    '青岛': 120.38, '沈阳': 123.43, '大连': 121.62, '哈尔滨': 126.53,
    '长春': 125.32, '石家庄': 114.51, '太原': 112.55, '呼和浩特': 111.75,
    '福州': 119.30, '厦门': 118.10, '南宁': 108.37, '昆明': 102.71,
    '贵阳': 106.71, '兰州': 103.83, '西宁': 101.78, '银川': 106.23,
    '乌鲁木齐': 87.62, '拉萨': 91.13, '海口': 110.35, '台北': 121.56,
}

# ── 中国夏令时区间（含起止日，期间钟表 +1 小时）──
# 来源：1986–1991 年国务院夏令时规定
DST_PERIODS = [
    ('1986-05-04', '1986-09-14'), ('1987-04-12', '1987-09-13'),
    ('1988-04-17', '1988-09-11'), ('1989-04-16', '1989-09-17'),
    ('1990-04-15', '1990-09-16'), ('1991-04-14', '1991-09-15'),
]

STANDARD_MERIDIAN = 120.0  # 北京时间基准经线（东经120°）

HOUR_NAMES = {
    0: '早子时 (00:00-01:00)', 1: '丑时 (01:00-03:00)', 2: '寅时 (03:00-05:00)',
    3: '卯时 (05:00-07:00)', 4: '辰时 (07:00-09:00)', 5: '巳时 (09:00-11:00)',
    6: '午时 (11:00-13:00)', 7: '未时 (13:00-15:00)', 8: '申时 (15:00-17:00)',
    9: '酉时 (17:00-19:00)', 10: '戌时 (19:00-21:00)', 11: '亥时 (21:00-23:00)',
    12: '晚子时 (23:00-00:00)',
}


def equation_of_time(dt):
    """均时差（分钟）。正值表示真太阳时快于平太阳时。
    标准近似公式，精度约 ±0.5 分钟。"""
    n = dt.timetuple().tm_yday
    b = math.radians(360.0 / 365.0 * (n - 81))
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


def in_dst(dt):
    for start, end in DST_PERIODS:
        s = datetime.strptime(start, '%Y-%m-%d')
        e = datetime.strptime(end, '%Y-%m-%d') + timedelta(days=1)
        if s <= dt < e:
            return True
    return False


def hour_to_index(dt):
    """真太阳时 datetime → 时辰索引（含早/晚子时区分）"""
    t = dt.hour + dt.minute / 60.0
    if 23 <= t < 24:
        return 12          # 晚子时
    if 0 <= t < 1:
        return 0           # 早子时
    return int(math.floor((t + 1) / 2))  # 丑..亥


def boundary_distance(dt):
    """到最近时辰边界的分钟数（边界在 1,3,5,...,23,以及 0/24 点）"""
    minutes = dt.hour * 60 + dt.minute
    boundaries = [h * 60 for h in range(1, 24, 2)] + [0, 1440]
    return min(abs(minutes - b) for b in boundaries)


def correct(date_str, time_str, lon, auto_dst=True, force_dst=None):
    dt = datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M')

    # 1) 夏令时回退
    dst = force_dst if force_dst is not None else (auto_dst and in_dst(dt))
    dst_min = -60 if dst else 0

    # 2) 经度时差
    lon_min = (lon - STANDARD_MERIDIAN) * 4.0

    # 3) 均时差
    eot_min = equation_of_time(dt)

    total = dst_min + lon_min + eot_min
    true_dt = dt + timedelta(minutes=total)

    idx = hour_to_index(true_dt)
    dist = boundary_distance(true_dt)

    return {
        'input': {
            'clock_date': date_str, 'clock_time': time_str,
            'longitude': lon, 'dst_detected': bool(dst),
        },
        'corrections_minutes': {
            'dst': dst_min, 'longitude': round(lon_min, 1),
            'equation_of_time': round(eot_min, 1), 'total': round(total, 1),
        },
        'true_solar_datetime': true_dt.strftime('%Y-%m-%d %H:%M'),
        # 喂给 calculate_chart.py 的两个参数：
        'solar_date_for_chart': f'{true_dt.year}-{true_dt.month}-{true_dt.day}',
        'hour_index': idx,
        'hour_name': HOUR_NAMES[idx],
        'boundary_warning': (
            f'真太阳时距时辰边界仅 {dist} 分钟，建议两个相邻时辰都排一盘，'
            f'用校准问答确认' if dist <= 15 else None
        ),
    }


def main():
    p = argparse.ArgumentParser(description='真太阳时校正（紫微排盘前置）')
    p.add_argument('--date', required=True, help='公历出生日期 YYYY-M-D')
    p.add_argument('--time', required=True, help='钟表出生时间 HH:MM（24小时制）')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--city', help='出生城市（查内置经度表）')
    g.add_argument('--lon', type=float, help='出生地东经经度，如 113.27')
    p.add_argument('--no-dst', action='store_true', help='强制不应用夏令时')
    p.add_argument('--force-dst', action='store_true', help='强制应用夏令时(-1h)')
    p.add_argument('--json', action='store_true', help='只输出 JSON')
    args = p.parse_args()

    # 规范化日期为 YYYY-MM-DD 供 strptime
    y, m, d = map(int, args.date.split('-'))
    date_norm = f'{y:04d}-{m:02d}-{d:02d}'

    if args.city:
        if args.city not in CITY_LON:
            print(f'城市"{args.city}"不在内置表，请用 --lon 指定经度。'
                  f'已知城市示例：{"、".join(list(CITY_LON)[:8])}…', file=sys.stderr)
            sys.exit(1)
        lon = CITY_LON[args.city]
    else:
        lon = args.lon

    force_dst = True if args.force_dst else (False if args.no_dst else None)
    r = correct(date_norm, args.time, lon, force_dst=force_dst)
    if args.city:
        r['input']['city'] = args.city

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return

    c = r['corrections_minutes']
    print(f"输入        : {r['input'].get('city', '')} {args.date} {args.time}（钟表/北京时间）")
    print(f"经度        : {lon}°E")
    print(f"夏令时      : {'是 (-60min)' if r['input']['dst_detected'] else '否'}")
    print(f"经度时差    : {c['longitude']:+.1f} min")
    print(f"均时差      : {c['equation_of_time']:+.1f} min")
    print(f"合计校正    : {c['total']:+.1f} min")
    print(f"真太阳时    : {r['true_solar_datetime']}")
    print('-' * 40)
    print(f"→ 排盘日期  : {r['solar_date_for_chart']}")
    print(f"→ 时辰      : {r['hour_name']}  (--hour {r['hour_index']})")
    if r['boundary_warning']:
        print(f"⚠ {r['boundary_warning']}")
    print('-' * 40)
    print(f"下一步：python3 calculate_chart.py --solar {r['solar_date_for_chart']} "
          f"--hour {r['hour_index']} --gender 男/女 --output /tmp/chart.json")


if __name__ == '__main__':
    main()
