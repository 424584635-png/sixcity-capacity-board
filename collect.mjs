// 聚合看板数据采集：风神站点考勤 + 轩辕考勤运力线/小队
// 取数方式：纯 HTTP（只带 Cookie 令牌），不经过浏览器 —— 避免自动登录把同账号的其他人顶下线
import fs from 'fs';
import path from 'path';
import { post as httpPost, probeFs } from './pipeline/http_client.mjs';

const ROOT = 'C:/Users/luansha/WorkBuddy/2026-11-07-23-44-13/agg_board_1122';
const RAW = path.join(ROOT, 'raw'); fs.mkdirSync(RAW, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let seq = 0; const calls = [];
async function post(api, request, tag) {
  const id = ++seq, t0 = Date.now();
  const r = await httpPost(api, request);
  const text = r.text || '', status = r.status || 0;
  fs.writeFileSync(path.join(RAW, `${String(id).padStart(3,'0')}_${tag}.json`), text, 'utf-8');
  const ok = r.ok;
  calls.push({ id, tag, status, ok, bytes: text.length, ms: Date.now() - t0, file: `${String(id).padStart(3,'0')}_${tag}.json`, err: r.err || null });
  console.log(`  [${id}] ${tag}: ${status} / biz ${r.code} / ${(text.length/1024).toFixed(0)}KB ${ok?'':'FAIL'}`);
  await sleep(150);
  return { ok, data: r.data, j: r.j, code: r.code };
}
console.log('START', new Date().toISOString());
const out = { meta: { collectedAt: new Date().toISOString(), areas: ['思茅区','景东','景谷','墨江','镇沅'] } };

// ===== 1. 风神：5 站点实时考勤（仅思茅站有权限） =====
const FS = 'xtop.fs.special.realtimeattendance.';
const SITES = [
  { area: '思茅区', site: '逸海-思茅站', teamId: 17424603 },
  { area: '景谷', site: '逸海-景谷站', teamId: 17427207 },
  { area: '景东', site: '逸海-景东站', teamId: 17437396 },
  { area: '墨江', site: '逸海-墨江站', teamId: 17427209 },
  { area: '镇沅', site: '逸海-镇沅站', teamId: 17438735 },
];
// 风神会话不可用时（令牌失效且未人工续期），用上一轮有效数据降级继续，不中断整轮
let prevFs = null;
try { prevFs = JSON.parse(fs.readFileSync(path.join(ROOT, 'data.json.prev.json'), 'utf-8')); } catch (e) {}

out.fengshen = {};
const fsAlive = await probeFs();
if (fsAlive) {
  for (const s of SITES) {
    const x = await post(FS + 'queryAttendanceStatistics', { teamId: s.teamId }, 'fs_' + s.teamId);
    out.fengshen[s.area] = { ...s, ok: x.ok, data: x.data || null, err: x.code === '401' ? '未登录' : null };
  }
} else {
  console.warn('风神令牌失效（需人工登录），跳过风神采集');
  for (const s of SITES) out.fengshen[s.area] = { ...s, ok: false, data: null, err: 'token expired' };
}
if (!out.fengshen['思茅区'].ok || !out.fengshen['思茅区'].data) {
  const canReuse = prevFs && prevFs.fengshen && prevFs.fengshen['思茅区'] && prevFs.fengshen['思茅区'].data;
  if (!canReuse) {
    console.error('风神思茅站数据缺失，且无历史快照可用，放弃本轮采集');
    fs.writeFileSync(path.join(ROOT, 'manifest.json'), JSON.stringify({ ...out.meta, calls, failed: true }, null, 2));
    process.exit(3);
  }
  console.warn('风神降级：使用上一轮有效风神数据（' + (prevFs.meta?.collectedAt || '未知时间') + '）');
  out.fengshen = prevFs.fengshen;
  out.fengshenTeams = prevFs.fengshenTeams || [];
  out.meta.fsStale = true;
  out.meta.fsStaleAt = prevFs.meta?.collectedAt || '';
} else {
  const teams = await post('xtop.lpd.intelligentConfig.getTeamsAll', {}, 'fs_teams');
  out.fengshenTeams = teams.data || [];
}

// ===== 2. 轩辕考勤：思茅商圈片 × 运力线 × 小队 =====
const XY = 'xtop.xy.special.realTimeAttendance.';
const BD = '100000447021';
const LINES = [{ line: '优选', type: 2 }, { line: '蜂跑', type: 7 }, { line: '优远', type: 8 }];
const times = await post(XY + 'listCustomTime', { objectType: 2, bdGroupIds: [BD] }, 'xy_times');
const periods = times.data || [];
const cur = (periods.find(p => p.current) || {}).timeCode || 120;
out.xy = { bdGroupId: BD, currentTimeCode: cur, periods, lines: {} };
for (const li of LINES) {
  const tm = await post(XY + 'optionalObjectVO', { objectTypes: [li.type], objectType: li.type, bdGroupIds: [BD] }, 'xy_teams_' + li.type);
  const teamsXY = Array.isArray(tm.data) ? tm.data.map(t => ({ id: Number(t.objectId || t.id), name: t.objectName || t.name })) : [];
  const L = { line: li.line, objectType: li.type, teams: teamsXY, lineStats: null, teamStats: {} };
  if (teamsXY.length) {
    const st = await post(XY + 'queryAttendanceStatistics', {
      objectIds: teamsXY.map(t => ({ objectType: li.type, objectId: t.id })),
      objectType: li.type, isCurrentTime: true, timeCode: cur,
    }, 'xy_line_stat_' + li.type);
    L.lineStats = st.data || null;
    for (const t of teamsXY) {
      const s = await post(XY + 'queryAttendanceStatistics', {
        objectIds: [{ objectType: li.type, objectId: t.id }],
        objectType: li.type, isCurrentTime: true, timeCode: cur,
      }, 'xy_team_stat_' + t.id);
      L.teamStats[t.name] = s.data || null;
      await sleep(80);
    }
  }
  out.xy.lines[li.line] = L;
}
out.meta.finishedAt = new Date().toISOString();
fs.writeFileSync(path.join(ROOT, 'data.json'), JSON.stringify(out), 'utf-8');
fs.writeFileSync(path.join(ROOT, 'manifest.json'), JSON.stringify({ ...out.meta, calls }, null, 2));
console.log('\nDONE', out.meta.finishedAt, '| calls', calls.length, '| fail', calls.filter(c => !c.ok).length);
console.log('Fengshen sites ok:', Object.entries(out.fengshen).filter(([k,v])=>v.ok).map(([k])=>k).join(','));
for (const [n,L] of Object.entries(out.xy.lines)) console.log('XY', n, 'teams', L.teams.length, 'lineStat', !!L.lineStats);
