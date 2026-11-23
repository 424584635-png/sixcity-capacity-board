// 风神当前时段骑手明细 + 骑手小组（用于时段排班/时段排班且在线/小组维度）
// 取数方式：纯 HTTP（只带 Cookie 令牌），不经过浏览器；令牌失效时降级沿用上一轮数据
import fs from 'fs';
import { post as httpPost, get as httpGet, probeFs } from './pipeline/http_client.mjs';

const ROOT = 'C:/Users/luansha/WorkBuddy/2026-11-07-23-44-13/agg_board_1122';
const out = JSON.parse(fs.readFileSync(ROOT + '/data.json', 'utf-8'));

// 滚动 7 天日期，避免跨天失效
const now = new Date(Date.now() + 8 * 3600e3);
const ds = d => d.toISOString().slice(0, 10);
const endDate = ds(now);
const startDate = ds(new Date(now.getTime() - 6 * 86400e3));

const alive = await probeFs();
if (!alive) {
  // 风神令牌失效（需人工登录）-> 降级：沿用上一轮有效的时段/小组数据，整轮不失败
  let prev = null;
  try { prev = JSON.parse(fs.readFileSync(ROOT + '/data.json.prev.json', 'utf-8')); } catch (e) {}
  if (prev && prev.fengshenPeriod && prev.fengshenPeriod.ok) {
    out.fengshenPeriod = { ...prev.fengshenPeriod, stale: true, staleNote: '风神令牌失效，沿用上一轮有效时段数据' };
    out.fsSquads = prev.fsSquads || [];
    out.fsPeriodRiders = prev.fsPeriodRiders || [];
    out.meta.fsStale = true;
    out.meta.fsStaleAt = prev.meta?.collectedAt || '';
    fs.writeFileSync(ROOT + '/data.json', JSON.stringify(out), 'utf-8');
    console.warn('风神令牌失效，时段明细降级为上一轮数据（timeCode=' + out.fengshenPeriod.timeCode + '）');
    process.exit(0);
  }
  console.error('风神令牌失效且无历史时段数据');
  process.exit(2);
}

// ---- 时段定位：四路兜底 ----
const mins = now.getUTCHours() * 60 + now.getUTCMinutes();
const hm = s => { const [h, m] = String(s || '00:00').split(':').map(Number); return h * 60 + m; };
const hourMap = h => h < 2 ? 100 : h < 4 ? 102 : h < 6 ? 103 : h < 8 ? 111 : h < 10.5 ? 112
  : h < 13.5 ? 120 : h < 15.5 ? 130 : h < 17.5 ? 131 : h < 20 ? 140 : h < 22 ? 150 : 151;
// 静态时段表，作为接口不可用时的兜底（保证看板头部始终有可读的时段名与时间区间）
const NAME_MAP = { 100: '凌晨1', 102: '凌晨2', 103: '凌晨3', 111: '早餐1', 112: '早餐2', 120: '午高峰',
  130: '下午茶1', 131: '下午茶2', 140: '晚高峰', 150: '夜宵1', 151: '夜宵2' };
const RANGE_MAP = { 100: '00:00-02:00', 102: '02:00-04:00', 103: '04:00-06:00', 111: '06:00-08:00',
  112: '08:00-10:30', 120: '10:30-13:30', 130: '13:30-15:30', 131: '15:30-17:30',
  140: '17:30-20:00', 150: '20:00-22:00', 151: '22:00-00:00' };

const timesX = await httpPost('xtop.fs.special.schedule.listCustomTime', { teamId: 17424603, startDate, endDate });
const fsPeriods = (timesX.data || []).filter(p => Number.isInteger(p.timeCode) && p.timeCode !== 2);

let cur = fsPeriods.find(p => { const s = hm(p.startTime), e = hm(p.endTime) || 1440; return mins >= s && mins < e; });
let src = 'fs-range';
if (!cur) { cur = fsPeriods.find(p => p.current); src = 'fs-current'; }
if (!cur) {
  const xy = await httpPost('xtop.xy.special.realTimeAttendance.listCustomTime', { objectType: 2, bdGroupIds: [100000447021] }, 30000);
  const xc = (xy.data || []).find(p => p.current);
  if (xc) { cur = fsPeriods.find(p => p.timeCode === xc.timeCode) || xc; src = 'xy-current'; }
}
if (!cur) { cur = { timeCode: hourMap(now.getUTCHours()), timeName: '', startTime: '', endTime: '' }; src = 'hour-map'; }
const tc = cur.timeCode;
console.log(`时段定位方式=${src} timeCode=${tc} ${cur.timeName || ''} ${cur.startTime || ''}-${cur.endTime || ''}`);

const att = await httpPost('xtop.fs.special.realtimeattendance.listAttendance',
  { teamId: 17424603, timeCode: String(tc), shiftedOffline: 0 });
if (!att.ok) {
  console.error('listAttendance 失败:', att.code, att.err || '');
  process.exit(3);
}
const riders = att.data || [];
const p = fsPeriods.find(x => x.timeCode === tc) || cur;
const timeName = p.timeName || NAME_MAP[tc] || '';
const timeRange = (p.startTime && p.endTime) ? `${p.startTime}-${p.endTime}` : (RANGE_MAP[tc] || '');
const periodScheduled = riders.filter(r => r.timeGrouped === true).length;
const periodSchedOnline = riders.filter(r => r.timeGrouped === true && (r.timeOnlineTime > 0 || r.onlineStatus === true)).length;
out.fengshenPeriod = {
  collectedAt: new Date().toISOString(), timeCode: tc, timeName,
  periodRange: timeRange,
  periodSource: src,
  ok: true, riderCount: riders.length, periodScheduled, periodSchedOnline,
  periodSchedOnlineRate: periodScheduled ? Math.round(periodSchedOnline / periodScheduled * 10000) / 100 : null,
  note: '时段排班=listAttendance 中 timeGrouped=true；时段排班且在线=其中时段在线时长>0 或 onlineStatus=true',
};
// 当前时段骑手明细（小组维度要用 workStatus / 时段在线，必须取当轮）
out.fsPeriodRiders = riders;

// 骑手小组（小组维度用）
const sq = await httpGet('/lpd.meepo.mgmt/team/squad/read/getTeamSquadList?teamId=17424603');
const squads = (sq.data || []).map(s => ({
  squadId: s.squadId, squadName: s.squadName, managerName: s.managerName || '',
  knightIds: (s.teamSquadKnights || []).map(k => k.knightId),
}));
out.fsSquads = squads;
out.fsSquadsAt = new Date().toISOString();
console.log('squads', squads.length, '| members', squads.reduce((a, s) => a + s.knightIds.length, 0));

fs.writeFileSync(ROOT + '/data.json', JSON.stringify(out), 'utf-8');
fs.mkdirSync(ROOT + '/raw', { recursive: true });
fs.writeFileSync(ROOT + '/raw/fs_period_attendance.json', att.text || '', 'utf-8');
console.log('period', tc, timeName, 'riders', riders.length, 'periodScheduled', periodScheduled,
  'periodSchedOnline', periodSchedOnline, 'rate', out.fengshenPeriod.periodSchedOnlineRate);
