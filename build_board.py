# -*- coding: utf-8 -*-
"""聚合看板：轩辕盯盘 + 轩辕小队 + 风神实时考勤 → 单文件 HTML"""
import json, os, datetime
from collections import defaultdict

ROOT = r'C:\Users\luansha\WorkBuddy\2026-11-07-23-44-13'
AGG = os.path.join(ROOT, 'agg_board_1122')
CDDP = os.path.join(ROOT, 'cddp_1122')

agg = json.load(open(os.path.join(AGG, 'data.json'), encoding='utf-8'))
cddp = json.load(open(os.path.join(CDDP, 'data.json'), encoding='utf-8'))
bd = json.load(open(os.path.join(CDDP, 'data_bd_tms.json'), encoding='utf-8'))

def num(v):
    if v is None or v == '' or v == '-': return None
    if isinstance(v, str):
        s = v.replace('%','').replace(',','').strip()
        try: return float(s)
        except ValueError: return None
    try: return float(v)
    except (TypeError, ValueError): return None

def pct(v): return None if v is None else round(v, 2)

# ---------- 时段口径数据 ----------
fs_period = agg.get('fengshenPeriod') or {}
# 盯盘时段字段：current_shift_driver_count(时段排班) / shift_online_driver_count(时段排班且在线) / shift_online_driver_rate(时段排班在线率)
# 时段排班未在线 = 时段排班骑手数 - 时段排班且在线数（统一计算口径）
def period_offline(ps, pso):
    return None if ps is None or pso is None else max(0, ps - pso)

# ---------- 站点维度 ----------
# 风神（仅思茅站有权限，7 指标齐全）
fs = agg['fengshen']['思茅区']['data'] or {}
site_rows = []
_fs_scale = num(fs.get('allKnightCount')); _fs_sched = num(fs.get('shiftedKnightCount')); _fs_online = num(fs.get('onlineKnight'))
site_rows.append({
    'city':'思茅区','site':'逸海-思茅站','line':'—',
    'scale':_fs_scale, 'sched':_fs_sched,
    'online':_fs_online, 'onlineRate':pct(_fs_online/_fs_sched*100) if _fs_sched else None,
    'periodSched':fs_period.get('periodScheduled'), 'periodSchedOnline':fs_period.get('periodSchedOnline'),
    'periodSchedOnlineRate':fs_period.get('periodSchedOnlineRate'),
    'schedOffline':num(fs.get('shiftedOfflineCount')),
    'periodSchedOffline':period_offline(fs_period.get('periodScheduled'), fs_period.get('periodSchedOnline')),
    'src':'风神实时考勤',
    'note':f"在线率=在线÷排班；时段口径来自{fs_period.get('timeName','')}（{fs_period.get('timeCode','')}）骑手明细",
})
# 盯盘（5 站点，5 指标；规模/在线率源站未提供）
site_ids = {'逸海-景谷站':'景谷','逸海-景东站':'景东','逸海-墨江站':'墨江','逸海-镇沅站':'镇沅'}
for r in cddp['siteTable']['tableRecords']:
    name = r.get('subject_name','')
    if name in site_ids:
        _sched = num(r.get('shift_driver_count')); _online = num(r.get('kai_gong_driver_count'))
        _ps = num(r.get('current_shift_driver_count')); _pso = num(r.get('shift_online_driver_count'))
        site_rows.append({
            'city':site_ids[name],'site':name,'line':'—',
            'scale':None,'sched':_sched,
            'online':_online,'onlineRate':pct(_online/_sched*100) if _sched else None,
            'periodSched':_ps,
            'periodSchedOnline':_pso,
            'periodSchedOnlineRate':pct((num(r.get('shift_online_driver_rate')) or 0)*100),
            'schedOffline':num(r.get('shift_no_attend_driver_count')),
            'periodSchedOffline':period_offline(_ps, _pso),
            'src':'轩辕盯盘','note':'时段口径：当前排班应开工/当前排班且开工/当前排班开工率；规模源站未提供',
        })
order = {'逸海-思茅站':0,'逸海-景谷站':1,'逸海-景东站':2,'逸海-墨江站':3,'逸海-镇沅站':4}
site_rows.sort(key=lambda x: order.get(x['site'],9))

# ---------- 站点 × 运力线维度（盯商圈分运力线）----------
bd_map = {
    '逸海-思茅站':'普洱思茅区中心商圈','逸海-景谷站':'普洱-景谷-景谷主商圈',
    '逸海-景东站':'普洱-景东-景东商圈','逸海-墨江站':'普洱-墨江-墨江商圈',
    '逸海-镇沅站':'普洱-镇沅-镇沅商圈',
}
line_map = {'专送':'专送','普众':'普通众包','优选':'优选','蜂跑':'蜂跑','优远':'优远','联盟':'联盟','未知':'未知'}
site_line_rows = []
# 直接用当轮盯商圈接口数据（tables[运力线].records），不再读静态 CSV（CSV 不会自动刷新，会一直是旧数据）
bd_subject_to_site = {v: k for k, v in bd_map.items()}
city_of = {'逸海-思茅站':'思茅区','逸海-景谷站':'景谷','逸海-景东站':'景东','逸海-墨江站':'墨江','逸海-镇沅站':'镇沅'}
_bd_tables = bd.get('tables') or {}
for _tname, _tbl in _bd_tables.items():
    if _tname == '全部运力线':
        continue
    _line = line_map.get(_tname, _tname)
    _seen = set()
    for r in (_tbl.get('records') or []):
        _sid = r.get('subject_id')
        if _sid in _seen:      # 同一商圈在单线查询里会重复返回，按 subject_id 去重
            continue
        _seen.add(_sid)
        _sitename = bd_subject_to_site.get(r.get('subject_name'))
        if not _sitename:
            continue
        _sched = num(r.get('shift_driver_count'))
        _online = num(r.get('kai_gong_driver_count'))
        _ps = num(r.get('current_shift_driver_count'))
        _pso = num(r.get('shift_online_driver_count'))
        _rate = num(r.get('shift_online_driver_rate'))
        if _sched is None and _online is None and _ps is None:
            continue        # 源站该商圈在此运力线下无任何数据（如「未知」线），不展示空行
        site_line_rows.append({
            'city': city_of.get(_sitename, ''),
            'site': _sitename, 'line': _line,
            'scale': None, 'sched': _sched, 'online': _online,
            'onlineRate': pct(_online / _sched * 100) if _sched else None,
            'periodSched': _ps,
            'periodSchedOnline': _pso,
            'periodSchedOnlineRate': pct(_rate * 100) if _rate is not None else None,
            'schedOffline': num(r.get('shift_no_attend_driver_count')),
            'periodSchedOffline': period_offline(_ps, _pso),
            'src': '轩辕盯盘/盯商圈',
            'note': '时段口径：当前排班应开工/当前排班且开工/当前排班开工率',
        })
site_line_rows.sort(key=lambda x:(order.get(x['site'],9), x['line']))

# ---------- 小队维度（轩辕考勤 cdsspbkq）----------
team_rows = []
for line, L in agg['xy']['lines'].items():
    for t in L['teams']:
        s = L['teamStats'].get(t['name']) or {}
        scale = num(s.get('capacityScale')); sched = num(s.get('todayScheduledNum')); online = num(s.get('onlineNum'))
        so = num(s.get('todayScheduledAttendNum'))
        team_rows.append({
            'city':'思茅区','site':'逸海-思茅站','line':line,'team':t['name'],
            'scale':scale,'sched':sched,'online':online,
            'onlineRate':pct(online/sched*100) if sched else None,
            'periodSched':num(s.get('scheduledNum')),
            'periodSchedOnline':num(s.get('timeScheduledAttendRiderNumByOnline')),
            'periodSchedOnlineRate':pct(num(s.get('timeScheduledAttendRateNew'))),
            'schedOffline':None if (sched is None or so is None) else max(0, sched - so),
            'periodSchedOffline':period_offline(num(s.get('scheduledNum')), num(s.get('timeScheduledAttendRiderNumByOnline'))),
            'src':'轩辕考勤','note':'时段口径：当前时段排班/时段排班出勤(在线)/时段出勤达成率',
        })
team_rows.sort(key=lambda x: ({'优选':0,'蜂跑':1,'优远':2}.get(x['line'],9), x['team']))

# ---------- 小组维度（仅思茅站，风神 squad 骑手分组）----------
import json as _json
# 优先用当轮采集的小组与当前时段骑手明细；缺失时才回退到历史静态快照（并标注）
_squads = agg.get('fsSquads') or []
_riders = agg.get('fsPeriodRiders') or []
_fs_stale = False
if not _squads or not _riders:
    _fs_detail = _json.load(open(os.path.join(ROOT,'aeolus_1122','data.json'), encoding='utf-8'))
    _squads = _fs_detail.get('squads') or []
    _fs_stale = True
    print('WARN: 当轮小组数据缺失，小组维度回退到静态快照', os.path.join(ROOT,'aeolus_1122','data.json'))
# 与看板标注时段保持一致：优先用 fengshenPeriod 的当前时段（151 等），而非 aeolus data.json 的 currentTimeCode（可能滞后）
_fscur = str(fs_period.get('timeCode') or 140)
_fs_riders = _riders if _riders else ((_fs_detail.get('attendance') or {}).get(_fscur, {}).get('riders') or [])
_rider_squad = {}
for _sq in _squads:
    for _kid in (_sq.get('knightIds') or []):
        _rider_squad[str(_kid)] = _sq.get('squadName','')
squad_rows = []
for _sq in _squads:
    _name = _sq.get('squadName','')
    _members = [r for r in _fs_riders if _rider_squad.get(str(r.get('knightId'))) == _name]
    _ps = sum(1 for r in _members if r.get('timeGrouped') is True)
    _pso = sum(1 for r in _members if r.get('timeGrouped') is True and ((r.get('timeOnlineTime') or 0) > 0))
    _sched = _ps if _ps else sum(1 for r in _members if r.get('todayScheduled') is True)
    # workStatus 映射（源站 JS 反推）：1=上班(在线) 2=小休 3=下班(离线) 5=申请下班
    _ws_on = sum(1 for r in _members if r.get('workStatus') == 1)
    _ws_rest = sum(1 for r in _members if r.get('workStatus') == 2)
    _ws_off = sum(1 for r in _members if r.get('workStatus') == 3)
    _ws_apply = sum(1 for r in _members if r.get('workStatus') == 5)
    _on = _ws_on + _ws_apply
    _rate = pct(_on/len(_members)*100) if _members else None
    squad_rows.append({
        'city':'思茅区','site':'逸海-思茅站','line':'—','squad':_name,
        'scale':len(_members),'sched':_sched,'online':_on,
        'wsOnline':_ws_on, 'wsRest':_ws_rest, 'wsOffline':_ws_off, 'wsApplyOff':_ws_apply,
        'wsStatus':f"在线{_ws_on} / 离线{_ws_off} / 小休{_ws_rest}" + (f" / 申请下班{_ws_apply}" if _ws_apply else ''),
        'onlineRate':_rate,
        'periodSched':_ps,'periodSchedOnline':_pso,
        'periodSchedOnlineRate':pct(_pso/_ps*100) if _ps else None,
        'schedOffline':None if not _sched else max(0, _sched - _on),
        'periodSchedOffline':period_offline(_ps, _pso),
        'src':'风神小组' + ('（静态快照）' if _fs_stale else ''),
        'note':f"小组={_name}，组长={_sq.get('managerName','')}；在线=workStatus 1(上班)+5(申请下班)，离线=3(下班)，小休=2；在线率=在线÷小组人数" + ('；⚠️ 本轮小组数据来自静态快照' if _fs_stale else ''),
    })
squad_rows.sort(key=lambda x: (-(x['periodSched'] or 0), x['squad']))

# ---------- 运力线汇总（轩辕考勤线级，思茅商圈片）----------
line_rows = []
for line, L in agg['xy']['lines'].items():
    s = L['lineStats'] or {}
    scale=num(s.get('capacityScale')); sched=num(s.get('todayScheduledNum')); online=num(s.get('onlineNum'))
    so=num(s.get('todayScheduledAttendNum'))
    line_rows.append({
        'city':'思茅区','site':'逸海-思茅站','line':line,
        'scale':scale,'sched':sched,'online':online,
        'onlineRate':pct(online/sched*100) if sched else None,
        'periodSched':num(s.get('scheduledNum')),
        'periodSchedOnline':num(s.get('timeScheduledAttendRiderNumByOnline')),
        'periodSchedOnlineRate':pct(num(s.get('timeScheduledAttendRateNew'))),
        'schedOffline':None if (sched is None or so is None) else max(0, sched-so),
        'periodSchedOffline':period_offline(num(s.get('scheduledNum')), num(s.get('timeScheduledAttendRiderNumByOnline'))),
        'src':'轩辕考勤','note':'商圈片口径；时段排班/时段排班且在线/时段排班在线率',
    })

DATA = {
    'meta': {
        'collectedAt': agg['meta']['finishedAt'],
        'cddpAt': cddp['meta']['finishedAt'],
        'bdAt': bd['meta']['finishedAt'],
        'periodCode': fs_period.get('timeCode'), 'periodName': fs_period.get('timeName') or '',
        'periodRange': (next((f"{p.get('startTime','')}-{p.get('endTime','')}" for p in (agg.get('xy',{}).get('periods') or []) if str(p.get('timeCode'))==str(fs_period.get('timeCode'))), '')
                       or fs_period.get('periodRange') or ''),
        'sites': ['逸海-思茅站','逸海-景谷站','逸海-景东站','逸海-墨江站','逸海-镇沅站'],
        'areas': ['思茅区','景谷','景东','墨江','镇沅'],
        'reverted': bool(agg['meta'].get('revertedAt')),
        'revertedReason': agg['meta'].get('revertedReason',''),
        'fsStale': bool(_fs_stale),
    },
    'siteRows': site_rows, 'siteLineRows': site_line_rows, 'teamRows': team_rows,
    'squadRows': squad_rows, 'lineRows': line_rows,
}

# ---------- 合并表：城市维度(站点/运力线) → 小队 → 小组 ----------
LINE_ORDER = {'专送':0,'优选':1,'蜂跑':2,'优远':3,'普通众包':4}
def linekey(l): return LINE_ORDER.get(l, 9)
all_rows = []
# 1) 城市维度（过滤未知/联盟，按截图线序）
for _c in ['思茅区','景谷','景东','墨江','镇沅']:
    _rs = sorted([r for r in site_line_rows if r['city']==_c and r['line'] in LINE_ORDER], key=lambda r: linekey(r['line']))
    for _i, _r in enumerate(_rs):
        _r2 = dict(_r); _r2['dim']='城市'; _r2['siteShow']=_r['site'] if _i==0 else '–'
        _r2['sortKey']=f"1-{['思茅区','景谷','景东','墨江','镇沅'].index(_c)}-{linekey(_r['line'])}"
        all_rows.append(_r2)
# 2) 小队维度（仅思茅站）
for _r in team_rows:
    _r2=dict(_r); _r2['dim']='小队'; _r2['siteShow']='–'; _r2['sortKey']=f"2-{linekey(_r['line'])}-{_r['team']}"
    all_rows.append(_r2)
# 3) 小组维度（仅思茅站）
for _r in squad_rows:
    _r2=dict(_r); _r2['dim']='小组'; _r2['siteShow']='–'; _r2['sortKey']=f"3-{_r['squad']}"
    all_rows.append(_r2)
DATA['allRows']=all_rows
OUT = os.path.join(AGG, 'board_data.json')
json.dump(DATA, open(OUT,'w',encoding='utf-8'), ensure_ascii=False)
print('data rows', len(site_rows), len(site_line_rows), len(team_rows), len(squad_rows), len(line_rows))





HTML = r'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>运力聚合看板 · 五区县</title>
<style>
:root{--bg:#f3f6fc;--card:#fff;--text:#172033;--muted:#7a869c;--line:#e5eaf3;--blue:#3b5bdb;--ink:#1b2a5b;--shadow:0 3px 16px rgba(28,45,90,.07)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:13px/1.55 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
header{background:linear-gradient(112deg,#16265c,#3b5bdb 58%,#647fe8);color:#fff;padding:20px 34px;position:relative;overflow:hidden}
header:after{content:"";position:absolute;right:-70px;top:-100px;width:320px;height:320px;border-radius:50%;background:rgba(255,255,255,.06)}
header h1{margin:0;font-size:21px;font-weight:650;letter-spacing:.6px}
.hmeta{display:flex;gap:10px;margin-top:10px;flex-wrap:wrap}
.hchip{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.22);border-radius:8px;padding:5px 12px;font-size:11.5px;backdrop-filter:blur(4px)}
.hchip b{font-size:13px;color:#fff}
.wrap{max-width:1640px;margin:0 auto;padding:18px 26px 70px}
.citybar{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-bottom:16px}
.city{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:12px 10px;text-align:center;cursor:pointer;transition:.18s;box-shadow:var(--shadow)}
.city:hover{transform:translateY(-2px);box-shadow:0 7px 20px rgba(30,50,90,.13)}
.city.on{border-color:var(--blue);background:linear-gradient(140deg,#eef2ff,#fff);box-shadow:0 5px 18px rgba(59,91,219,.2)}
.city .nm{font-size:13.5px;font-weight:650}.city .nums{margin-top:6px;font-size:10.5px;color:var(--muted);line-height:1.65}
.city .nums b{font-size:15px;color:var(--ink);font-weight:700}
.bar{display:flex;gap:12px;align-items:center;margin-bottom:16px;flex-wrap:wrap}
.tools{margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
input,select{padding:7px 10px;border:1px solid var(--line);border-radius:8px;background:#fff;font-size:12px;color:var(--text);outline:none}
input:focus,select:focus{border-color:var(--blue)}
.btn{border:1px solid var(--line);background:#fff;padding:7px 11px;border-radius:8px;cursor:pointer;font-size:11px;color:var(--muted)}
.hero{display:grid;grid-template-columns:repeat(4,1fr);gap:11px;margin-bottom:17px}
.hcard{background:linear-gradient(150deg,#fff,#f8faff);border:1px solid var(--line);border-radius:13px;padding:13px 16px;box-shadow:var(--shadow);position:relative;overflow:hidden}
.hcard:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--blue)}
.hcard.g:before{background:#0ca678}.hcard.a:before{background:#e8590c}.hcard.r:before{background:#c92a2a}
.hcard .k{font-size:11px;color:var(--muted)}.hcard .v{font-size:26px;font-weight:700;margin-top:4px;color:var(--ink);font-variant-numeric:tabular-nums}
.hcard .h{font-size:10px;color:#9aa5b8;margin-top:3px}
.section{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);margin-bottom:20px;overflow:hidden}
.stitle{display:flex;align-items:center;justify-content:space-between;padding:13px 18px;border-bottom:1px solid var(--line);background:linear-gradient(90deg,#eef2ff,#fff)}
.stitle h2{margin:0;font-size:15px;font-weight:650;color:var(--ink)}
.stitle .badge{font-size:11px;color:var(--muted)}
table{width:100%;border-collapse:separate;border-spacing:0;font-size:12px}
th,td{text-align:center;padding:9px 7px;border-bottom:1px solid #eef1f7;white-space:nowrap}
th{background:#f7f9fd;color:#5c6880;font-weight:650;position:sticky;top:0;z-index:2;border-bottom:2px solid var(--line)}
th:hover{background:#eef2ff;color:var(--blue);cursor:pointer}
tbody tr:hover td{background:#f8faff}
td.txt{color:var(--text);font-weight:550}td.dash{color:#c8d0df}
td.rate{font-weight:750;border-radius:5px}
td.empty{text-align:center;padding:30px;color:var(--muted)}
/* 城市网格分隔：每个城市一个块，块间粗线 */
tr.city-start td{border-top:3px solid #2b4bbd;background:#eef2ff}
tr.city-start td:first-child{box-shadow:inset 4px 0 0 var(--blue)}
tbody tr:first-child td{border-top:0}
tr.bandA td{background:#f9fbff}
tr.bandB td{background:#fff}
tr.city-start td{background:linear-gradient(90deg,#dbe4ff,#eef2ff)}
.foot{padding:9px 16px;background:#fafbfe;border-top:1px solid var(--line);font-size:10.5px;color:var(--muted)}
.hint{font-size:11px;color:var(--muted);margin:8px 2px 0;line-height:1.9}
.tooltip{position:fixed;pointer-events:none;background:#16265c;color:#fff;padding:8px 11px;border-radius:7px;font-size:11px;z-index:99;opacity:0;transition:opacity .1s;max-width:290px;line-height:1.6}
.lg{display:inline-flex;align-items:center;gap:5px;font-size:10px;color:var(--muted);margin-left:10px}
.g1{display:inline-block;width:80px;height:9px;border-radius:5px;background:linear-gradient(90deg,#dc2626,#f97316,#fde047,#5eead4,#2563eb)}
.g2{display:inline-block;width:80px;height:9px;border-radius:5px;background:linear-gradient(90deg,#e03131,#f06595,#b197fc,#5f3dc4,#1e3a8a)}
@media(max-width:1200px){.citybar{grid-template-columns:repeat(3,1fr)}.hero{grid-template-columns:repeat(2,1fr)}}
</style></head><body>
<header><h1>运力聚合看板 · 五区县运营实时监控</h1>
<div class="hmeta">
 <span class="hchip">⏱ 当前时段 <b id="hperiod">—</b></span>
 <span class="hchip">📅 数据时间 <b id="hdata">—</b></span>
 <span class="hchip">🔄 采集时间 <b id="hcollect">—</b></span>
 <span class="hchip" id="hrev" style="display:none">⚠️ 本轮为上一轮有效快照</span>
 <span class="hchip">源站每 10 分钟刷新</span>
</div></header>
<div class="wrap">
  <div class="citybar" id="citybar"></div>
  <div class="bar">
    <div class="tools">
      <select id="fline"><option value="">全部运力线</option></select>
      <input id="q" placeholder="搜索 站点/小队/小组/运力线" style="width:210px">
      <button class="btn" id="reset">重置筛选</button>
      <span id="cnt" style="font-size:11px;color:var(--muted)"></span>
    </div>
  </div>
  <div class="hero" id="hero"></div>
  <div id="sections"></div>
  <div class="hint">
    配色：<span class="lg">低<span class="g1"></span>高</span> —— 在线率与时段在线率共用同一套色阶（蓝色高、红色低），按该列有数值的行强制排名上色，排名越靠前越蓝。
    口径：在线率 = 在线骑手数 ÷ 排班骑手数（全天）；时段排班未在线 = 时段排班骑手数 − 时段排班且在线数；小组在线率按「排班内全天在线 ÷ 排班数」计算（已排除未排班骑手）。
  </div>
</div>
<div class="tooltip" id="tip"></div>
<script>
const D=__DATA__;
const M=[['scale','规模'],['sched','排班数'],['online','在线骑手数'],['onlineRate','在线率(%)'],
 ['periodSched','时段排班骑手数'],['periodSchedOnline','时段排班且在线数'],['periodSchedOnlineRate','时段在线率(%)'],
 ['periodSchedOffline','时段排班未在线骑手数']];
const CITY_ORDER=['思茅区','景谷','景东','墨江','镇沅'];
let city='',sortKey='',sortDir=1;
const tip=document.getElementById('tip');
const SECTIONS=[{dim:'城市',title:'① 城市维度 · 城市 / 站点 / 运力线',cols:['city','siteShow','line']},
 {dim:'小队',title:'② 小队维度 · 各运力线具体小队（仅思茅站）',cols:['city','line','team']},
 {dim:'小组',title:'③ 小组维度 · 风神骑手小组（仅思茅站）',cols:['city','squad','wsOnline','wsOffline','wsRest','wsApplyOff','wsStatus']}];
function sum(rs,k){const v=rs.map(r=>r[k]).filter(x=>x!=null);return v.length?v.reduce((a,b)=>a+b,0):null}
function avg(rs,k){const v=rs.map(r=>r[k]).filter(x=>x!=null);return v.length?Math.round(v.reduce((a,b)=>a+b,0)/v.length*10)/10:null}
function cityRowsD(c){let rs=D.allRows.filter(r=>r.dim==='城市');if(c)rs=rs.filter(r=>r.city===c);return rs}
function filtered(dim){let rs=D.allRows.filter(r=>r.dim===dim);if(city)rs=rs.filter(r=>r.city===city);
 const fl=document.getElementById('fline').value,q=document.getElementById('q').value.trim();
 if(fl)rs=rs.filter(r=>r.line===fl);if(q)rs=rs.filter(r=>Object.values(r).join(' ').indexOf(q)>=0);return rs}
// 蓝高红低：两组独立色阶
// 统一色阶：红(低) → 蓝(高)；按该列「有数值的行」做强制排名后上色
const SCALE=[[220,38,38],[249,115,22],[253,224,71],[94,234,212],[37,99,235]];
let RANKS={};
function calcRanks(rs){const m={};
 for(const k of ['onlineRate','periodSchedOnlineRate']){
  const vals=rs.map(r=>r[k]).filter(v=>v!=null).slice().sort((a,b)=>b-a);
  const n=vals.length;const map=new Map();
  vals.forEach((v,i)=>{if(!map.has(v))map.set(v,n<=1?1:(n-1-i)/(n-1))});m[k]=map}
 return m}
function rateBg(v,key,dim){if(v==null)return '';const map=(RANKS[dim]||{})[key];const t=map&&map.has(v)?map.get(v):0.5;
 const p=t*(SCALE.length-1),i=Math.min(SCALE.length-2,Math.floor(p)),f=p-i;const c=SCALE[i].map((x,j)=>Math.round(x+(SCALE[i+1][j]-x)*f));return 'background:rgba('+c.join(',')+',0.42)'}
function headerInfo(){const m=D.meta;document.getElementById('hperiod').textContent=(m.periodName||'—')+' ('+(m.periodCode||'—')+') '+(m.periodRange||'');
 const fmt=s=>{if(!s)return '—';const d=new Date(s);return new Date(d.getTime()+8*3600e3).toISOString().slice(0,16).replace('T',' ')+' CST'};
 document.getElementById('hdata').textContent=fmt(m.finishedAt||m.collectedAt);document.getElementById('hcollect').textContent=fmt(m.collectedAt);
 const rv=document.getElementById('hrev');if(rv){if(m.reverted){rv.style.display='inline-block';rv.title=m.revertedReason||''}else{rv.style.display='none'}}}
function renderCities(){document.getElementById('citybar').innerHTML=['',...CITY_ORDER].map(c=>{const rs=cityRowsD(c);const ps=sum(rs,'periodSched'),pso=sum(rs,'periodSchedOnline');
 return '<div class="city'+((c||'')===city?' on':'')+'" data-c="'+c+'"><div class="nm">'+(c||'全部城市')+'</div><div class="nums">时段排班 <b>'+(ps==null?'—':ps)+'</b><br>时段在线 <b>'+(pso==null?'—':pso)+'</b></div></div>'}).join('');
 document.querySelectorAll('.city').forEach(e=>e.onclick=()=>{city=e.dataset.c;sortKey='';renderAll()})}
function renderHero(){const rs=cityRowsD(city);const cards=[['覆盖城市',new Set(rs.map(r=>r.city)).size,'个'],['站点数',new Set(rs.map(r=>r.site)).size,'个'],
 ['时段排班骑手',sum(rs,'periodSched'),'人'],['时段在线骑手',sum(rs,'periodSchedOnline'),'人']];
 document.getElementById('hero').innerHTML=cards.map((c,i)=>'<div class="hcard '+['','g','a','r'][i]+'"><div class="k">'+c[0]+'</div><div class="v">'+(c[1]==null?'—':c[1])+'<span style="font-size:12px;color:var(--muted)"> '+c[2]+'</span></div><div class="h">'+(i<2?'当前筛选范围':'当前时段口径')+'</div></div>').join('')}
function renderFline(){const e=document.getElementById('fline');const cur=e.value;e.innerHTML='<option value="">全部运力线</option>'+[...new Set(D.allRows.map(r=>r.line).filter(Boolean))].sort().map(v=>'<option>'+v+'</option>').join('');e.value=cur}
function cellHtml(r,k,dim){const v=r[k];
 if(k==='siteShow')return '<td class="'+(v==='–'?'dash':'txt')+'">'+v+'</td>';
 if(['city','line','team','squad','wsStatus'].indexOf(k)>=0)return '<td class="txt">'+(v==null?'–':v)+'</td>';
 if(['wsOnline','wsOffline','wsRest','wsApplyOff'].indexOf(k)>=0)return '<td class="'+(v?'num':'dash')+'" style="'+(k==='wsOnline'&&v?'color:var(--green);font-weight:700':k==='wsOffline'&&v?'color:var(--red,#c92a2a);font-weight:700':'')+'">'+v+'</td>';
 if(v==null)return '<td class="dash">—</td>';
 if(k==='onlineRate'||k==='periodSchedOnlineRate')return '<td class="rate" style="'+rateBg(v,k,dim)+'">'+v+'%</td>';
 return '<td>'+v+'</td>'}
function renderSections(){let html='';let total=0;
 for(const s of SECTIONS){const rs=filtered(s.dim);total+=rs.length;const cols=[...s.cols,...M.map(m=>m[0])];
  RANKS[s.dim]=calcRanks(rs);
  const label={city:'城市',siteShow:'站点',line:'运力线',team:'小队',squad:'小组',wsOnline:'在线',wsOffline:'离线',wsRest:'小休',wsApplyOff:'申请下班',wsStatus:'在线状态'};M.forEach(m=>label[m[0]]=m[1]);
  const lg='<span class="lg">低<span class="g1"></span>高（按本列有值行排名）</span>';
  html+='<div class="section"><div class="stitle"><h2>'+s.title+'</h2><span class="badge">共 <b>'+rs.length+'</b> 条 '+lg+'</span></div>';
  html+='<div style="overflow:auto"><table><thead><tr>'+cols.map(k=>'<th data-d="'+s.dim+'" data-k="'+k+'">'+label[k]+(sortKey===k?' ↑':'')+'</th>').join('')+'</tr></thead><tbody>';
  if(!rs.length)html+='<tr><td class="empty" colspan="'+cols.length+'">'+(city&&city!=='思茅区'&&s.dim!=='城市'?'该维度仅提供思茅站数据，请筛选思茅区或全部城市':'当前筛选无数据')+'</td></tr>';
  else{let lastCity='',ci=0;for(const r of rs){const isStart=(s.dim==='城市'&&r.city!==lastCity);if(isStart){lastCity=r.city;ci++}
   const band=isStart?'city-start':(ci%2?'bandA':'bandB');
   html+='<tr class="'+band+'">'+cols.map(k=>cellHtml(r,k,s.dim)).join('')+'</tr>'}}
  html+='</tbody></table></div><div class="foot">快照 '+new Date(new Date(D.meta.collectedAt).getTime()+8*3600e3).toISOString().slice(0,16).replace('T',' ')+' CST · 数据来自 '+[...new Set(rs.map(r=>r.src).filter(Boolean))].join(' / ')+'</div></div>'}
 document.getElementById('sections').innerHTML=html;document.getElementById('cnt').textContent='共 '+total+' 条';
 document.querySelectorAll('th[data-k]').forEach(th=>th.onclick=()=>{const d=th.dataset.d,k=th.dataset.k;if(['siteShow','line','team','squad','wsStatus','city'].indexOf(k)>=0)return;sortKey=k;sortDir=1;applySort(d)});
 bindTips()}
function applySort(d){if(!sortKey)return;const idx=SECTIONS.findIndex(s=>s.dim===d);const rows=filtered(d);
 rows.sort((a,b)=>{const x=a[sortKey],y=b[sortKey];if(x==null)return 1;if(y==null)return -1;return (typeof x==='number'?x-y:String(x).localeCompare(String(y)))*sortDir});
 const body=document.querySelectorAll('#sections .section')[idx].querySelector('tbody');const cols=[...SECTIONS[idx].cols,...M.map(m=>m[0])];
 body.innerHTML=rows.map(r=>'<tr>'+cols.map(k=>cellHtml(r,k,d)).join('')+'</tr>').join('');bindTips()}
function bindTips(){document.querySelectorAll('#sections td').forEach(td=>{td.onmouseenter=e=>{const tr=td.parentElement;const th=document.querySelectorAll('#sections th')[td.cellIndex];const key=th?th.dataset.k:'';
  const s=tr.closest('.section');const si=Array.from(document.querySelectorAll('#sections .section')).indexOf(s);const dim=SECTIONS[si].dim;
  const cellTexts=Array.from(tr.children).map(x=>x.textContent.trim());const rs=filtered(dim);
  const r=rs.find(x=>x.city===cellTexts[0]&&(x.siteShow||'')===cellTexts[1]&&(x.line||'–')===cellTexts[2]&&(x.team||'–')===cellTexts[3]&&(x.squad||'–')===cellTexts[4]&&String(x.wsOnline||'')===(cellTexts[5]||''));
  if(!r)return;const v=r[key];tip.innerHTML='<b>'+th.textContent.replace(' ↑','')+'</b>：'+(v==null?'源站未提供':v+(key.indexOf('Rate')>=0?'%':''))+(r.note?'<br><span style="opacity:.75">'+r.note+'</span>':'');tip.style.opacity='1';tip.style.left=(e.clientX+14)+'px';tip.style.top=(e.clientY+14)+'px'};
  td.onmousemove=e=>{tip.style.left=(e.clientX+14)+'px';tip.style.top=(e.clientY+14)+'px'};td.onmouseleave=()=>tip.style.opacity='0'})}
function renderAll(){headerInfo();renderCities();renderFline();renderHero();renderSections()}
document.getElementById('reset').onclick=()=>{city='';sortKey='';document.getElementById('fline').value='';document.getElementById('q').value='';renderAll()};
document.getElementById('q').addEventListener('input',renderSections);
document.getElementById('fline').addEventListener('change',renderSections);
renderAll();
</script></body></html>'''

time = (datetime.datetime.fromisoformat(agg['meta']['finishedAt'].replace('Z','+00:00'))+datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
html = HTML.replace('__TIME__', time).replace('__DATA__', json.dumps(DATA, ensure_ascii=False))
out_html = os.path.join(AGG, '运力聚合看板.html')
open(out_html,'w',encoding='utf-8').write(html)
print('HTML', out_html, len(html), 'bytes')
