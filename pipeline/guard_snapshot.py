#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集结果校验 + 快照回退。

问题背景：凌晨/业务低峰时盯盘接口会返回 0 行，风神会话掉线时风神指标为空，
如果照单全收就会推出"缺数据/空表"的看板。这里做三件事：
  1) 校验本轮采集的关键数据是否完整；
  2) 不完整 -> 自动回退到上一轮有效快照（并保留回退标记）；
  3) 完整 -> 把本轮存为下一轮的备份。

用法: python guard_snapshot.py check
退出码: 0 = 数据可用（可能已回退）；1 = 无有效数据可用
"""
import json
import os
import shutil
import sys

ROOT = r'C:\Users\luansha\WorkBuddy\2026-11-07-23-44-13'
AGG = os.path.join(ROOT, 'agg_board_1122')
CDDP = os.path.join(ROOT, 'cddp_1122')

FILES = {
    'agg': os.path.join(AGG, 'data.json'),
    'site': os.path.join(CDDP, 'data.json'),
    'bd': os.path.join(CDDP, 'data_bd_tms.json'),
}

# 四个县的站点名（盯站点表里必须能查到，否则说明接口返回了空表）
KEY_SITES = ['逸海-思茅站', '逸海-景谷站', '逸海-景东站', '逸海-墨江站', '逸海-镇沅站']


def check_agg(d):
    errs = []
    fs = (d.get('fengshen') or {}).get('思茅区') or {}
    if not fs.get('ok') or not fs.get('data'):
        errs.append('风神思茅站数据缺失')
    elif not (fs['data'].get('allKnightCount') or 0):
        errs.append('风神思茅站骑手数为 0')
    fp = d.get('fengshenPeriod') or {}
    if not fp.get('ok') or not fp.get('riderCount'):
        errs.append('风神时段明细缺失')
    xy = d.get('xy') or {}
    lines = xy.get('lines') or {}
    if not any((L.get('teams') or []) and L.get('lineStats') for L in lines.values()):
        errs.append('轩辕小队数据缺失')
    return errs


def check_site(d):
    errs = []
    st = d.get('siteTable') or {}
    recs = st.get('tableRecords') or []
    if len(recs) < 5:
        errs.append(f'盯站点表仅 {len(recs)} 行（异常）')
        return errs
    blob = json.dumps(recs, ensure_ascii=False)
    missing = [s for s in KEY_SITES if s not in blob]
    if missing:
        errs.append('盯站点表缺少站点：' + '、'.join(missing))
    return errs


def check_bd(d):
    errs = []
    t = (d.get('tables') or {}).get('全部运力线') or {}
    recs = t.get('records') or []
    if len(recs) < 3:
        errs.append(f'盯商圈表仅 {len(recs)} 行（异常）')
    return errs


CHECKERS = {'agg': check_agg, 'site': check_site, 'bd': check_bd}


def prev_path(fp):
    return fp + '.prev.json'


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if mode == 'save':
        for fp in FILES.values():
            if os.path.exists(fp):
                shutil.copy2(fp, prev_path(fp))
        print('snapshot saved')
        return 0

    reverted, fatal = [], []
    for key, fp in FILES.items():
        errs = []
        if not os.path.exists(fp):
            errs = ['文件不存在']
        else:
            try:
                d = json.load(open(fp, encoding='utf-8'))
                errs = CHECKERS[key](d)
            except Exception as e:
                errs = [f'解析失败 {e}']
        if not errs:
            continue
        print(f'[{key}] 数据校验不通过：{"；".join(errs)}')
        pp = prev_path(fp)
        if os.path.exists(pp):
            try:
                shutil.copy2(pp, fp)
                d = json.load(open(fp, encoding='utf-8'))
                meta = d.setdefault('meta', {})
                meta['revertedAt'] = meta.get('collectedAt')
                meta['revertedReason'] = '；'.join(errs)
                json.dump(d, open(fp, 'w', encoding='utf-8'), ensure_ascii=False)
                print(f'[{key}] 已回退到上一轮有效快照')
                reverted.append(key)
            except Exception as e:
                print(f'[{key}] 回退失败 {e}')
                fatal.append(key)
        else:
            print(f'[{key}] 无可用快照')
            fatal.append(key)

    if fatal:
        print('GUARD FAIL:', ','.join(fatal))
        return 1
    if reverted:
        print('GUARD OK (已回退):', ','.join(reverted))
    else:
        print('GUARD OK')
    # 本轮有效 -> 存为下一轮备份
    for fp in FILES.values():
        if os.path.exists(fp):
            try:
                d = json.load(open(fp, encoding='utf-8'))
                if not (d.get('meta') or {}).get('revertedAt'):
                    shutil.copy2(fp, prev_path(fp))
            except Exception:
                pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
