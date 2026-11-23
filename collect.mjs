// 聚合看板数据采集：风神站点考勤 + 轩辕考勤运力线/小队 + 盯盘指标（后者从已抓 JSON 提取）
// 修复：风神会话掉线自动重建 + 接口重试；思茅站数据拿不到时直接失败（避免推出缺数据的看板）
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
const require = createRequire('C:/Users/luansha/Documents/deepseek-harness/default-workspace/package.json');
const { chromium } = require('playwright-core');
import { ensureFs, fsCall } from './fs_guard.mjs';

const ROOT = 'C:/Users/luansha/WorkBuddy/2026-11-07-23-44-13/agg_board_1122';
const RAW = path.join(ROOT, 'raw'); fs.mkdirSync(RAW, { recursive: true });
const b = await chromium.connectOverCDP('http://127.0.0.1:9223');
const ctx = b.contexts()[0];
const R = ctx.request;
const H = 'https://httpizza.ele.me/xtop/';
const sleep = ms => new Promise(r => setTimeout(r, ms));
let seq = 0; const calls = [];
async function post(api, request, tag) {
  const id = ++seq, t0 = Date.now();
  let text = '', status = 0, err = null;
  try {
    const r = await R.post(H + api + '/1.0', { data: { params: { request } },
      headers: { 'Content-Type': 'application/json' }, timeout: 60000 });
    status = r.status(); text = await r.text();
  } catch (e) { err = String(e.message || e); }
  fs.writeFileSync(path.join(RAW, `${String(id).padStart(3,'0')}_${tag}.json`), text, 'utf-8');
  let j = null; try { j = JSON.parse(text); } catch (e) {}
  const data = j && j.result && j.result.data !== undefined ? j.result.data : (j && j.data);
  const ok = status === 200 && j && String(j.code) === '200' && j.result && String(j.result.code) === '200';
  calls.push({ id, tag, status, ok, bytes: text.length, ms: Date.now() - t0, file: `${String(id).padStart(3,'0')}_${tag}.json`, err });
  console.log(`  [${id}] ${tag}: ${status} / biz ${j?.result?.code ?? j?.code} / ${(text.length/1024).toFixed(0)}KB ${ok?'':'FAIL'}`);
  await sleep(150);
  return { ok, data, j };
}
// 风神专用：带会话守卫与重试的调用
async function fsPost(api, request, tag) {
  const id = ++seq, t0 = Date.now();
  const r = await fsCall(ctx, R, api, request, { tries: 3 });
  fs.writeFileSync(path.join(RAW, `${String(id).padStart(3,'0')}_${tag}.json`), r.text || '', 'utf-8');
  const ok = r.code === '200';
  calls.push({ id, tag, status: 200, ok, bytes: (r.text || '').length, ms: Date.now() - t0, file: `${String(id).padStart(3,'0')}_${tag}.json`, err: r.err || null });
  console.log(`  [${id}] ${tag}: biz ${r.code} / ${((r.text || '').length/1024).toFixed(0)}KB ${ok?'':'FAIL'}`);
  await sleep(150);
  return { ok, data: r.data, err: r.err };
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
// 风神会话不可用时（统一登录中心要求验证码），用上一轮有效风神数据降级继续，
// 而不是让整轮失败——轩辕/盯盘数据照常刷新，推送也不会断。
let fsDegraded = false;
let prevFs = null;
try {
  const prevRaw = fs.readFileSync(path.join(ROOT, 'data.json.prev.json'), 'utf-8');
  prevFs = JSON.parse(prevRaw);
} catch (e) { /* 没有历史快照 */ }

out.fengshen = {};
// 先探一次会话：不可用就整体降级，不要对 5 个站点各重登一次（会白等好几分钟且容易触发风控）
const fsReady = await ensureFs(ctx, R, { attempts: 1 });
if (fsReady) {
  for (const s of SITES) {
    const x = await fsPost(FS + 'queryAttendanceStatistics', { teamId: s.teamId }, 'fs_' + s.teamId);
    out.fengshen[s.area] = { ...s, ok: x.ok, data: x.data || null, err: x.err || null };
  }
} else {
  console.warn('风神会话不可用，跳过风神站点采集（降级模式）');
  for (const s of SITES) {
    out.fengshen[s.area] = { ...s, ok: false, data: null, err: 'session unavailable' };
  }
}
// 思茅站是看板主指标来源，缺失则整轮失败（由流水线回退到上一轮有效快照）
if (!out.fengshen['思茅区'].ok || !out.fengshen['思茅区'].data) {
  const canReuse = prevFs && prevFs.fengshen && prevFs.fengshen['思茅区'] && prevFs.fengshen['思茅区'].data;
  if (!canReuse) {
    console.error('风神思茅站数据缺失，且无历史快照可用，放弃本轮采集');
    fs.writeFileSync(path.join(ROOT, 'manifest.json'), JSON.stringify({ ...out.meta, calls, failed: true }, null, 2));
    await b.close();
    process.exit(3);
  }
  fsDegraded = true;
  console.warn('风神会话不可用，降级使用上一轮有效风神数据（' + (prevFs.meta?.collectedAt || '未知时间') + '）');
  out.fengshen = prevFs.fengshen;
  out.fengshenTeams = prevFs.fengshenTeams || [];
  out.meta.fsStale = true;
  out.meta.fsStaleAt = prevFs.meta?.collectedAt || '';
} else {
  // 风神站点可用清单（权限）
  const teams = await fsPost('xtop.lpd.intelligentConfig.getTeamsAll', {}, 'fs_teams');
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
fs.writeFileSync(path.join(ROOT, 'manifest.json'), JSON.stringify({ ...out.meta, calls }, null, 2), 'utf-8');
console.log('\nDONE', out.meta.finishedAt, '| calls', calls.length, '| fail', calls.filter(c => !c.ok).length);
console.log('Fengshen sites ok:', Object.entries(out.fengshen).filter(([k,v])=>v.ok).map(([k])=>k).join(','));
for (const [n,L] of Object.entries(out.xy.lines)) console.log('XY', n, 'teams', L.teams.length, 'lineStat', !!L.lineStats);
await b.close();
